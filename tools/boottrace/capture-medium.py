#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Commit one bounded v4 userspace checkpoint without replacing prior evidence."""
import argparse
import base64
import hashlib
import json
import os
import subprocess

# Reuse the observer's native admission and legacy-compatible decoder.
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('native_observer',Path(__file__).with_name('observe-medium.py'))
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
stick, medium = observer.stick, observer.medium
session_log = observer.module('session_log','session-log.py')
evidence = observer.module('installer_evidence','installer-evidence.py')
DIOCGFLUSH = 0x20006487
PHASES = {'init-ready': (2,'kernel-console'), 'installer': (3,'installer-events')}


def encode_checkpoint(parent, phase, content, truncated=False):
    if phase not in PHASES or type(content) is not bytes or len(content)>2048 or type(truncated) is not bool:
        raise ValueError('bounded checkpoint phase/content required')
    if parent.get('schema') != 'daemonarchy/normal-boot-trace@4':
        raise ValueError('v4 checkpoint parent required')
    medium.identity(parent)
    values = dict(parent,phase=phase)
    keys = ('image_id','archive_sha256','trace_partition','session','phase',
            'identity','early_kernel_backend','boot_nonce','boot_identity')
    body = 'Daemonarchy normal boot trace v4\n'
    body += ''.join(key+'='+values[key]+'\n' for key in keys)
    body += 'content_kind='+PHASES[phase][1]+'\n'
    body += 'content_bytes='+str(len(content))+'\n'
    body += 'content_sha256='+hashlib.sha256(content).hexdigest()+'\n'
    body += 'content_truncated='+('yes' if truncated else 'no')+'\n'
    body += 'content_base64='+base64.b64encode(content).decode('ascii')+'\n'
    data=body.encode('ascii')
    return stick.padded(data+('sum=%08x\n'%stick.fnv1a(data)).encode(),4096)


def commit_bank(read, write, flush, guard, slot_offset, original, index, bank):
    """One bank write; a torn attempt is retained, never automatically replaced."""
    if index not in (2,3) or len(original)!=16384 or len(bank)!=4096 or slot_offset%512:
        raise ValueError('invalid bank write extent')
    phase = 'init-ready' if index==2 else 'installer'
    child = stick._normal_userspace_stage(bank,phase)
    parent = stick.normal_record(original)
    if medium.identity(child)!=medium.identity(parent):
        raise ValueError('checkpoint parent identity mismatch')
    start,end=index*4096,(index+1)*4096
    previous=original[start:end]
    if previous!=bank and previous!=b'\n'*4096:
        raise ValueError('checkpoint bank already contains evidence')
    guard()
    if read(slot_offset,16384)!=original:
        raise ValueError('normal slot changed before checkpoint commit')
    if previous==bank:
        flush()
        if read(slot_offset,16384)!=original:
            raise ValueError('existing checkpoint readback mismatch')
        guard()
        return dict(status='already-recorded',writes_performed=0)
    count=write(slot_offset+start,bank)
    if count!=4096:
        raise OSError('partial checkpoint write; incomplete bank retained')
    flush()
    returned=read(slot_offset,16384)
    if returned[:start]!=original[:start] or returned[end:]!=original[end:]:
        raise ValueError('protected normal banks changed during checkpoint commit')
    if returned[start:end]!=bank:
        raise ValueError('checkpoint readback mismatch')
    decoded=stick.normal_record(returned)
    if decoded['init' if index==2 else 'installer']['status']!='recorded':
        raise ValueError('checkpoint decoder refused durable readback')
    guard()
    return dict(status='recorded',writes_performed=1,bank_bytes=4096,
                bank_sha256=hashlib.sha256(bank).hexdigest())


def capture(phase, content, truncated=False, structured=False):
    if phase not in PHASES or type(content) is not bytes:
        raise ValueError('bounded checkpoint phase/content required')
    with observer.open_medium(writable=True) as state:
        def flush():
            os.fsync(state['fd'])
            observer.fcntl.ioctl(state['fd'],DIOCGFLUSH)
        write=lambda off,data:observer.bounded_write(state['fd'],off-state['write_base'],data)
        extents=state['result']['filesystem'].get('log_extents')
        full=None
        if extents is not None:
            kind=PHASES[phase][1]
            relative,size=extents[kind]
            if size!=session_log.FILE_SIZE:
                raise ValueError('wrong userspace log extent size')
            offset=state['write_base']+relative
            original=state['read'](offset,size)
            frames,latest=session_log.inspect(original,state['record'],kind)
            full_content=content[:session_log.CONTENT_LIMIT]
            full_truncated=truncated or len(content)>session_log.CONTENT_LIMIT
            if phase=='installer' and latest is not None:
                previous=frames[latest]['content']
                full_content=(evidence.append_batch(previous,content) if structured else
                              previous if previous.endswith(content) else previous+content)
                full_truncated=truncated or frames[latest]['metadata']['content_truncated']
                if len(full_content)>session_log.CONTENT_LIMIT:
                    raise ValueError('installer log full; previous progress retained')
            elif phase=='installer' and structured:
                full_content=evidence.append_batch(b'',content)
            full=session_log.commit(state['read'],write,flush,state['guard'],offset,
                                    original,state['record'],kind,full_content,full_truncated)
        bank=encode_checkpoint(state['record'],phase,content[:2048],truncated or len(content)>2048)
        index=PHASES[phase][0]
        if full is not None and state['slot'][index*4096:(index+1)*4096] not in (b'\n'*4096,bank):
            name='init' if phase=='init-ready' else 'installer'
            committed=dict(status='preserved',writes_performed=0,
                           previous_bank_status=state['record'][name]['status'])
        else:
            committed=commit_bank(state['read'],write,flush,state['guard'],
                                  state['slot_offset'],state['slot'],index,bank)
        result=dict(schema='daemonarchy/native-userspace-checkpoint@1',
                    phase=phase,session=state['result']['selection']['session'],
                    boot_nonce_sha256=state['result']['selection']['boot_nonce_sha256'],
                    content_bytes=min(len(content),2048),
                    content_truncated=truncated or len(content)>2048,
                    writes_admitted=True,full_log_retention=full is not None,**committed)
        if full is not None:
            result['bounded_log']=full
            result['bounded_log_limit']=session_log.CONTENT_LIMIT
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=PHASES)
    source=parser.add_mutually_exclusive_group()
    source.add_argument('--event',choices=('started','completed','failed'))
    source.add_argument('--events-file',type=Path)
    args=parser.parse_args()
    try:
        readiness=None
        if args.phase=='init-ready':
            if args.event is not None or args.events_file is not None:
                raise ValueError('installer event is not kernel-console content')
            readiness=observer.wait_for_partition()
            content=observer.command(['/sbin/dmesg'])
            truncated=False
        else:
            if args.event is None and args.events_file is None:
                raise ValueError('explicit sanitized installer event required')
            content=(evidence.batch(args.events_file) if args.events_file is not None else
                     ('installer='+args.event+'\n').encode())
            truncated=False
        result=capture(args.phase,content,truncated,structured=args.events_file is not None)
        if readiness is not None:
            result['boot_medium_readiness']=readiness
    except (ValueError,OSError,UnicodeError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='unavailable',writes_admitted=False,reason=str(error))))
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
