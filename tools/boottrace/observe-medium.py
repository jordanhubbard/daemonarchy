#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Native FreeBSD read-only boot-medium observation; never opens for writing."""
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


def geometry(fd, selection):
    def ioctl(request, length):
        buf = bytearray(length)
        fcntl.ioctl(fd, request, buf)
        return bytes(buf)
    sector = struct.unpack('<I',ioctl(DIOCGSECTORSIZE,4))[0]
    size = struct.unpack('<q',ioctl(DIOCGMEDIASIZE,8))[0]
    name = ioctl(DIOCGPROVIDERNAME,1024).split(b'\0',1)[0].decode('ascii')
    if (sector != selection['sector_bytes'] or size != selection['disk_bytes'] or
            '/dev/'+name != selection['disk']):
        raise ValueError('open device does not match selected provider')


def observe():
    if sys.platform != 'freebsd' and not sys.platform.startswith('freebsd'):
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
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path,flags)
    try:
        if device_identity(os.fstat(fd)) != before:
            raise ValueError('device identity changed during open')
        geometry(fd,selection)
        medium.require_idle(snapshot(),selection,own_reader=True)
        read = lambda offset,length: os.pread(fd,length,offset)
        gpt = medium.validate_gpt(read,selection)
        filesystem = fat.validate_fat(read,selection,'NORMAL/'+match[2]+'.TXT')
        off,length = filesystem['selected_extent']
        slot_offset = selection['start_lba']*512+off
        slot = read(slot_offset,length)
        record = stick.normal_record(slot)
        correlated = medium.bind_session(snapshot(),kenv,record)
        if environment() != kenv:
            raise ValueError('kernel session changed during observation')
        if (medium.validate_gpt(read,selection) != gpt or
                fat.validate_fat(read,selection,'NORMAL/'+match[2]+'.TXT') != filesystem or
                read(slot_offset,length) != slot):
            raise ValueError('boot-medium metadata changed during observation')
        geometry(fd,selection)
        medium.require_idle(snapshot(),selection,own_reader=True)
        if device_identity(os.lstat(path)) != before or device_identity(os.fstat(fd)) != before:
            raise ValueError('open device identity no longer matches path')
        return dict(schema='daemonarchy/native-boot-medium-observation@1',
                    selection=correlated,gpt=gpt,filesystem=filesystem,
                    read_only=True,writes_admitted=False)
    finally:
        os.close(fd)


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
