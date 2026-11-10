#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Native FreeBSD read-only boot-medium observation; never opens for writing."""
from contextlib import contextmanager
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


medium = module('boot_medium', 'boot-medium.py')
fat = module('boot_fat', 'fat-volume.py')
stick = module('boot_stick', 'stick.py')
# FreeBSD sys/disk.h _IOR('d', 128/129/138, u_int/off_t/char[MAXPATHLEN]).
DIOCGSECTORSIZE = 0x40046480
DIOCGMEDIASIZE = 0x40086481
DIOCGPROVIDERNAME = 0x4400648a


def command(argv):
    result = subprocess.run(argv, capture_output=True, timeout=5, check=True)
    if len(result.stdout) > medium.MAX_XML:
        raise ValueError('native observation exceeds byte budget')
    return result.stdout


def snapshot():
    return command(['/sbin/sysctl','-b','kern.geom.confxml'])


def environment():
    result = {}
    for key in ('partition','session','capture','boot_nonce'):
        name = 'daemonarchy.trace.' + key
        result[name] = command(['/bin/kenv','-q',name]).decode('ascii').strip()
    return result


def device_identity(info):
    if not stat.S_ISCHR(info.st_mode):
        raise ValueError('canonical character device required')
    return info.st_dev, info.st_ino, info.st_rdev


def geometry(fd, selection, partition=False):
    def ioctl(request, length):
        buf = bytearray(length)
        fcntl.ioctl(fd, request, buf)
        return bytes(buf)
    sector = struct.unpack('<I',ioctl(DIOCGSECTORSIZE,4))[0]
    size = struct.unpack('<q',ioctl(DIOCGMEDIASIZE,8))[0]
    name = ioctl(DIOCGPROVIDERNAME,1024).split(b'\0',1)[0].decode('ascii')
    expected_size = selection['sectors']*512 if partition else selection['disk_bytes']
    expected_name = selection['device'] if partition else selection['disk']
    if (sector != selection['sector_bytes'] or size != expected_size or
            '/dev/'+name != expected_name):
        raise ValueError('open device does not match selected provider')


def assert_identity_file(read, selection, filesystem, record):
    off,length = filesystem['identity_extent']
    if not 0 < length <= 512:
        raise ValueError('bounded installation identity required')
    rounded = (length+511)//512*512
    data = read(selection['start_lba']*512+off,rounded)
    if len(data) != rounded:
        raise ValueError('short installation identity read')
    actual = data[:length]
    expected = ('Daemonarchy installation trace identity v1\nimage_id='+
                record['image_id']+'\narchive_sha256='+record['archive_sha256']+
                '\nmode=observe-only\n').encode('ascii')
    if actual != expected:
        raise ValueError('installation identity disagrees with loader session')


DEVICE_IO_LIMIT = 64 * 1024


def bounded_read(fd, offset, length):
    """Read the complete extent using sector-aligned device requests.

    USB CAM paths can refuse a large raw request even when the same sectors
    are readable in smaller transfers. Never accept a short metadata read.
    """
    if (type(offset) is not int or type(length) is not int or
            offset < 0 or length < 0 or offset % 512 or length % 512):
        raise ValueError('sector-aligned device read required')
    content = bytearray()
    while len(content) < length:
        count = min(DEVICE_IO_LIMIT, length - len(content))
        part = os.pread(fd, count, offset + len(content))
        if len(part) != count:
            raise OSError('short device read; incomplete extent refused')
        content.extend(part)
    return bytes(content)


def bounded_write(fd, offset, data):
    """Keep payload transfers bounded without retrying a partial write.

    The frame committer must see the short total and retain the interrupted
    inactive frame. Its flush/readback and header commit order remain intact.
    """
    if (type(offset) is not int or offset < 0 or offset % 512 or
            type(data) is not bytes or len(data) % 512):
        raise ValueError('sector-aligned device write required')
    total = 0
    view = memoryview(data)
    while total < len(data):
        count = min(DEVICE_IO_LIMIT, len(data) - total)
        written = os.pwrite(fd, view[total:total + count], offset + total)
        if type(written) is not int or not 0 <= written <= count:
            raise OSError('invalid device write count')
        total += written
        if written != count:
            break
    return total


