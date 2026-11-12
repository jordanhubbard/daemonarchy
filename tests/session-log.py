#!/usr/bin/env python3
"""Session-log framing, corruption and interrupted-update preservation."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
log=load('log',ROOT/'tools/boottrace/session-log.py')
fixtures=load('fixtures',ROOT/'tests/boot-medium.py')
PARENT=fixtures.session()[1]


class SessionLog(unittest.TestCase):
    def disk(self):
        disk=bytearray(b'\n'*log.FILE_SIZE)
        def read(off,n):return bytes(disk[off:off+n])
        def write(off,data):disk[off:off+len(data)]=data;return len(data)
        return disk,read,write

    def commit(self,disk,read,write,content,flush=lambda:None):
        return log.commit(read,write,flush,lambda:None,0,bytes(disk),PARENT,
                          'installer-events',content)

    def test_bounded_binary_roundtrip_and_explicit_truncation(self):
        for content in (b'',bytes(range(256))*2032):
            frame=log.encode(PARENT,'kernel-console',1,content,True)
            result=log.decode(frame,PARENT,'kernel-console')
            self.assertEqual(result['content'],content)
            self.assertTrue(result['metadata']['content_truncated'])
        with self.assertRaises(ValueError):
            log.encode(PARENT,'kernel-console',1,b'x'*(log.CONTENT_LIMIT+1))

    def test_three_updates_rotate_without_overwriting_latest_frame(self):
        disk,read,write=self.disk()
        self.commit(disk,read,write,b'start\n')
        first=bytes(disk[:log.FRAME_SIZE])
        self.commit(disk,read,write,b'start\nextract\n')
        self.assertEqual(disk[:log.FRAME_SIZE],first)
        second=bytes(disk[log.FRAME_SIZE:])
        result=self.commit(disk,read,write,b'start\nextract\ncompleted\n')
        self.assertEqual(result['sequence'],3)
        self.assertEqual(disk[log.FRAME_SIZE:],second)
        frames,latest=log.inspect(bytes(disk),PARENT,'installer-events')
        self.assertEqual(frames[latest]['content'],b'start\nextract\ncompleted\n')

    def test_torn_payload_preserves_latest_and_failed_frame(self):
        disk,read,write=self.disk();self.commit(disk,read,write,b'first')
        first=bytes(disk[:log.FRAME_SIZE])
        def partial(off,data):write(off,data[:512]);return 512
        with self.assertRaises(OSError):self.commit(disk,read,partial,b'second')
        frames,latest=log.inspect(bytes(disk),PARENT,'installer-events')
        self.assertEqual(latest,0);self.assertEqual(frames[1]['status'],'unreadable')
        self.assertEqual(bytes(disk[:log.FRAME_SIZE]),first)
        failed=bytes(disk)
        with self.assertRaises(ValueError):self.commit(disk,read,write,b'third')
        self.assertEqual(bytes(disk),failed)

    def test_torn_header_and_flush_failures_keep_previous_frame(self):
        for fault in ('header','payload-flush','header-flush'):
            disk,read,write=self.disk();self.commit(disk,read,write,b'first')
            first=bytes(disk[:log.FRAME_SIZE]);writes=0;flushes=0
            def faulty_write(off,data):
                nonlocal writes
                writes+=1
                if fault=='header' and writes==2:
                    write(off,data[:128]);return 128
                return write(off,data)
            def flush():
                nonlocal flushes
                flushes+=1
                if fault=='payload-flush' and flushes==1 or fault=='header-flush' and flushes==2:
                    raise OSError('simulated cache failure')
            with self.subTest(fault=fault),self.assertRaises(OSError):
                self.commit(disk,read,faulty_write,b'second',flush)
            self.assertEqual(bytes(disk[:log.FRAME_SIZE]),first)
            self.assertEqual(log.decode(first,PARENT,'installer-events')['content'],b'first')

    def test_header_payload_padding_and_foreign_identity_corruption(self):
        frame=log.encode(PARENT,'kernel-console',1,b'kernel')
        for at in (0,60,log.HEADER_SIZE,log.FRAME_SIZE-1):
            changed=bytearray(frame);changed[at]^=1
            with self.subTest(at=at),self.assertRaises(ValueError):
                log.decode(bytes(changed),PARENT,'kernel-console')
        foreign=dict(PARENT,boot_nonce=bytes(reversed(range(32))).hex())
        disk,read,write=self.disk();disk[:log.FRAME_SIZE]=frame
        with self.assertRaises(ValueError):
            log.commit(read,write,lambda:None,lambda:None,0,bytes(disk),foreign,'kernel-console',b'foreign')
        self.assertEqual(disk[:log.FRAME_SIZE],frame)

    def test_first_interruption_can_use_other_empty_frame_without_erasing_failure(self):
        disk,read,write=self.disk()
        def partial(off,data):write(off,data[:512]);return 512
        with self.assertRaises(OSError):self.commit(disk,read,partial,b'attempt')
        first=bytes(disk[:log.FRAME_SIZE])
        result=self.commit(disk,read,write,b'recovered')
        self.assertEqual(result['frame'],1)
        self.assertEqual(disk[:log.FRAME_SIZE],first)

    def test_stale_snapshot_idempotency_and_sequence_exhaustion(self):
        disk,read,write=self.disk();self.commit(disk,read,write,b'first')
        original=bytes(disk)
        def unexpected(*args):self.fail('idempotent commit attempted a write')
        result=self.commit(disk,read,unexpected,b'first')
        self.assertEqual(result['writes_performed'],0)
        disk[-1]^=1
        with self.assertRaises(ValueError):
            log.commit(read,write,lambda:None,lambda:None,0,original,PARENT,'installer-events',b'new')
        disk[:]=log.encode(PARENT,'installer-events',0xffffffff,b'last')+b'\n'*log.FRAME_SIZE
        with self.assertRaises(ValueError):self.commit(disk,read,unexpected,b'overflow')

    def test_ambiguous_sequence_and_invalid_file_length_refused(self):
        frame=log.encode(PARENT,'installer-events',1,b'a')
        with self.assertRaises(ValueError):log.inspect(frame+frame,PARENT,'installer-events')
        with self.assertRaises(ValueError):log.inspect(frame,PARENT,'installer-events')


if __name__=='__main__':unittest.main()
