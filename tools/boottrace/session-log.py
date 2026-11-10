#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Two-frame bounded session logs; preserve the last durable frame on interruption."""
import hashlib
import importlib.util
import json
from pathlib import Path

FILE_SIZE = 1024 * 1024
FRAME_SIZE = FILE_SIZE // 2
HEADER_SIZE = 4096
CONTENT_LIMIT = FRAME_SIZE - HEADER_SIZE
TAG = b'Daemonarchy userspace session log v1\n'
KINDS = ('kernel-console', 'installer-events')
spec = importlib.util.spec_from_file_location('log_medium',Path(__file__).with_name('boot-medium.py'))
medium = importlib.util.module_from_spec(spec)
spec.loader.exec_module(medium)


class ForeignLog(ValueError):
    pass


def checksum(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return value


def canonical(metadata):
    return json.dumps(metadata,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')


def metadata(parent,kind,sequence,content,truncated):
    if (kind not in KINDS or type(sequence) is not int or not 1 <= sequence <= 0xffffffff or
            type(content) is not bytes or len(content)>CONTENT_LIMIT or type(truncated) is not bool):
        raise ValueError('bounded session log metadata required')
    return dict(medium.identity(parent),kind=kind,sequence=sequence,
                content_bytes=len(content),content_sha256=hashlib.sha256(content).hexdigest(),
                content_truncated=truncated)


def encode(parent,kind,sequence,content,truncated=False):
    info = metadata(parent,kind,sequence,content,truncated)
    body = TAG + canonical(info) + b'\n'
    header = body + ('sum=%08x\n'%checksum(body)).encode()
    if len(header)>HEADER_SIZE:
        raise ValueError('session log header budget exceeded')
    return header.ljust(HEADER_SIZE,b'\n') + content.ljust(CONTENT_LIMIT,b'\n')


def decode(frame,parent,kind):
    if len(frame)!=FRAME_SIZE:
        raise ValueError('wrong session log frame size')
    header = frame[:HEADER_SIZE].rstrip(b'\n')
    lines = header.split(b'\n')
    if len(lines)!=3 or lines[0]+b'\n'!=TAG:
        raise ValueError('incomplete session log header')
    body = lines[0]+b'\n'+lines[1]+b'\n'
    if lines[2] != ('sum=%08x'%checksum(body)).encode():
        raise ValueError('session log header checksum mismatch')
    if lines[1].count(b'{')!=1 or lines[1].count(b'}')!=1 or b'[' in lines[1]:
        raise ValueError('session log metadata must be flat')
    try:
        info=json.loads(lines[1])
    except (ValueError,UnicodeError) as error:
        raise ValueError('invalid session log metadata') from error
    if not isinstance(info,dict) or canonical(info)!=lines[1]:
        raise ValueError('noncanonical session log metadata')
    count=info.get('content_bytes')
    if type(count) is not int or not 0<=count<=CONTENT_LIMIT:
        raise ValueError('invalid session log content length')
    content=frame[HEADER_SIZE:HEADER_SIZE+count]
    intrinsic=dict(info,identity='declared-archive',early_kernel_backend='not-enabled')
    expected=metadata(intrinsic,info.get('kind'),info.get('sequence'),content,info.get('content_truncated'))
    if info!=expected or frame[HEADER_SIZE+count:]!=b'\n'*(CONTENT_LIMIT-count):
        raise ValueError('session log content identity mismatch')
    if medium.identity(parent)!=medium.identity(intrinsic) or kind!=info['kind']:
        raise ForeignLog('foreign session log identity or kind')
    return dict(status='recorded',metadata=info,content=content)


def inspect(data,parent,kind):
    if len(data)!=FILE_SIZE:
        raise ValueError('wrong session log file size')
    frames=[]
    for index in range(2):
        frame=data[index*FRAME_SIZE:(index+1)*FRAME_SIZE]
        if frame==b'\n'*FRAME_SIZE:
            frames.append(dict(status='empty'))
        else:
            try:
                frames.append(decode(frame,parent,kind))
            except ForeignLog as error:
                frames.append(dict(status='foreign',reason=str(error),
                                   raw_sha256=hashlib.sha256(frame).hexdigest()))
            except (ValueError,UnicodeError) as error:
                frames.append(dict(status='unreadable',reason=str(error),
                                   raw_sha256=hashlib.sha256(frame).hexdigest()))
    recorded=[i for i,f in enumerate(frames) if f['status']=='recorded']
    if len(recorded)==2 and frames[0]['metadata']['sequence']==frames[1]['metadata']['sequence']:
        raise ValueError('ambiguous session log sequence')
    latest=max(recorded,key=lambda i:frames[i]['metadata']['sequence']) if recorded else None
    return frames,latest


def commit(read,write,flush,guard,offset,original,parent,kind,content,truncated=False):
    """Commit payload then header in an inactive frame; never overwrite latest."""
    if type(offset) is not int or offset<0 or offset%512:
        raise ValueError('unaligned session log extent')
    frames,latest=inspect(original,parent,kind)
    if any(frame['status']=='foreign' for frame in frames):
        raise ValueError('foreign session log retained; writes refused')
    sequence=frames[latest]['metadata']['sequence'] if latest is not None else 0
    requested=metadata(parent,kind,max(sequence,1),content,truncated)
    if latest is not None and requested==frames[latest]['metadata']:
        guard()
        if read(offset,FILE_SIZE)!=original:
            raise ValueError('session log changed before retry')
        flush()
        if read(offset,FILE_SIZE)!=original:
            raise ValueError('session log retry readback mismatch')
        guard()
        return dict(status='already-recorded',sequence=sequence,writes_performed=0)
    candidates=[1-latest] if latest is not None else [i for i,f in enumerate(frames) if f['status']=='empty']
    if not candidates or frames[candidates[0]]['status']=='unreadable':
        raise ValueError('incomplete session log frame retained; no writable frame')
    target=candidates[0]
    encoded=encode(parent,kind,sequence+1,content,truncated)
    start=target*FRAME_SIZE
    guard()
    if read(offset,FILE_SIZE)!=original:
        raise ValueError('session log changed before commit')
    if write(offset+start+HEADER_SIZE,encoded[HEADER_SIZE:])!=CONTENT_LIMIT:
        raise OSError('partial session log payload; earlier frame retained')
    flush()
    after_payload=original[:start+HEADER_SIZE]+encoded[HEADER_SIZE:]+original[start+FRAME_SIZE:]
    if read(offset,FILE_SIZE)!=after_payload:
        raise ValueError('session log payload readback mismatch')
    guard()
    if write(offset+start,encoded[:HEADER_SIZE])!=HEADER_SIZE:
        raise OSError('partial session log header; earlier frame retained')
    flush()
    expected=original[:start]+encoded+original[start+FRAME_SIZE:]
    returned=read(offset,FILE_SIZE)
    if returned!=expected:
        raise ValueError('session log commit readback mismatch')
    observed,current=inspect(returned,parent,kind)
    if current!=target or observed[current]['metadata']['sequence']!=sequence+1:
        raise ValueError('session log durable sequence mismatch')
    guard()
    return dict(status='recorded',sequence=sequence+1,writes_performed=2,
                content_bytes=len(content),content_sha256=hashlib.sha256(content).hexdigest(),
                content_truncated=truncated,frame=target)


def main():
    import argparse
    import stat
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('normal_slot',type=Path)
    parser.add_argument('log_file',type=Path)
    parser.add_argument('--kind',choices=KINDS,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        for path,size in ((args.normal_slot,16384),(args.log_file,FILE_SIZE)):
            if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size!=size:
                raise ValueError('fixed-size regular input required')
        s=importlib.util.spec_from_file_location('log_stick',Path(__file__).with_name('stick.py'))
        stick=importlib.util.module_from_spec(s);s.loader.exec_module(stick)
        with args.normal_slot.open('rb') as source:
            parent=stick.normal_record(source.read(16385))
        with args.log_file.open('rb') as source:
            frames,latest=inspect(source.read(FILE_SIZE+1),parent,args.kind)
        if latest is None:
            raise ValueError('no complete correlated session log frame')
        with args.out.open('xb') as output:
            output.write(frames[latest]['content'])
        print(json.dumps(dict(metadata=frames[latest]['metadata'],
                              frame_states=[f['status'] for f in frames],
                              volume_modified=False),sort_keys=True))
    except (ValueError,OSError,UnicodeError) as error:
        parser.exit(1,'session-log: '+str(error)+'\n')


if __name__=='__main__':
    main()