@contextmanager
def open_medium(writable=False):
    """Hold one verified descriptor; writable does not bypass admission checks."""
    if not sys.platform.startswith('freebsd'):
        raise ValueError('native FreeBSD observation required')
    if os.geteuid() != 0:
        raise ValueError('native device observation requires root')
    kenv = environment()
    partition = kenv['daemonarchy.trace.partition']
    medium.canonical_uuid(partition)
    session = kenv['daemonarchy.trace.session']
    match = re.fullmatch(r'([0-9a-f-]{36})-([0-9]{4})',session)
    if not match or not 1 <= int(match[2]) <= 32:
        raise ValueError('invalid kernel trace session')
    medium.canonical_uuid(match[1])
    selection = medium.resolve_partition(snapshot(), partition)
    medium.require_idle(snapshot(), selection)
    path = selection['disk']
    before = device_identity(os.lstat(path))
    # O_EXCL is ignored by geom_dev.c. Keep a read-only whole-disk view;
    # a whole-disk write open would spoil its PART consumers. The writer
    # instead holds the selected partition, whose access propagates
    # write-exclusive ownership through g_part_access.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path,flags)
    write_fd = None
    write_identity = None
    try:
        def guard():
            if device_identity(os.fstat(fd)) != before or device_identity(os.lstat(path)) != before:
                raise ValueError('device identity changed during open')
            geometry(fd,selection)
            if write_fd is not None:
                if (device_identity(os.fstat(write_fd)) != write_identity or
                        device_identity(os.lstat(selection['device'])) != write_identity):
                    raise ValueError('writable partition identity changed')
                geometry(write_fd,selection,partition=True)
            medium.require_idle(snapshot(),selection,own_reader=write_fd is None,own_writer=write_fd is not None)
            if environment() != kenv:
                raise ValueError('kernel session changed during observation')
        guard()
        read = lambda offset,length: bounded_read(fd,offset,length)
        gpt = medium.validate_gpt(read,selection)
        filesystem = fat.validate_fat(read,selection,'NORMAL/'+match[2]+'.TXT')
        off,length = filesystem['selected_extent']
        slot_offset = selection['start_lba']*512+off
        slot = read(slot_offset,length)
        record = stick.normal_record(slot)
        correlated = medium.bind_session(snapshot(),kenv,record)
        assert_identity_file(read,selection,filesystem,record)
        if (medium.validate_gpt(read,selection) != gpt or
                fat.validate_fat(read,selection,'NORMAL/'+match[2]+'.TXT') != filesystem or
                read(slot_offset,length) != slot):
            raise ValueError('boot-medium metadata changed during observation')
        guard()
        if writable:
            write_identity = device_identity(os.lstat(selection['device']))
            write_fd = os.open(selection['device'],os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
            guard()
            if (medium.validate_gpt(read,selection) != gpt or
                    fat.validate_fat(read,selection,'NORMAL/'+match[2]+'.TXT') != filesystem or
                    read(slot_offset,length) != slot):
                raise ValueError('medium changed during partition writer open')
        result = dict(schema='daemonarchy/native-boot-medium-observation@1',
                      selection=correlated,gpt=gpt,filesystem=filesystem,
                      installation_identity_verified=True,
                      read_only=not writable,writes_admitted=False)
        yield dict(fd=write_fd if writable else fd,read=read,guard=guard,
                   write_base=selection['start_lba']*512,
                   result=result,record=record,slot=slot,slot_offset=slot_offset)
        guard()
        if (medium.validate_gpt(read,selection) != gpt or
                fat.validate_fat(read,selection,'NORMAL/'+match[2]+'.TXT') != filesystem):
            raise ValueError('boot-medium layout changed during device operation')
        assert_identity_file(read,selection,filesystem,record)
        if not writable and read(slot_offset,length) != slot:
            raise ValueError('normal slot changed during read-only observation')
    finally:
        if write_fd is not None:
            os.close(write_fd)
        os.close(fd)


def observe():
    with open_medium() as state:
        result = state['result']
    return result


def main():
    try:
        result = observe()
    except (ValueError,OSError,UnicodeError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='unavailable',read_only=True,writes_admitted=False,
                              reason=str(error))))
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
