#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Guard the simulator's boot/collection acceptance and raw-image bounds."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("pi4sim", Path(__file__).resolve().parents[1] / "tools/hwtrace/pi4-simulator.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


class SimulatorChecks(unittest.TestCase):
    def test_diagnostic_completion_requires_every_probe_and_smp(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / "kenv.txt").write_text('boottrace_capture_acpi="NO"\n')
            (p / "capture.log").write_text("".join(f"finish {n}.txt status=0\n" for n in ("dmesg", "kenv", "sysctl", "kldstat", "pciconf", "devinfo", "usbconfig")))
            (p / "done.txt").write_text("completed\n")
            (p / "sysctl.txt").write_text("kern.smp.active: 1\nkern.smp.cpus: 4\nhw.pagesize: 4096\n")
            serial = "\n".join(sim.CHECKS.values())
            self.assertTrue(all(sim.assess(serial, p).values()))
            (p / "capture.log").write_text("finish dmesg.txt status=0\n")
            self.assertFalse(sim.assess(serial, p)["completed_probes"])
            (p / "kenv.txt").write_text('boottrace_capture_acpi="YES"\n')
            self.assertFalse(sim.assess(serial, p)["fdt_profile"])
            self.assertFalse(sim.assess(serial.replace("Resetting system", ""), p)["reset"])
            self.assertFalse(sim.assess(serial + "_secure_path: /etc/login.conf", p)["no_ownership_warning"])

    def test_regular_input_refuses_device_and_mismatched_hash(self):
        with self.assertRaises(ValueError):
            sim.regular(Path("/dev/null"))
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "image"
            p.write_bytes(b"control")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                sim.checked(p, "0" * 64)
            self.assertEqual(p.read_bytes(), b"control")

    def test_gpt_partition_must_be_within_regular_image(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "image"
            data = bytearray(4096)
            data[512:520] = b"EFI PART"
            struct.pack_into("<QII", data, 512 + 72, 2, 1, 128)
            struct.pack_into("<QQ", data, 1024 + 32, 4, 7)
            data[1024 + 56:1024 + 56 + 14] = "DATRACE".encode("utf-16-le")
            p.write_bytes(data)
            self.assertEqual(sim.data_offset(p), 2048)
            struct.pack_into("<Q", data, 1024 + 40, 8)
            p.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "bounded DATRACE"):
                sim.data_offset(p)


if __name__ == "__main__":
    unittest.main()
