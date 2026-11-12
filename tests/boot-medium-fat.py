#!/usr/bin/env python3
"""Independent FAT32 allocation fixtures and corruption controls."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec=importlib.util.spec_from_file_location('fat',Path(__file__).resolve().parents[1]/'tools/boottrace/fat-volume.py')
fat=importlib.util.module_from_spec(spec);spec.loader.exec_module(fat)
RESERVED,FATSZ,COUNT=32,513,65525
DATA=(RESERVED+2*FATSZ)*512
SIZE=DATA+COUNT*512


def fixture():
    image=bytearray(SIZE)
    boot=bytearray(512)
    struct.pack_into('<HBHB',boot,11,512,1,RESERVED,2)
    boot[21]=0xf8
    struct.pack_into('<IIHHIHH',boot,32,SIZE//512,FATSZ,0,0,2,1,2)
    boot[82:90]=b'FAT32   ';boot[510:512]=b'\x55\xaa'
    image[:512]=boot;image[1024:1536]=boot
    table=bytearray(FATSZ*512)
    struct.pack_into('<II',table,0,0x0ffffff8,0x0fffffff)
    next_cluster=2
    def allocate(clusters):
        nonlocal next_cluster
        first=next_cluster
        for c in range(first,first+clusters):
            struct.pack_into('<I',table,c*4,c+1 if c<first+clusters-1 else 0x0fffffff)
        next_cluster+=clusters
        return first
    root,traces,normal=allocate(1),allocate(13),allocate(3)
    files={}
    for name,size in [('STATE.TXT',512),('SLOTS.MAP',16384)]+[
        ('TRACES/%04d.TXT'%i,16384) for i in range(1,201)]+[
        ('NORMAL/%04d.TXT'%i,16384) for i in range(1,33)]:
        files[name]=(allocate(size//512),size)
    def offset(c):return DATA+(c-2)*512
    def entry(name,cluster,size,attr=32):
        e=bytearray(32);base,_,ext=name.partition('.')
        e[:11]=(base.ljust(8)+ext.ljust(3)).encode()
        e[11]=attr
        struct.pack_into('<H',e,20,cluster>>16)
        struct.pack_into('<HI',e,26,cluster&65535,size)
        return e
    roots=[entry('TRACES',traces,0,16),entry('NORMAL',normal,0,16)]
    roots += [entry(p,c,n) for p,(c,n) in files.items() if '/' not in p]
    image[offset(root):offset(root)+len(roots)*32]=b''.join(roots)
    for directory,cluster in [('TRACES',traces),('NORMAL',normal)]:
        entries=[entry(p.split('/')[1],c,n) for p,(c,n) in files.items() if p.startswith(directory+'/')]
        image[offset(cluster):offset(cluster)+len(entries)*32]=b''.join(entries)
    ordered=['STATE.TXT']+sorted(p for p in files if p.startswith('TRACES/'))+sorted(p for p in files if p.startswith('NORMAL/'))
    body='Daemonarchy DATRACE block map v1\npart_lba=0\npart_sectors=%d\ndata_off=%d\n'%(SIZE//512,DATA)
    body+=''.join('file=%s off=%d size=%d\n'%(p,offset(files[p][0]),files[p][1]) for p in ordered)
    checksum=2166136261
    for byte in body.encode():checksum=((checksum^byte)*16777619)&0xffffffff
    content=(body+'sum=%08x\n'%checksum).encode().ljust(16384,b'\n')
    mapoff=offset(files['SLOTS.MAP'][0]);image[mapoff:mapoff+16384]=content
    for i in range(2):image[(RESERVED+i*FATSZ)*512:(RESERVED+(i+1)*FATSZ)*512]=table
    return image,files,mapoff


def observe(image):
    return fat.validate_fat(lambda off,n:bytes(image[off:off+n]),dict(start_lba=0,sectors=len(image)//512))


def change_fat(image,cluster,value):
    for i in range(2):struct.pack_into('<I',image,(RESERVED+i*FATSZ)*512+cluster*4,value)


class Allocation(unittest.TestCase):
    def test_complete_independent_volume(self):
        result=observe(fixture()[0])
        self.assertEqual(result['mapped_files'],233)
        self.assertFalse(result['writes_admitted'])

    def test_boot_geometry_and_backup_disagreement(self):
        original=fixture()[0]
        for at in (11,13,16,32,40,44,50,82,1024+13):
            image=bytearray(original);image[at]^=1
            with self.subTest(at=at),self.assertRaises(ValueError):observe(image)

    def test_allocation_copy_disagreement(self):
        image,_,_=fixture();image[RESERVED*512+16]^=1
        with self.assertRaises(ValueError):observe(image)

    def test_cycles_crosslinks_bad_free_and_orphan_clusters(self):
        original,files,_=fixture()
        first=files['NORMAL/0001.TXT'][0]
        other=files['TRACES/0001.TXT'][0]
        for value in (first,other,0,0x0ffffff7,COUNT+2):
            image=bytearray(original);change_fat(image,first,value)
            with self.subTest(value=value),self.assertRaises(ValueError):observe(image)
        image=bytearray(original);change_fat(image,COUNT,0x0fffffff)
        with self.assertRaises(ValueError):observe(image)

    def test_short_allocation_and_noncontiguous_map_extent(self):
        original,files,_=fixture()
        first=files['NORMAL/0001.TXT'][0]
        image=bytearray(original);change_fat(image,first,0x0fffffff)
        with self.assertRaises(ValueError):observe(image)
        image=bytearray(original)
        change_fat(image,first,first+2)
        change_fat(image,first+2,first+1)
        change_fat(image,first+1,first+3)
        with self.assertRaisesRegex(ValueError,'contiguous'):observe(image)

    def test_map_corruption_and_duplicate_directory_names(self):
        image,_,mapoff=fixture();image[mapoff+100]^=1
        with self.assertRaises(ValueError):observe(image)
        image,_,_=fixture();image[DATA+32:DATA+64]=image[DATA:DATA+32]
        with self.assertRaises(ValueError):observe(image)

    def test_short_reads_and_partition_bound(self):
        with self.assertRaises(ValueError):
            fat.validate_fat(lambda off,n:bytes(n-1),dict(start_lba=0,sectors=SIZE//512))
        image=fixture()[0]
        with self.assertRaises(ValueError):
            fat.validate_fat(lambda off,n:bytes(image[off:off+n]),dict(start_lba=0,sectors=SIZE//512-1))


if __name__=='__main__':unittest.main()
