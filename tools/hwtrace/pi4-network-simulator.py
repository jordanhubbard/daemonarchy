#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Actual FreeBSD GENET DHCP/SSH/SCP control over isolated QEMU user networking.

Uses immutable regular inputs, a fresh image/overlay and VM-only SSH identities.
The native FDT GENET driver must exchange actual packets; no other NIC qualifies.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pi4_fdt_network', HERE / 'pi4-simulator.py')
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
spec = importlib.util.spec_from_file_location('pi4_network_stick', HERE.parent / 'boottrace/stick.py')
stick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stick)
SIZE = 1 << 20
MAC = '52:54:00:12:34:56'
ADDRESS = '10.0.2.15'


def framed_output(completed, nonce):
    if completed.returncode:
        raise RuntimeError(f'SSH command failed ({completed.returncode}): {completed.stderr[-4096:]}')
    text = completed.stdout
    if len(text) > 1 << 20:
        raise ValueError('SSH observation exceeds bound')
    begin, end = f'NET_BEGIN_{nonce}\n', f'NET_END_{nonce}\n'
    if not text.startswith(begin) or not text.endswith(end) or text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError('SSH command lacks fresh complete output framing')
    return text[len(begin):-len(end)]


def link_checks(text):
    blocks = re.split(r'(?m)^(?=[A-Za-z][A-Za-z0-9]*: flags=)', text)
    interfaces = {block.split(':', 1)[0]: block for block in blocks if ': flags=' in block}
    genet = interfaces.get('genet0', '')
    other_wired = [name for name, block in interfaces.items() if name != 'genet0' and re.search(r'(?m)^\s+ether ', block)]
    return {'native_genet_only': bool(genet) and not other_wired,
            'configured_mac': f'ether {MAC}' in genet,
            'dhcp_ipv4': bool(re.search(r'\binet ' + re.escape(ADDRESS) + r'\b', genet)),
            'genet_link_active': bool(re.search(r'(?m)^\s+status: active\s*$', genet))}


def packet_counters(text):
    lines = [line.split() for line in text.splitlines() if line.strip()]
    for n, header in enumerate(lines):
        if not all(name in header for name in ('Name', 'Ibytes', 'Obytes')):
            continue
        incoming, outgoing = header.index('Ibytes'), header.index('Obytes')
        for row in lines[n + 1:]:
            if row and row[0].rstrip('*') == 'genet0' and len(row) > max(incoming, outgoing):
                try:
                    if int(row[incoming]) >= SIZE and int(row[outgoing]) >= SIZE:
                        return True
                except ValueError:
                    pass
    return False


def verify_file(path, expected):
    if not path.is_file() or path.stat().st_size != SIZE or sim.digest(path) != expected:
        raise ValueError(f'SCP payload missing, partial or SHA-256 mismatch: {path.name}')


def banner_ready(waiter, output, milliseconds):
    expression = ('(if (cadr (assoc (quote satisfied) '
        '(wait-for (quote (matches "serial.log" '
        '"=== Daemonarchy hardware trace: debugger ready ===")) '
        f'(quote ((timeout-ms {milliseconds})))))) "ready" "waiting")')
    try:
        waited = subprocess.run([waiter, '--root', str(output), '--text', '-e', expression],
            cwd=output, capture_output=True, text=True, timeout=milliseconds / 1000 + 5)
    except subprocess.TimeoutExpired:
        # A helper deadline is not a guest reset, terminal state or success.
        return False
    if waited.returncode:
        raise RuntimeError(f'observable wait failed: {waited.stderr[-2048:]}')
    answer = waited.stdout.strip()
    if answer not in ('ready', 'waiting'):
        raise RuntimeError(f'invalid observable wait result: {answer[-2048:]}')
    return answer == 'ready'


