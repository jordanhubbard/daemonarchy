#!/usr/bin/env python3
"""Real-codec and local transport controls; fake SSH/QEMU/device boundaries, no native qualification."""
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codec = load("master_test_codec", ROOT / "scripts/split-media.py")
master = load("master_media_test", ROOT / "scripts/master-media.py")


class MasterSplit(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="master split's ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.product = self.work / ("product-" + COMMIT[:12])
        self.product.mkdir()
        (self.product / "VERSION").write_text("1.6.0\n")
        (self.work / "evidence").mkdir()
        (self.product / "tests").mkdir()
        (self.product / "tests/qemu-desktop.py").write_text("# fixture only\n")
        (self.product / "test-qemu.sh").write_text("""#!/bin/sh
set -eu
python3 - "$1" <<'CONTROL_ONLY'
import hashlib, json, os, pathlib, sys
image = pathlib.Path(sys.argv[1])
assert hashlib.sha256(image.read_bytes()).hexdigest() == os.environ['CONTROL_RAW_SHA256']
assert os.environ['ARCH'] == os.environ['CONTROL_QA_ARCH']
assert pathlib.Path(os.environ['POST_INSTALL_CHECK']).is_file()
pathlib.Path(os.environ['CONTROL_QA_RECEIPT']).write_text(json.dumps({'image':str(image), 'arch':os.environ['ARCH'], 'feed':os.environ['EXPECTED_PACKAGE_REPOSITORY_TAG']}))
CONTROL_ONLY
""")
        self.script("ssh", """#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
with open(os.environ['CONTROL_SSH_LOG'], 'a') as stream: stream.write(json.dumps(sys.argv[1:]) + chr(10))
command = sys.argv[2]
if command.startswith('sh -s -- ') and os.environ.get('CONTROL_CORRUPT_TRANSFER'):
    for part in pathlib.Path(os.environ['CONTROL_QA_PARENT']).glob('qa.split.*/*.part0001.xz'):
        part.write_bytes(b'corrupt transferred bytes')
raise SystemExit(subprocess.run(command, shell=True).returncode)
""")
        self.script("bsdtar", "#!/bin/sh\nexec tar \"$@\"\n")
        self.script("lsblk", "#!/bin/sh\necho 'sdzzb 8000000000 usb TEST disk'\n")
        self.script("sudo", "#!/bin/sh\necho unsafe-device-dispatch >>\"$CONTROL_DEVICE_LOG\"\nexit 97\n")
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        WORK=str(self.work), MAIN_COMMIT=COMMIT, RELEASE="1.6.0", ARCH="aarch64",
                        QA_HOST="fixture.invalid", QA_USER="fixture", QA_DIR=str(self.root / 'qa'),
                        PACKAGE_REPOSITORY_TAG="packages-16-aarch64-1.6.0", LSBLK=str(self.bin / 'lsblk'),
                        CONTROL_SSH_LOG=str(self.root / 'ssh.log'), CONTROL_QA_RECEIPT=str(self.root / 'qa-receipt.json'),
                        CONTROL_DEVICE_LOG=str(self.root / 'device.log'), CONTROL_QA_PARENT=str(self.root))
        self.select("aarch64")

    def script(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def select(self, arch):
        self.image = f"daemonarchy-1.6.0-{arch}.iso"
        source = self.root / self.image
        with tarfile.open(source, 'w') as archive:
            for name, data in [("./usr/local/share/daemonarchy-installer/version", b"1.6.0\n"),
                               ("./usr/local/lib/python3.12/lib-dynload/_sqlite3.so", b"fixture"),
                               ("boot/kernel/kernel", b"selected kernel"), ("boot/loader.efi", b"selected loader"),
                               ("boot/loader_lua.efi", b"selected loader"), ("boot/lua/retained.lua", b"retained"),
                               ("boot/lua/brand-daemonarchy.lua", b"brand"), ("boot/lua/local.lua", b"local")]:
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
        self.raw = source.read_bytes()
        directory = self.root / ('parts-' + arch)
        self.packed = codec.pack(source, hashlib.sha256(self.raw).hexdigest(), directory, 4096)
        self.manifest = directory / self.packed['manifest']
        self.env.update(ARCH=arch, MEDIA_MANIFEST=str(self.manifest), MEDIA_MANIFEST_SHA256=self.packed['sha256'],
                        CONTROL_RAW_SHA256=hashlib.sha256(self.raw).hexdigest(),
                        CONTROL_QA_ARCH='aarch64' if arch == 'aarch64' else 'x86_64')

    def run_master(self, *args, check=True, **environment):
        result = subprocess.run(['bash', str(ROOT / 'scripts/master-release.sh'), *args],
                                env=dict(self.env, **environment), capture_output=True, text=True)
        if check and result.returncode:
            self.fail(result.stdout + result.stderr)
        return result

    def stick_args(self):
        return ['sticks', '--manifest', str(self.manifest), '--manifest-sha256', self.packed['sha256'],
                '--raw-sha256', hashlib.sha256(self.raw).hexdigest(), '--raw-size', str(len(self.raw)),
                '--device', '/dev/sdzzb:TEST']

    def test_real_master_reconstruction_and_both_architecture_qa_paths(self):
        for arch in ['aarch64', 'amd64']:
            if arch == 'amd64':
                self.select(arch)
            with self.subTest(arch=arch):
                self.run_master('--force', 'verify')
                outputs = list(self.work.glob('master-media.*/' + self.image))
                self.assertTrue(outputs)
                self.assertEqual(outputs[-1].read_bytes(), self.raw)
                previous = self.root / 'qa'
                previous.mkdir(exist_ok=True)
                (previous / 'retained').write_text('earlier evidence')
                self.run_master('--force', 'qa')
                receipt = json.loads((self.root / 'qa-receipt.json').read_text())
                self.assertEqual(receipt['arch'], self.env['CONTROL_QA_ARCH'])
                self.assertEqual(Path(receipt['image']).read_bytes(), self.raw)
                self.assertEqual((previous / 'retained').read_text(), 'earlier evidence')

    def test_private_join_does_not_overwrite_and_preserves_failed_output(self):
        target = self.root / 'reconstructed.iso'
        master.selected(self.manifest, self.packed['sha256'], self.image, target)
        self.assertEqual(target.read_bytes(), self.raw)
        with self.assertRaises(ValueError):
            master.selected(self.manifest, self.packed['sha256'], self.image, target)
        self.assertEqual(target.read_bytes(), self.raw)
        part = self.manifest.parent / self.packed['parts'][0]['name']
        part.write_bytes(b'broken')
        failed = self.root / 'failed.iso'
        with self.assertRaises((ValueError, lzma.LZMAError)):
            master.selected(self.manifest, self.packed['sha256'], self.image, failed)
        self.assertFalse(failed.exists())
        self.assertTrue(list(self.root.glob('.failed.iso.*')))

    def test_wrong_pin_architecture_and_historical_release_refuse(self):
        for environment in [dict(MEDIA_MANIFEST_SHA256='0' * 64), dict(ARCH='amd64'), dict(RELEASE='1.5.1'),
                            dict(MEDIA_MANIFEST_SHA256='')]:
            with self.subTest(environment=environment):
                self.assertNotEqual(self.run_master('verify', check=False, **environment).returncode, 0)
        self.assertFalse((self.work / 'master-state.tsv').exists())

    def test_remote_tamper_refuses_before_qa_runner(self):
        result = self.run_master('qa', check=False, CONTROL_CORRUPT_TRANSFER='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'qa-receipt.json').exists())
        self.assertFalse((self.work / 'master-state.tsv').exists())
        self.assertTrue(list(self.root.glob('qa.split.*/.daemonarchy*.iso.*')))

    def test_old_resume_state_cannot_skip_split_checks(self):
        state = self.work / 'master-state.tsv'
        state.write_text('verify\tok\told\n')
        self.run_master('verify')
        self.assertIn('verify:xz-parts@1:' + self.packed['sha256'], state.read_text())
        self.assertTrue(list(self.work.glob('master-media.*')))
        # Even the exact recorded selection rechecks all bytes before reusing a step.
        part = self.manifest.parent / self.packed['parts'][0]['name']
        part.write_bytes(b'changed')
        self.assertNotEqual(self.run_master('verify', check=False).returncode, 0)

    def test_dry_run_does_not_create_outputs_or_contact_qa(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        self.run_master('--dry-run', 'verify', 'qa')
        self.run_master('--dry-run', *self.stick_args())
        self.assertEqual(sorted(str(p) for p in self.root.rglob('*')), before)

    def test_split_sticks_verify_identity_before_device_dispatch(self):
        args = self.stick_args()
        wrong = list(args)
        wrong[wrong.index('--raw-sha256') + 1] = '0' * 64
        self.assertNotEqual(self.run_master(*wrong, check=False).returncode, 0)
        wrong = list(args)
        wrong[wrong.index('--raw-size') + 1] = str(len(self.raw) + 1)
        self.assertNotEqual(self.run_master(*wrong, check=False).returncode, 0)
        self.assertNotEqual(self.run_master(*args, '--iso', str(self.root / self.image), check=False).returncode, 0)
        part = self.manifest.parent / self.packed['parts'][0]['name']
        part.write_bytes(b'changed')
        self.assertNotEqual(self.run_master(*args, check=False).returncode, 0)
        self.assertFalse((self.root / 'device.log').exists())

    def test_hwtrace_extracts_only_the_selected_split_images_boot_payload(self):
        (self.product / 'build-hwtrace-image.sh').write_text("""#!/bin/sh
python3 - "$@" <<'CONTROL_ONLY'
import hashlib, lzma, os, pathlib, sys
args = sys.argv[1:]
def argument(flag): return args[args.index(flag) + 1]
assert hashlib.sha256(pathlib.Path(argument('-I')).read_bytes()).hexdigest() == os.environ['CONTROL_RAW_SHA256']
assert pathlib.Path(argument('-k')).read_bytes() == b'selected kernel'
assert pathlib.Path(argument('-l')).read_bytes() == b'selected loader'
lua = pathlib.Path(argument('-L'))
assert (lua / 'retained.lua').read_bytes() == b'retained'
assert not (lua / 'brand-daemonarchy.lua').exists() and not (lua / 'local.lua').exists()
name = 'daemonarchy-hwtrace-' + argument('-V') + '-' + argument('-a') + '.img.xz'
output = pathlib.Path(argument('-o')) / name
output.write_bytes(lzma.compress(b'controller hwtrace fixture; not bootable'))
output.with_name(name + '.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + name + chr(10))
CONTROL_ONLY
""")
        self.run_master('hwtrace')
        output = self.work / 'assets-1.6.0/daemonarchy-hwtrace-1.6.0-aarch64.img.xz'
        before = output.read_bytes()
        self.assertIn(b'controller hwtrace fixture', lzma.decompress(before))
        self.assertNotEqual(self.run_master('--force', 'hwtrace', check=False).returncode, 0)
        self.assertEqual(output.read_bytes(), before)

    def fake_device(self, bad_readback=False):
        # Only this executable sees /dev-like arguments. It never opens a device.
        self.script('sudo', """#!/usr/bin/env python3
import hashlib, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CONTROL_DEVICE_LOG'], 'a') as log: log.write(repr(args) + chr(10))
image = pathlib.Path(os.environ['CONTROL_FAKE_DEVICE'])
if args[0] == 'dd':
    source = next((a[3:] for a in args if a.startswith('if=')), None)
    assert 'of=/dev/sdzzb' in args
    data = pathlib.Path(source).read_bytes() if source else sys.stdin.buffer.read()
    assert hashlib.sha256(data).hexdigest() == os.environ['CONTROL_RAW_SHA256']
    image.write_bytes(data)
elif args[:2] == ['head', '-c']:
    assert args[3] == '/dev/sdzzb'
    data = image.read_bytes()[:int(args[2])]
    if os.environ.get('CONTROL_BAD_READBACK'): data = b'corrupt' + data[7:]
    sys.stdout.buffer.write(data)
else:
    raise SystemExit('unexpected simulated-device command')
""")
        self.script('sync', '#!/bin/sh\nexit 0\n')
        self.env['CONTROL_FAKE_DEVICE'] = str(self.root / 'fake-device-image')
        self.env['TMPDIR'] = str(self.root)
        if bad_readback: self.env['CONTROL_BAD_READBACK'] = '1'

    def test_split_sticks_full_reconstruction_write_and_readback_control(self):
        self.fake_device()
        self.run_master(*self.stick_args())
        self.assertEqual((self.root / 'fake-device-image').read_bytes(), self.raw)
        log = (self.root / 'device.log').read_text()
        self.assertIn("'dd'", log)
        self.assertIn("'head', '-c'", log)
        self.assertIn('sticks\tok', (self.work / 'master-state.tsv').read_text())
        self.assertTrue(list(self.root.glob('daemonarchy-sticks.*/reconstructed.json')))

    def test_split_sticks_bad_readback_never_records_success(self):
        self.fake_device(bad_readback=True)
        result = self.run_master(*self.stick_args(), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('read back', result.stderr)
        self.assertFalse((self.work / 'master-state.tsv').exists())

    def test_all_named_devices_pass_checks_before_first_write(self):
        self.fake_device()
        result = self.run_master(*self.stick_args(), '--device', '/dev/sdzzc:WRONG', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'device.log').exists())

    def test_single_file_writer_preserves_literal_quoted_paths(self):
        self.fake_device()
        image = self.root / "literal'file.iso.xz"
        image.write_bytes(lzma.compress(self.raw))
        self.run_master('sticks', '--iso', str(image), '--raw-sha256', self.env['CONTROL_RAW_SHA256'],
                        '--raw-size', str(len(self.raw)), '--device', '/dev/sdzzb:TEST')
        self.assertEqual((self.root / 'fake-device-image').read_bytes(), self.raw)

    def test_split_qa_refuses_relative_destination_without_ssh(self):
        self.assertNotEqual(self.run_master('qa', QA_DIR='relative', check=False).returncode, 0)
        self.assertFalse((self.root / 'ssh.log').exists())

    def test_listing_probe_drains_producer_after_sqlite_match(self):
        self.script('bsdtar', """#!/bin/sh
if [ "$1" = -tf ]; then
  tar "$@"
  python3 -c 'import sys; sys.stdout.write("extra listing entry" * 100000)'
else
  exec tar "$@"
fi
""")
        self.run_master('verify')

    def test_mounted_device_probe_drains_producer_before_refusing(self):
        self.fake_device()
        self.script('mount', """#!/usr/bin/env python3
import sys
sys.stdout.write('/dev/sdzzb1 on /fixture type ufs' + chr(10))
sys.stdout.flush()
sys.stdout.write('other mounted entry' * 100000)
""")
        result = self.run_master(*self.stick_args(), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('mounted filesystem', result.stderr)
        self.assertFalse((self.root / 'device.log').exists())

    def test_master_budget_rejected_before_creating_output(self):
        record = codec.load_manifest(self.manifest, self.packed['sha256'])
        record['image']['bytes'] = master.RAW_LIMIT
        record['part_raw_bytes'] = codec.PART_LIMIT
        record['parts'] = []
        for n in range(4):
            name = f"{self.image}.part{n+1:04d}.xz"
            (self.manifest.parent / name).write_bytes(b'placeholder')
            record['parts'].append(dict(name=name, bytes=11, sha256='1' * 64,
                                       raw_bytes=min(codec.PART_LIMIT, master.RAW_LIMIT - n*codec.PART_LIMIT), raw_sha256='2' * 64))
        expected = {p['name'] for p in record['parts']}
        for path in self.manifest.parent.glob(self.image + '.part[0-9]*.xz'):
            if path.name not in expected: path.unlink()
        data = lzma.compress(json.dumps(record).encode(), check=lzma.CHECK_SHA256)
        self.manifest.write_bytes(data)
        pin = hashlib.sha256(data).hexdigest()
        self.manifest.with_name(self.manifest.name + '.sha256').write_text(f"{pin}  {self.manifest.name}\n")
        target = self.root / 'oversized.iso'
        with self.assertRaisesRegex(ValueError, 'budget'):
            master.selected(self.manifest, pin, self.image, target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob('.oversized.iso.*')))


if __name__ == '__main__':
    unittest.main()
