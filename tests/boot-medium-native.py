#!/usr/bin/env python3
"""Native observation refusal and GEOM consumer ownership controls."""
import importlib.util
from pathlib import Path
import stat
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
observer=load('observer',ROOT/'tools/boottrace/observe-medium.py')
fixtures=load('fixtures',ROOT/'tests/boot-medium.py')
medium=observer.medium


def topology():
    mesh=fixtures.fixture()
    for node in mesh.iter():
        if node.tag in ('provider','consumer') and 'id' in node.attrib:
            ET.SubElement(node,'mode').text='r0w0e0'
    return mesh


class NativeObservation(unittest.TestCase):
    def test_readiness_waits_for_absence_before_any_native_device_open(self):
        absent=topology()
        absent.find('class/geom/provider/config/rawuuid').text='ffffffff-ffff-ffff-ffff-ffffffffffff'
        environment,_=fixtures.session()
        pause=Mock()
        with patch.object(observer.sys,'platform','freebsd16'), patch.object(observer.os,'geteuid',return_value=0), \
                patch.object(observer,'environment',return_value=environment), \
                patch.object(observer,'snapshot',side_effect=[fixtures.encode(absent),fixtures.encode(topology())]), \
                patch.object(observer.os,'open') as opened:
            result=observer.wait_for_partition(1,pause,clock=Mock(side_effect=[0,0.1]))
            self.assertEqual(result,dict(observations=2,not_enumerated=1))
            pause.assert_called_once_with(0.25)
            opened.assert_not_called()

    def test_readiness_does_not_retry_ambiguity_session_change_or_expired_absence(self):
        environment,_=fixtures.session()
        for error in (ValueError('ambiguous provider'),medium.PartitionNotReady('not enumerated')):
            pause=Mock()
            with patch.object(observer.sys,'platform','freebsd16'), patch.object(observer.os,'geteuid',return_value=0), \
                    patch.object(observer,'environment',return_value=environment), patch.object(observer,'snapshot',return_value=b'fixture'), \
                    patch.object(medium,'resolve_partition',side_effect=error), patch.object(observer.os,'open') as opened:
                with self.assertRaises(type(error)):
                    observer.wait_for_partition(1,pause,clock=Mock(side_effect=[0,2]))
                pause.assert_not_called()
                opened.assert_not_called()
        with patch.object(observer.sys,'platform','freebsd16'), patch.object(observer.os,'geteuid',return_value=0), \
                patch.object(observer,'environment',side_effect=[environment,dict(environment,changed='yes')]), \
                patch.object(observer,'snapshot') as snapshot:
            with self.assertRaisesRegex(ValueError,'session changed'):
                observer.wait_for_partition(1,Mock(),clock=lambda:0)
            snapshot.assert_not_called()

    def test_large_extents_use_complete_bounded_aligned_requests(self):
        data = bytes(range(256)) * 4096
        pread, pwrite = os.pread, os.pwrite
        reads, writes = [], []
        with tempfile.TemporaryFile() as file:
            file.write(bytes(len(data) + 1024));file.flush()
            def write(fd, block, offset):
                self.assertLessEqual(len(block), 65536)
                self.assertEqual((offset % 512, len(block) % 512), (0, 0))
                writes.append((offset, len(block)))
                return pwrite(fd, block, offset)
            with patch.object(observer.os, 'pwrite', side_effect=write):
                self.assertEqual(observer.bounded_write(file.fileno(), 512, data), len(data))
            self.assertEqual(pread(file.fileno(), len(data) + 1024, 0),
                             bytes(512) + data + bytes(512))
            def read(fd, length, offset):
                self.assertLessEqual(length, 65536)
                self.assertEqual((offset % 512, length % 512), (0, 0))
                reads.append((offset, length))
                return pread(fd, length, offset)
            with patch.object(observer.os, 'pread', side_effect=read):
                self.assertEqual(observer.bounded_read(file.fileno(), 512, 522240), data[:522240])
                self.assertEqual(observer.bounded_read(file.fileno(), 512, len(data)), data)
            self.assertGreater(len(reads), 1);self.assertGreater(len(writes), 1)

    def test_short_device_transfers_are_not_retried_or_hidden(self):
        data = b'x' * (3 * 65536)
        pread, pwrite = os.pread, os.pwrite
        with tempfile.TemporaryFile() as file:
            file.write(bytes(len(data)));file.flush()
            calls = []
            def write(fd, block, offset):
                calls.append(offset)
                count = len(block) if len(calls) == 1 else 512
                return pwrite(fd, block[:count], offset)
            with patch.object(observer.os, 'pwrite', side_effect=write):
                self.assertEqual(observer.bounded_write(file.fileno(), 0, data), 65536 + 512)
            self.assertEqual(calls, [0, 65536])
            self.assertEqual(pread(file.fileno(), len(data), 0),
                             data[:65536 + 512] + bytes(len(data) - 65536 - 512))
            calls.clear()
            def read(fd, length, offset):
                calls.append(offset)
                return pread(fd, length if len(calls) == 1 else length - 1, offset)
            with patch.object(observer.os, 'pread', side_effect=read):
                with self.assertRaisesRegex(OSError, 'short device read'):
                    observer.bounded_read(file.fileno(), 0, len(data))
            self.assertEqual(calls, [0, 65536])

    def test_invalid_device_extents_refuse_before_io(self):
        with patch.object(observer.os, 'pread') as read, patch.object(observer.os, 'pwrite') as write:
            for offset, length in ((-512, 512), (1, 512), (0, 513), (False, 512)):
                with self.subTest(offset=offset, length=length), self.assertRaises(ValueError):
                    observer.bounded_read(3, offset, length)
            for offset, block in ((-512, bytes(512)), (1, bytes(512)), (0, bytes(513)), (0, 'secret')):
                with self.subTest(offset=offset), self.assertRaises(ValueError):
                    observer.bounded_write(3, offset, block)
            read.assert_not_called();write.assert_not_called()

    def test_only_own_disk_reader_is_allowed(self):
        mesh=topology();data=fixtures.encode(mesh)
        selected=medium.resolve_partition(data,fixtures.GUID)
        medium.require_idle(data,selected)
        mesh.findall('class')[1].find('geom/provider/mode').text='r1w0e0'
        medium.require_idle(fixtures.encode(mesh),selected,own_reader=True)
        with self.assertRaises(ValueError):medium.require_idle(fixtures.encode(mesh),selected)

    def test_partition_writer_and_separate_disk_reader_counts(self):
        mesh=topology()
        selected=medium.resolve_partition(fixtures.encode(mesh),fixtures.GUID)
        mesh.find('class/geom/provider/mode').text='r1w1e0'
        mesh.find('class/geom/consumer/mode').text='r1w1e1'
        disk=mesh.findall('class')[1].find('geom/provider/mode')
        disk.text='r2w1e1'
        medium.require_idle(fixtures.encode(mesh),selected,own_writer=True)
        disk.text='r3w1e1'
        with self.assertRaises(ValueError):medium.require_idle(fixtures.encode(mesh),selected,own_writer=True)

    def test_partition_reader_writer_or_exclusive_consumer_refused(self):
        selected=medium.resolve_partition(fixtures.encode(topology()),fixtures.GUID)
        for mode in ('r1w0e0','r0w1e0','r0w0e1','r0w0e2','unknown'):
            for target in ('provider/mode','consumer/mode'):
                mesh=topology();mesh.find('class/geom/'+target).text=mode
                with self.subTest(mode=mode,target=target),self.assertRaises(ValueError):
                    medium.require_idle(fixtures.encode(mesh),selected)

    def test_alias_busy_and_open_geometry_change_refused(self):
        mesh=fixtures.add_iso_alias(topology())
        for node in mesh.iter():
            if node.tag in ('provider','consumer') and 'id' in node.attrib and node.find('mode') is None:
                ET.SubElement(node,'mode').text='r0w0e0'
        selected=medium.resolve_partition(fixtures.encode(mesh),fixtures.GUID)
        mesh.findall('class')[-1].find('geom/provider/mode').text='r1w0e0'
        with self.assertRaises(ValueError):medium.require_idle(fixtures.encode(mesh),selected)
        mesh=topology();mesh.find('class/geom/provider/config/start').text='2049'
        with self.assertRaises(ValueError):medium.require_idle(fixtures.encode(mesh),selected)

    def test_platform_and_privilege_refuse_before_device_open(self):
        with patch.object(observer.sys,'platform','linux'),patch.object(observer.os,'open') as opened:
            with self.assertRaises(ValueError):observer.observe()
            opened.assert_not_called()
        with patch.object(observer.sys,'platform','freebsd16'),patch.object(observer.os,'geteuid',return_value=1001),patch.object(observer.os,'open') as opened:
            with self.assertRaises(ValueError):observer.observe()
            opened.assert_not_called()

    def test_installation_identity_disagreement_refused(self):
        _,record=fixtures.session()
        expected=('Daemonarchy installation trace identity v1\nimage_id='+record['image_id']+
                  '\narchive_sha256='+record['archive_sha256']+'\nmode=observe-only\n').encode()
        selected=dict(start_lba=10)
        fs=dict(identity_extent=(1024,len(expected)))
        observer.assert_identity_file(lambda off,n:expected.ljust(n,b'\n'),selected,fs,record)
        with self.assertRaises(ValueError):
            observer.assert_identity_file(lambda off,n:expected.replace(b'observe-only',b'observe-evil').ljust(n,b'\n'),selected,fs,record)

    def test_regular_file_and_symlink_are_not_native_devices(self):
        for mode in (stat.S_IFREG|0o600,stat.S_IFLNK|0o777):
            with self.assertRaises(ValueError):observer.device_identity(SimpleNamespace(st_mode=mode))
        identity=SimpleNamespace(st_mode=stat.S_IFCHR|0o600,st_dev=1,st_ino=2,st_rdev=3)
        self.assertEqual(observer.device_identity(identity),(1,2,3))

    def test_wrong_open_provider_ioctl_geometry_refused(self):
        selected=dict(sector_bytes=512,disk_bytes=1024,disk='/dev/vtbd0')
        def ioctl(fd,request,buf):
            if request==observer.DIOCGSECTORSIZE:buf[:]=(512).to_bytes(4,'little')
            elif request==observer.DIOCGMEDIASIZE:buf[:]=(1024).to_bytes(8,'little')
            else:buf[:]=b'vtbd1\0'.ljust(1024,b'\0')
        with patch.object(observer.fcntl,'ioctl',side_effect=ioctl):
            with self.assertRaises(ValueError):observer.geometry(3,selected)


if __name__=='__main__':unittest.main()
