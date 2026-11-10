#!/usr/bin/env python3
"""Read-only boot-medium correlation and refusal controls; no device access."""
import copy
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('medium', ROOT / 'tools/boottrace/boot-medium.py')
medium = importlib.util.module_from_spec(spec); spec.loader.exec_module(medium)
GUID = 'fedcba98-7654-3210-fedc-ba9876543210'


def fixture():
    return ET.fromstring(f'''<mesh>
<class id="1"><name>PART</name><geom id="2"><class ref="1"/><name>vtbd0</name>
<config><scheme>GPT</scheme><modified>false</modified><state>OK</state>
<entries>128</entries><first>34</first><last>2097118</last></config>
<consumer id="3"><geom ref="2"/><provider ref="7"/></consumer>
<provider id="4"><geom ref="2"/><name>vtbd0p3</name><mediasize>268435456</mediasize>
<sectorsize>512</sectorsize><config><start>2048</start><end>526335</end><index>3</index>
<offset>1048576</offset><length>268435456</length><type>ms-basic-data</type>
<label>DATRACE</label><rawtype>{medium.BASIC_DATA}</rawtype><rawuuid>{GUID}</rawuuid>
</config></provider></geom></class>
<class id="5"><name>DISK</name><geom id="6"><class ref="5"/><name>vtbd0</name>
<provider id="7"><geom ref="6"/><name>vtbd0</name><mediasize>1073741824</mediasize>
<sectorsize>512</sectorsize><config/></provider></geom></class></mesh>''')


def add_iso_alias(mesh):
    original = mesh.find('class/geom')
    alias = copy.deepcopy(original)
    mapping = {'2':'102', '3':'103', '4':'104'}
    for node in alias.iter():
        for attribute in ('id', 'ref'):
            if node.get(attribute) in mapping:
                node.set(attribute, mapping[node.get(attribute)])
    alias.find('name').text = 'iso9660/MEDIA'
    alias.find('consumer/provider').set('ref', '10')
    alias.find('provider/name').text = 'iso9660/MEDIAp3'
    mesh.find('class').append(alias)
    mesh.append(ET.fromstring("""<class id="8"><name>LABEL</name>
<geom id="9"><class ref="8"/><name>vtbd0</name>
<consumer id="11"><geom ref="9"/><provider ref="7"/></consumer>
<provider id="10"><geom ref="9"/><name>iso9660/MEDIA</name>
<mediasize>1073741824</mediasize><sectorsize>512</sectorsize>
<config><offset>0</offset><length>1073741824</length><secoffset>0</secoffset>
<seclength>2097152</seclength></config></provider></geom></class>"""))
    return mesh


def encode(mesh):
    return ET.tostring(mesh)


def session():
    record = dict(schema='daemonarchy/normal-boot-trace@4', phase='loader-ready',
                  image_id='01234567-89ab-cdef-0123-456789abcdef', archive_sha256='ab'*32,
                  trace_partition=GUID, session='0001', boot_nonce=bytes(range(32)).hex(),
                  boot_identity='firmware-rng', identity='declared-archive',
                  early_kernel_backend='not-enabled')
    later = dict(record, phase='pre-exit')
    record['pre_exit'] = dict(status='recorded', record=later)
    kenv = {'daemonarchy.trace.partition': GUID,
            'daemonarchy.trace.session': record['image_id']+'-0001',
            'daemonarchy.trace.boot_nonce': record['boot_nonce'],
            'daemonarchy.trace.capture': 'saved'}
    return kenv, record


