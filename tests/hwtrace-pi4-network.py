#!/usr/bin/env python3
"""Guard actual-NIC selection, SSH identity/output and durable transfer evidence."""
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('network', Path(__file__).resolve().parents[1] / 'tools/hwtrace/pi4-network-simulator.py')
network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(network)
LINK = ('genet0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> metric 0 mtu 1500\n'
        '\tether 52:54:00:12:34:56\n\tinet 10.0.2.15 netmask 0xffffff00\n'
        '\tmedia: Ethernet autoselect (1000baseT <full-duplex>)\n\tstatus: active\n')
STATS = ('Name Mtu Network Address Ipkts Ierrs Idrop Ibytes Opkts Oerrs Obytes Coll\n'
         'genet0 1500 <Link#1> 52:54:00:12:34:56 900 0 0 2097152 1800 0 4194304 0\n')


class NetworkGuards(unittest.TestCase):
    def test_helper_timeout_is_waiting_not_success_or_guest_terminal(self):
        with mock.patch.object(network.subprocess, 'run', side_effect=network.subprocess.TimeoutExpired('wait', 1)):
            self.assertFalse(network.banner_ready('wait', Path('.'), 100))
        for answer, expected in (('waiting', False), ('ready', True)):
            with mock.patch.object(network.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=0, stdout=answer, stderr='')):
                self.assertEqual(network.banner_ready('wait', Path('.'), 100), expected)

    def test_zero_ssh_status_does_not_prove_completed_command(self):
        def result(stdout, rc=0):
            return SimpleNamespace(returncode=rc, stdout=stdout, stderr='failure')
        self.assertEqual(network.framed_output(result('NET_BEGIN_new\ndata\nNET_END_new\n'), 'new'), 'data\n')
        for stdout in ('', 'data\n', 'NET_BEGIN_old\ndata\nNET_END_old\n',
                       'NET_BEGIN_new\npartial', 'NET_BEGIN_new\nNET_END_new\nNET_END_new\n'):
            with self.assertRaises(ValueError):
                network.framed_output(result(stdout), 'new')
        with self.assertRaises(RuntimeError):
            network.framed_output(result('NET_BEGIN_new\ndata\nNET_END_new\n', 1), 'new')

    def test_other_nic_wrong_mac_ip_or_link_cannot_qualify(self):
        self.assertTrue(all(network.link_checks(LINK).values()))
        for text in (LINK.replace('genet0', 'em0'), LINK.replace('52:54:00:12:34:56', '52:54:00:00:00:01'),
                     LINK.replace('10.0.2.15', '169.254.2.15'), LINK.replace('status: active', 'status: no carrier'),
                     LINK + LINK.replace('genet0', 'em0')):
            self.assertFalse(all(network.link_checks(text).values()))

    def test_packet_counts_require_both_byte_directions_on_genet(self):
        self.assertTrue(network.packet_counters(STATS))
        for text in (STATS.replace('genet0', 'em0'), STATS.replace('2097152', '100'),
                     STATS.replace('4194304', '100'), STATS.replace('Ibytes', 'missing'), ''):
            self.assertFalse(network.packet_counters(text))

    def test_scp_success_without_exact_fresh_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'payload'
            expected = hashlib.sha256(bytes(network.SIZE)).hexdigest()
            for data in (None, b'', bytes(network.SIZE - 1), b'x' * network.SIZE):
                if data is not None:
                    p.write_bytes(data)
                with self.assertRaises(ValueError):
                    network.verify_file(p, expected)
            p.write_bytes(bytes(network.SIZE))
            network.verify_file(p, expected)

    def test_durable_network_records_need_current_queue_and_complete_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            control = network.NetworkControl(SimpleNamespace())
            control.output = p
            control.label = 'current'
            control.report.update(bidirectional_payloads=True, ssh_host_key_verified=True,
                                  natural_qemu_exit=True, continue_requested=True, transport_complete=True)
            (p / 'network.txt').write_text('state=listening\ninterface=genet0\naddress=10.0.2.15\n')
            (p / 'network-ifconfig.txt').write_text(LINK)
            (p / 'network-netstat.txt').write_text(STATS)
            (p / 'network-token.txt').write_text('current\n')
            (p / 'kenv.txt').write_text('boottrace_label="current"\n')
            self.assertTrue(all(control.assess(p).values()))
            (p / 'network-token.txt').write_text('old\n')
            self.assertFalse(control.assess(p)['fresh_network_diagnostics'])
            (p / 'network-token.txt').write_text('current\n')
            (p / 'network.txt').write_text('state=listening\ninterface=genet0\naddress=10.0.2.15\naddress=192.0.2.1\n')
            self.assertFalse(control.assess(p)['network_handover_genet'])
            (p / 'network-ifconfig.txt').unlink()
            with self.assertRaises(FileNotFoundError):
                control.assess(p)


if __name__ == '__main__':
    unittest.main()