class NetworkControl:
    def __init__(self, args):
        self.args = args
        self.label = 'genet-' + secrets.token_hex(12)
        self.report = {'schema': 'daemonarchy/pi4-genet-network@1', 'label': self.label, 'ok': False}

    def prepare(self, control, queue, output):
        self.output = output
        self.waiter = shutil.which('toolscheme')
        if self.waiter is None:
            raise ValueError('toolscheme must be on PATH for bounded observable waits')
        self.client = output / 'controller_key'
        self.host = output / 'vm_host_key'
        for path in (self.client, self.host):
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'private-genet-vm', '-f', str(path)], check=True)
            path.chmod(0o600)
        volume = stick.Volume(str(control))
        volume.mkdir('KEYS')
        volume.write('KEYS/authorized_keys', self.client.with_suffix('.pub').read_bytes())
        volume.write('KEYS/ssh_host_ed25519_key', self.host.read_bytes())
        volume.write('KEYS/ssh_host_ed25519_key.pub', self.host.with_suffix('.pub').read_bytes())
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            self.port = reserve.getsockname()[1]
        self.known_hosts = output / 'known_hosts'
        self.known_hosts.write_text(f'[127.0.0.1]:{self.port} ' + self.host.with_suffix('.pub').read_text())
        self.known_hosts.chmod(0o600)
        fingerprint = subprocess.check_output(['ssh-keygen', '-lf', str(self.host.with_suffix('.pub'))], text=True).split()[1]
        self.report.update(ssh_host_fingerprint=fingerprint, host_forward=f'127.0.0.1:{self.port}',
                           mac=MAC, interface='genet0', address=ADDRESS,
                           harness_sha256=sim.digest(Path(__file__).resolve()),
                           fdt_harness_sha256=sim.digest(HERE / 'pi4-simulator.py'))
        queue.write_text(f'[pi4-native-genet]\nhw.ncpu=4\nboottrace_label="{self.label}"\n'
                         'hwtrace.net="YES"\nhwtrace.dhcp=30\nhwtrace.hold=120\n')
        self.save()

    def validate_image(self, control):
        subprocess.run([sys.executable, str(HERE.parent / 'boottrace/stick.py'),
                        'check-map', str(control)], check=True)
        self.report['slot_map_valid_after_keys_and_queue'] = True
        self.save()

    def save(self):
        (self.output / 'network-result.json').write_text(json.dumps(self.report, indent=2) + '\n')

    def configure_dtb(self, path):
        node = '/scb/ethernet@7d580000'
        subprocess.run(['fdtput', '-t', 's', str(path), node, 'status', 'okay'], check=True)
        for prop in ('local-mac-address', 'mac-address'):
            subprocess.run(['fdtput', '-t', 'bx', str(path), node, prop, *MAC.split(':')], check=True)

    def configure_command(self, command):
        command = list(command)
        i = command.index('-nic')
        assert command[i + 1] == 'none'
        command.extend(['-global', 'bcm2838-peripherals.genet-network=on',
            '-netdev', f'user,id=genet0,restrict=on,hostfwd=tcp:127.0.0.1:{self.port}-:2222',
            '-global', 'bcm2838-genet.netdev=genet0', '-global', f'bcm2838-genet.mac={MAC}'])
        return command

    def identity(self):
        return {key: value for key, value in {**self.report, 'network': 'QEMU usernet restricted; loopback-only forwarding',
                'trust': 'preprovisioned VM host key; StrictHostKeyChecking=yes'}
                .items() if key != 'ok'}

    def options(self):
        return ['-F', '/dev/null', '-i', str(self.client), '-o', 'BatchMode=yes',
                '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'ForwardAgent=no',
                '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={self.known_hosts}',
                '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=3',
                '-o', 'ConnectionAttempts=1', '-o', 'ControlMaster=no']

    def remote(self, script):
        nonce = secrets.token_hex(12)
        script = f"set -eu; printf 'NET_BEGIN_{nonce}\\n'; {script}; printf 'NET_END_{nonce}\\n'"
        command = ['ssh', *self.options(), '-p', str(self.port), 'root@127.0.0.1', script]
        result = subprocess.run(command, capture_output=True, text=True, timeout=self.remaining())
        return framed_output(result, nonce)

    def remaining(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('network experiment deadline expired')
        return min(left, 30)

    def transfer(self, source, target):
        result = subprocess.run(['scp', *self.options(), '-P', str(self.port), source, target],
                                capture_output=True, text=True, timeout=self.remaining())
        if result.returncode:
            raise RuntimeError(f'SCP failed ({result.returncode}): {result.stderr[-4096:]}')

    def collect_extra(self):
        """Collect transport-specific evidence before the natural hand-over ends."""

    def wait(self, process, timeout):
        self.deadline = time.monotonic() + timeout
        try:
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Guest exited before network hand-over')
                milliseconds = max(1, min(2000, int(self.remaining() * 1000)))
                if banner_ready(self.waiter, self.output, milliseconds):
                    break
            # The banner is emitted after the rc collector unmounts DATRACE.
            identity = self.remote('id -u; ifconfig -a; netstat -rn')
            if not identity.startswith('0\n') or not all(link_checks(identity).values()):
                raise ValueError('SSH peer is not root on the actual linked GENET interface')
            (self.output / 'ssh-identity.txt').write_text(identity)
            payload = os.urandom(SIZE)
            upload = self.output / 'upload.bin'
            upload.write_bytes(payload)
            upload_sha = hashlib.sha256(payload).hexdigest()
            remote_upload = f'/var/tmp/{self.label}.upload'
            remote_download = f'/var/tmp/{self.label}.download'
            self.transfer(str(upload), f'root@127.0.0.1:{remote_upload}')
            guest_md5 = self.remote(f'/rescue/rescue md5 -q {remote_upload}').strip()
            if guest_md5 != hashlib.md5(payload).hexdigest():
                raise ValueError('Guest upload digest mismatch')
            returned = self.output / 'upload-roundtrip.bin'
            self.transfer(f'root@127.0.0.1:{remote_upload}', str(returned))
            verify_file(returned, upload_sha)
            guest_md5 = self.remote(f'/rescue/rescue dd if=/dev/zero of={remote_download} bs=65536 count=16 2>/dev/null; '
                                    f'/rescue/rescue md5 -q {remote_download}').strip()
            zeros = bytes(SIZE)
            if guest_md5 != hashlib.md5(zeros).hexdigest():
                raise ValueError('Guest-generated download digest mismatch')
            downloaded = self.output / 'download.bin'
            self.transfer(f'root@127.0.0.1:{remote_download}', str(downloaded))
            verify_file(downloaded, hashlib.sha256(zeros).hexdigest())
            snapshots = self.remote('ifconfig -a; netstat -ibn')
            if not all(link_checks(snapshots).values()) or not packet_counters(snapshots):
                raise ValueError('GENET packet counters do not cover transferred payloads')
            self.report.update(upload_sha256=upload_sha, roundtrip_sha256=sim.digest(returned),
                               download_sha256=sim.digest(downloaded), transfer_bytes=SIZE,
                               actual_genet_link=True, bidirectional_payloads=True, ssh_host_key_verified=True)
            self.remote('mount -t msdosfs -o sync /dev/gpt/DATRACE /mnt; '
                        f"printf '%s\\n' '{self.label}' > /mnt/DUMPS/0001/network-token.txt; "
                        'ifconfig -a > /mnt/DUMPS/0001/network-ifconfig.txt; '
                        'netstat -ibn > /mnt/DUMPS/0001/network-netstat.txt; sync; umount /mnt')
            self.collect_extra()
            self.remote('/sbin/hwtrace-continue')
            self.report['continue_requested'] = True
            code = process.wait(timeout=self.remaining())
            self.report['natural_qemu_exit'] = code == 0
            self.report['transport_complete'] = code == 0
            return code
        except BaseException as error:
            self.report['error'] = str(error)
            raise
        finally:
            self.save()

    def assess(self, dumps):
        network = (dumps / 'network.txt').read_text(errors='replace')
        ifconfig = (dumps / 'network-ifconfig.txt').read_text(errors='replace')
        stats = (dumps / 'network-netstat.txt').read_text(errors='replace')
        token = (dumps / 'network-token.txt').read_text().strip()
        kenv = (dumps / 'kenv.txt').read_text(errors='replace')
        metadata = {key: re.findall(r'^' + key + r'=(.*)$', network, re.MULTILINE)
                    for key in ('state', 'interface', 'address')}
        checks = {'network_handover_genet': metadata == {
                      'state': ['listening'], 'interface': ['genet0'], 'address': [ADDRESS]},
                  'fresh_network_diagnostics': token == self.label and f'boottrace_label="{self.label}"' in kenv,
                  'scp_bidirectional_sha256': self.report.get('bidirectional_payloads') is True,
                  'verified_vm_host_key': self.report.get('ssh_host_key_verified') is True,
                  'native_packet_counts': packet_counters(stats),
                  'natural_network_continue': self.report.get('natural_qemu_exit') is True and self.report.get('continue_requested') is True}
        checks.update(link_checks(ifconfig))
        self.report['offline_checks'] = checks
        self.report['ok'] = all(checks.values()) and self.report.get('transport_complete') is True
        self.save()
        return checks


def main(control_class=NetworkControl, description=__doc__):
    parser = argparse.ArgumentParser(description=description)
    sim.memory_options(parser)
    for name in ('image', 'uboot', 'dtb', 'qemu'):
        parser.add_argument('--' + name, type=Path, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--qemu-img', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    if not 60 <= args.timeout <= 3600:
        parser.error('timeout must be between 60 and 3600 seconds')
    try:
        args.qemu = sim.checked(args.qemu, args.qemu_sha256)
        image = sim.checked(args.image, args.image_sha256)
        if stick.Volume(str(image)).listdir('DUMPS'):
            raise ValueError('source DUMPS must be empty; refuse stale evidence')
        sim.run(args, control_class(args))
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