class BootMedium(unittest.TestCase):
    def test_identical_iso_alias_is_one_canonical_physical_partition(self):
        value = medium.resolve_partition(encode(add_iso_alias(fixture())), GUID)
        self.assertEqual(value['device'], '/dev/vtbd0p3')
        self.assertEqual(value['equivalent_aliases'], 1)
        self.assertFalse(value['writes_admitted'])

    def test_shifted_truncated_or_cyclic_alias_cannot_hide_a_duplicate_uuid(self):
        for fault in ('offset', 'length', 'cycle', 'range'):
            mesh = add_iso_alias(fixture())
            label = mesh.findall('class')[-1].find('geom')
            if fault == 'offset': label.find('provider/config/offset').text = '512'
            if fault == 'length': label.find('provider/mediasize').text = '1073741312'
            if fault == 'cycle': label.find('consumer/provider').set('ref', '10')
            if fault == 'range':
                mesh.findall('class')[0].findall('geom')[1].find('provider/config/start').text = '2049'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                medium.resolve_partition(encode(mesh), GUID)

    def test_exact_geometry_selection_never_admits_device_writes(self):
        data = encode(fixture())
        for snapshot in (data, data+b'\0'):
            value = medium.resolve_partition(snapshot, GUID)
            self.assertEqual(value['device'], '/dev/vtbd0p3')
            self.assertEqual(value['disk'], '/dev/vtbd0')
            self.assertEqual((value['start_lba'], value['sectors']), (2048, 524288))
            self.assertTrue(value['read_only'])
            self.assertFalse(value['writes_admitted'])
            self.assertTrue(value['raw_gpt_and_fat_validation_required'])

    def test_malformed_oversized_entity_and_unknown_uuid_refused(self):
        for data in (b'', b'<mesh>', b'x'*(medium.MAX_XML+1),
                     encode(fixture())+b'\0\0',
                     b'<!DOCTYPE mesh [<!ENTITY x SYSTEM "file:///etc/passwd">]><mesh>&x;</mesh>'):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                medium.resolve_partition(data, GUID)
        for value in ('unknown', GUID.upper(), '00000000-0000-0000-0000-000000000000',
                      'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'):
            with self.subTest(uuid=value), self.assertRaises(ValueError):
                medium.resolve_partition(encode(fixture()), value)

    def test_duplicate_partition_on_another_disk_is_not_a_label_selection(self):
        mesh = fixture()
        for klass in list(mesh):
            geom = copy.deepcopy(klass.find('geom'))
            mapping = {'2':'102', '3':'103', '4':'104', '6':'106', '7':'107'}
            for node in geom.iter():
                for attribute in ('id', 'ref'):
                    if node.get(attribute) in mapping:
                        node.set(attribute, mapping[node.get(attribute)])
                if node.tag == 'name' and node.text and node.text.startswith('vtbd0'):
                    node.text = node.text.replace('vtbd0', 'vtbd1')
            klass.append(geom)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            medium.resolve_partition(encode(mesh), GUID)
        # Even a noncanonical foreign copy cannot hide the duplicate identity.
        mesh.findall('class/geom/provider/config/rawuuid')[-1].text = GUID.upper()
        with self.assertRaises(ValueError):
            medium.resolve_partition(encode(mesh), GUID)

    def test_missing_duplicate_or_dangling_graph_identifiers_refused(self):
        for fault in ('provider-id', 'duplicate-id', 'dangling', 'owner'):
            mesh = fixture()
            if fault == 'provider-id': del mesh.find('class/geom/provider').attrib['id']
            if fault == 'duplicate-id': mesh.find('class/geom/provider').set('id', '2')
            if fault == 'dangling': mesh.find('class/geom/consumer/provider').set('ref', 'missing')
            if fault == 'owner': mesh.find('class/geom/provider/geom').set('ref', '6')
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                medium.resolve_partition(encode(mesh), GUID)

    def test_foreign_types_names_and_inconsistent_geometry_refused(self):
        faults = {
            'class/geom/config/scheme': 'MBR',
            'class/geom/config/modified': 'true',
            'class/geom/config/state': 'unknown',
            'class/geom/config/entries': '0',
            'class/geom/provider/config/rawtype': 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b',
            'class/geom/provider/config/type': 'efi',
            'class/geom/provider/config/label': 'OTHER',
            'class/geom/provider/name': '../vtbd0p3',
            'class/geom/provider/config/index': '4',
            'class/geom/provider/config/offset': '0',
            'class/geom/provider/config/length': '1',
            'class/geom/provider/config/end': '2097152',
            'class/geom/provider/config/start': str(2**64),
            'class/geom/provider/mediasize': '1',
            'class/geom/provider/sectorsize': '4096'}
        for path, value in faults.items():
            mesh = fixture(); mesh.find(path).text = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                medium.resolve_partition(encode(mesh), GUID)
        mesh = fixture(); mesh.findall('class')[1].find('name').text = 'MD'
        with self.assertRaisesRegex(ValueError, 'DISK'):
            medium.resolve_partition(encode(mesh), GUID)

    def test_corrupt_gpt_observation_is_not_write_admission(self):
        mesh = fixture(); mesh.find('class/geom/config/state').text = 'CORRUPT'
        value = medium.resolve_partition(encode(mesh), GUID)
        self.assertEqual(value['gpt_state'], 'CORRUPT')
        self.assertFalse(value['writes_admitted'])
        self.assertTrue(value['raw_gpt_and_fat_validation_required'])

    def test_full_v4_correlation_is_still_read_only(self):
        kenv, record = session()
        value = medium.bind_session(encode(fixture()), kenv, record)
        self.assertTrue(value['session_correlated'])
        self.assertFalse(value['writes_admitted'])
        self.assertNotIn('boot_nonce', value)
        self.assertEqual(len(value['boot_nonce_sha256']), 64)

    def test_foreign_kernel_values_or_incomplete_later_stage_refused(self):
        for key in session()[0]:
            kenv, record = session(); kenv[key] = 'foreign'
            with self.subTest(key=key), self.assertRaises(ValueError):
                medium.bind_session(encode(fixture()), kenv, record)
        for fault in ('absent', 'partial', 'nonce', 'version', 'phase'):
            kenv, record = session()
            if fault == 'absent': del record['pre_exit']
            if fault == 'partial': record['pre_exit']['status'] = 'unreadable'
            if fault == 'nonce': record['pre_exit']['record']['boot_nonce'] = bytes(range(1,33)).hex()
            if fault == 'version': record['pre_exit']['record']['schema'] = 'daemonarchy/normal-boot-trace@3'
            if fault == 'phase': record['pre_exit']['record']['phase'] = 'installer'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                medium.bind_session(encode(fixture()), kenv, record)

    def test_missing_entropy_and_legacy_records_cannot_be_fresh_correlations(self):
        for fault in ('legacy', 'unavailable', 'stuck', 'unknown-identity'):
            kenv, record = session()
            if fault == 'legacy': record['schema'] = 'daemonarchy/normal-boot-trace@3'
            if fault == 'unavailable': record['boot_nonce'] = 'unavailable'
            if fault == 'stuck': record['boot_nonce'] = '00'*32
            if fault == 'unknown-identity': record['identity'] = 'unknown'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                medium.bind_session(encode(fixture()), kenv, record)


if __name__ == '__main__':
    unittest.main()
