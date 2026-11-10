#!/usr/bin/env python3
"""Real-XZ release-record controls; these fixtures are not release artifacts."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_assets_split_test', ROOT / 'scripts/verify-release-assets.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)
media = assets.split_verifier()


def identity(data):
    return [len(data), 'sha256:' + hashlib.sha256(data).hexdigest()]


class SplitReleaseRecords(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.image = 'daemonarchy-1.6.0-amd64.iso.xz'
        source = self.root / self.image.removesuffix('.xz')
        raw = bytes(range(256)) * 5
        source.write_bytes(raw)
        self.directory = self.root / 'assets'
        packed = media.pack(source, hashlib.sha256(raw).hexdigest(), self.directory, 313)
        self.manifest = packed['manifest']
        self.record = {'schema': 'daemonarchy/release-inputs@1', 'version': '1.6.0', 'tag': 'daemonarchy-1.6.0',
                       'installer_commit': 'a' * 40, 'source_commit': 'b' * 40, 'osversion': 1600029,
                       'architectures': ['amd64'], 'assets': {}, 'image_transports': {self.image: {
                           'format': 'xz-parts@1', 'manifest': self.manifest,
                           'parts': [p['name'] for p in packed['parts']], 'raw_image': identity(raw)}}}
        for path in self.directory.iterdir():
            self.record['assets'][path.name] = identity(path.read_bytes())
        for suffix in ['boot.txz', 'boot.txz.sig', 'pem', 'der']:
            separator = '.' if suffix in ['pem', 'der'] else '-'
            self.asset('daemonarchy-1.6.0' + separator + suffix, b'not a certificate or signed bundle')
        self.closure = self.root / 'closure'
        tag = 'packages-16-amd64-1.6.0-development'
        shard = self.closure / tag
        shard.mkdir(parents=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:xz') as tar:
            entry = tarfile.TarInfo('catalog')
            entry.size = 3
            tar.addfile(entry, io.BytesIO(b'{}\n'))
        closure_assets = {}
        for name, data in [('meta.conf', b'fixture\n'), ('data.pkg', archive.getvalue()), ('fixture-1.pkg', b'fixture')]:
            (shard / name).write_bytes(data)
            closure_assets[name] = identity(data)
        self.record['closure_feeds'] = [{'tag': tag, 'assets': closure_assets}]
        self.path = self.root / 'release.json'
        self.save()

    def asset(self, name, data):
        (self.directory / name).write_bytes(data)
        self.record['assets'][name] = identity(data)

    def save(self):
        self.path.write_text(json.dumps(self.record) + '\n')

    def read(self):
        self.save()
        return assets.read_record(self.path)[0]

    def rejected_record(self):
        self.save()
        with self.assertRaises(ValueError):
            assets.read_record(self.path)

    def test_explicit_transport_and_complete_raw_identity(self):
        record = self.read()
        observed = assets.verify_split_image(record, self.directory, self.image)
        self.assertEqual(identity((self.root / self.image.removesuffix('.xz')).read_bytes()),
                         [observed['image']['bytes'], 'sha256:' + observed['image']['sha256']])
        self.assertNotIn(self.image, record['assets'])

    def test_no_implicit_split_fallback(self):
        del self.record['image_transports']
        self.rejected_record()

    def test_historical_releases_cannot_gain_split_semantics(self):
        self.record['version'] = '1.5.1'
        self.record['tag'] = 'daemonarchy-1.5.1'
        self.rejected_record()

    def test_monolithic_and_split_cannot_both_be_approved(self):
        self.asset(self.image, b'old monolithic bytes')
        self.asset(self.image + '.sha256', b'old checksum')
        self.rejected_record()

    def test_unknown_transport_format_or_field(self):
        transport = self.record['image_transports'][self.image]
        transport['format'] = 'arbitrary-format'
        self.rejected_record()
        transport['format'] = 'xz-parts@1'
        transport['skip_verification'] = True
        self.rejected_record()

    def test_foreign_logical_image(self):
        self.record['image_transports']['daemonarchy-1.6.0-mips.iso.xz'] = self.record['image_transports'].pop(self.image)
        self.rejected_record()

    def test_manifest_cannot_escape_image_family(self):
        self.record['image_transports'][self.image]['manifest'] = '../elsewhere.parts.json.xz'
        self.rejected_record()

    def test_part_order_duplicates_and_paths(self):
        transport = self.record['image_transports'][self.image]
        original = list(transport['parts'])
        for value in [original[::-1], original + [original[0]], ['../escape.xz']]:
            with self.subTest(value=value):
                transport['parts'] = value
                self.rejected_record()

    def test_raw_budget_and_boolean_sizes(self):
        for size in [assets.RAW_IMAGE_LIMIT, assets.RAW_IMAGE_LIMIT + 1, True, 0]:
            with self.subTest(size=size):
                self.record['image_transports'][self.image]['raw_image'][0] = size
                self.rejected_record()

    def test_public_asset_limit_is_exclusive(self):
        part = self.record['image_transports'][self.image]['parts'][0]
        self.record['assets'][part][0] = assets.PUBLIC_ASSET_LIMIT
        self.rejected_record()

    def test_manifest_budget(self):
        self.record['assets'][self.manifest][0] = (1 << 20) + 1
        self.rejected_record()

    def test_manifest_and_approved_raw_identity_must_agree(self):
        self.record['image_transports'][self.image]['raw_image'][1] = 'sha256:' + '0' * 64
        record = self.read()
        with self.assertRaisesRegex(ValueError, 'approved logical image'):
            assets.verify_split_image(record, self.directory, self.image)

    def test_manifest_and_approved_part_identity_must_agree(self):
        part = self.record['image_transports'][self.image]['parts'][0]
        self.record['assets'][part][1] = 'sha256:' + '0' * 64
        record = self.read()
        with self.assertRaisesRegex(ValueError, 'approved release asset'):
            assets.verify_split_image(record, self.directory, self.image)

    def test_manifest_may_not_enroll_unapproved_extra_parts(self):
        dropped = self.record['image_transports'][self.image]['parts'].pop()
        del self.record['assets'][dropped]
        record = self.read()
        with self.assertRaisesRegex(ValueError, 'approved logical image'):
            assets.verify_split_image(record, self.directory, self.image)

    def test_new_transport_does_not_skip_real_certificate_validation(self):
        self.read()
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            assets.verify(self.path, self.directory, self.closure)
        self.assertEqual(caught.exception.cmd[:2], ['openssl', 'x509'])

    def test_private_certificate_material_is_still_refused(self):
        self.asset('daemonarchy-1.6.0.pem', b'-----BEGIN PRIVATE KEY-----')
        self.read()
        with self.assertRaisesRegex(ValueError, 'private material'):
            assets.verify(self.path, self.directory, self.closure)

    def test_closure_gate_is_still_required(self):
        self.read()
        with self.assertRaisesRegex(ValueError, 'closure-assets'):
            assets.verify(self.path, self.directory)

    def test_publication_verifier_pages_all_split_assets_and_rejects_extra(self):
        # Metadata-only control; staged byte/signature checks have separate tests.
        record = {"tag": "daemonarchy-1.6.0", "installer_commit": "a" * 40,
                  "assets": {f"fixture-{n}": [n + 1, "sha256:" + "b" * 64] for n in range(105)}}
        listing = [{"name": n, "size": v[0], "digest": v[1]} for n, v in record["assets"].items()]
        release = {"id": 7, "tag_name": record["tag"], "draft": False, "prerelease": False,
                   "target_commitish": record["installer_commit"], "assets": listing[:100]}
        seen = []

        def github(path):
            seen.append(path)
            if path.startswith("releases/7/assets?"):
                page = int(path.rsplit("=", 1)[1])
                return listing[(page - 1) * 100:page * 100]
            if path.startswith("git/ref/"):
                return {"object": {"type": "commit", "sha": record["installer_commit"]}}
            return release

        with patch.object(assets, "github", side_effect=github), patch.object(assets, "verify_published_closure"):
            assets.verify_published(record)
            self.assertIn("releases/7/assets?per_page=100&page=2", seen)
            listing.append({"name": "unapproved-extra", "size": 1, "digest": "sha256:" + "c" * 64})
            with self.assertRaises(ValueError):
                assets.verify_published(record)


if __name__ == '__main__':
    unittest.main(verbosity=2)
