#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Acceptance rejects stale, partial, SD-only or single-CPU UEFI captures."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("uefi_usb_control", Path(__file__).resolve().parents[1] /
                                             "tools/hwtrace/pi4-uefi-simulator.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class UefiUsbChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.label = "uefi-usb-fresh"
        self.serial = "FreeBSD/arm64 EFI loader\nloader ACPI capture saved and read back\n"
        self.snapshot = {"topology": {"enabled": 4}}
        (self.root / "dmesg.txt").write_text("acpi0: <BRCM>\nxhci0: <Generic xHCI>\n"
            "umass0: <QEMU>\nda0: <QEMU>\nTrying to mount root from ufs:/dev/gpt/HWTROOT [ro]\n")
        (self.root / "kenv.txt").write_text('boottrace_capture_acpi="YES"\n'
            'boottrace_label="uefi-usb-fresh"\nboottrace_q_id="0001"\n')
        (self.root / "sysctl.txt").write_text("kern.smp.cpus: 4\nkern.smp.active: 1\nhw.pagesize: 4096\n")
        (self.root / "capture.log").write_text("".join(f"finish {p}.txt status=0\n" for p in control.PROBES))
        (self.root / "done.txt").write_text("completed\n")

    def checks(self):
        return control.assess(self.serial, self.root, self.snapshot, self.label)

    def test_requires_actual_usb_and_completed_probes(self):
        self.assertTrue(all(self.checks().values()))
        dmesg = self.root / "dmesg.txt"
        dmesg.write_text(dmesg.read_text().replace("umass0:", "mmcsd0:"))
        self.assertFalse(self.checks()["native_usb_storage"])
        (self.root / "capture.log").write_text("finish dmesg.txt status=0\n")
        self.assertFalse(self.checks()["all_probes_complete"])
        (self.root / "done.txt").write_bytes(b"")
        self.assertFalse(self.checks()["done_marker"])

    def test_rejects_stale_profile_and_missing_acpi(self):
        self.label = "another-run"
        self.assertFalse(self.checks()["fresh_run_label"])
        self.serial = "FreeBSD/arm64 EFI loader"
        self.assertFalse(self.checks()["loader_acpi_readback"])
        (self.root / "kenv.txt").write_text('boottrace_capture_acpi="NO"\n')
        self.assertFalse(self.checks()["acpi_profile"])
        self.assertFalse(self.checks()["queue_experiment"])

    def test_requires_active_smp_and_firmware_topology_independently(self):
        (self.root / "sysctl.txt").write_text("kern.smp.cpus: 1\nkern.smp.active: 0\nhw.pagesize: 4096\n")
        self.assertFalse(self.checks()["four_active_cpus"])
        self.snapshot["topology"]["enabled"] = 3
        self.assertFalse(self.checks()["acpi_four_enabled_cpus"])

    def test_ownership_warning_and_missing_diagnostics_cannot_pass(self):
        dmesg = self.root / "dmesg.txt"
        dmesg.write_text(dmesg.read_text() + "_secure_path: /etc/login.conf\n")
        self.assertFalse(self.checks()["no_ownership_warning"])
        (self.root / "done.txt").unlink()
        with self.assertRaises(FileNotFoundError):
            self.checks()


if __name__ == "__main__":
    unittest.main()
