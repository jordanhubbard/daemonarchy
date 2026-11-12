#!/usr/bin/env python3
"""Checkpoint codec and torn-write preservation controls."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
capture=load('capture',ROOT/'tools/boottrace/capture-medium.py')
fixtures=load('fixtures',ROOT/'tests/boot-medium.py')
stick=capture.stick


def original():
    _,parent=fixtures.session()
    keys=('image_id','archive_sha256','trace_partition','session','phase',
          'identity','early_kernel_backend','boot_nonce','boot_identity')
    def stage(phase):
        record=dict(parent,phase=phase)
        body=('Daemonarchy normal boot trace v4\n'+''.join(k+'='+record[k]+'\n' for k in keys)).encode()
        return stick.padded(body+('sum=%08x\n'%stick.fnv1a(body)).encode(),4096)
    return stage('loader-ready')+stage('pre-exit')+b'\n'*8192


class Checkpoint(unittest.TestCase):
    def test_binary_content_and_explicit_truncation(self):
        for phase in capture.PHASES:
            for content in (b'',bytes(range(256))*8):
                bank=capture.encode_checkpoint(stick.normal_record(original()),phase,content,True)
                parsed=stick._normal_userspace_stage(bank,phase)
                self.assertEqual(int(parsed['content_bytes']),len(content))
                self.assertEqual(parsed['content_truncated'],'yes')

    def test_oversize_missing_entropy_or_legacy_parent_refused(self):
        parent=stick.normal_record(original())
        with self.assertRaises(ValueError):capture.encode_checkpoint(parent,'init-ready',b'x'*2049)
        for key,value in (('boot_nonce','unavailable'),('schema','daemonarchy/normal-boot-trace@3')):
            changed=dict(parent);changed[key]=value
            with self.assertRaises(ValueError):capture.encode_checkpoint(changed,'init-ready',b'ok')

    def setup_disk(self,phase='init-ready'):
        old=original();disk=bytearray(bytes(512)+old+bytes(512))
        bank=capture.encode_checkpoint(stick.normal_record(old),phase,b'observed\n')
        read=lambda off,n:bytes(disk[off:off+n])
        def write(off,data):
            disk[off:off+len(data)]=data;return len(data)
        return old,disk,bank,read,write

    def test_committed_and_idempotent_preserve_all_other_banks(self):
        for phase,(index,_) in capture.PHASES.items():
            old,disk,bank,read,write=self.setup_disk(phase)
            result=capture.commit_bank(read,write,lambda:None,lambda:None,512,old,index,bank)
            self.assertEqual(result['status'],'recorded')
            returned=read(512,16384)
            self.assertEqual(returned[:index*4096],old[:index*4096])
            self.assertEqual(returned[(index+1)*4096:],old[(index+1)*4096:])
            self.assertEqual(disk[:512]+disk[-512:],bytes(1024))
            def unexpected(*args):self.fail('idempotent retry attempted a write')
            result=capture.commit_bank(read,unexpected,lambda:None,lambda:None,512,returned,index,bank)
            self.assertEqual(result['writes_performed'],0)

    def test_partial_write_preserves_loader_and_refuses_automatic_replacement(self):
        old,disk,bank,read,write=self.setup_disk()
        def partial(off,data):
            disk[off:off+511]=data[:511];return 511
        with self.assertRaises(OSError):
            capture.commit_bank(read,partial,lambda:None,lambda:None,512,old,2,bank)
        returned=read(512,16384)
        decoded=stick.normal_record(returned)
        self.assertEqual(decoded['pre_exit']['status'],'recorded')
        self.assertEqual(decoded['init']['status'],'unreadable')
        self.assertEqual(returned[:8192],old[:8192])
        with self.assertRaisesRegex(ValueError,'already contains'):
            capture.commit_bank(read,write,lambda:None,lambda:None,512,returned,2,bank)

    def test_flush_failure_does_not_claim_durable_success(self):
        old,disk,bank,read,write=self.setup_disk()
        def flush():raise OSError('device cache flush failed')
        with self.assertRaises(OSError):
            capture.commit_bank(read,write,flush,lambda:None,512,old,2,bank)
        self.assertEqual(read(512,8192),old[:8192])

    def test_stale_parent_or_foreign_identity_refused_before_write(self):
        old,disk,bank,read,write=self.setup_disk()
        disk[512]^=1
        with self.assertRaises(ValueError):
            capture.commit_bank(read,write,lambda:None,lambda:None,512,old,2,bank)
        self.assertEqual(read(512+8192,4096),b'\n'*4096)
        parent=stick.normal_record(old);parent['boot_nonce']=bytes(reversed(range(32))).hex()
        foreign=capture.encode_checkpoint(parent,'init-ready',b'foreign')
        with self.assertRaises(ValueError):
            capture.commit_bank(read,write,lambda:None,lambda:None,512,old,2,foreign)

    def test_nonempty_evidence_and_readback_corruption_refused(self):
        old,disk,bank,read,write=self.setup_disk()
        def corrupt(off,data):
            count=write(off,data);disk[off+1]^=1;return count
        with self.assertRaisesRegex(ValueError,'readback'):
            capture.commit_bank(read,corrupt,lambda:None,lambda:None,512,old,2,bank)
        returned=read(512,16384)
        self.assertEqual(returned[:8192],old[:8192])
        with self.assertRaises(ValueError):
            capture.commit_bank(read,write,lambda:None,lambda:None,512,returned,2,bank)


if __name__=='__main__':unittest.main()
