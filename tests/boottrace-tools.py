#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Host checks for the boottrace decoder, stick manager and Windows reader."""

import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "boottrace"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


decoder = load("decode_boottrace", TOOLS / "decode-boottrace.py")
stick = load("stick", TOOLS / "stick.py")


def record(status=1, flags=0, msgs=b"atrtc0: Warning: Couldn't map I/O.\n"):
    crumbs = [
        struct.pack("<IIHHII76s", 41, 1200, 1, 0, 0x3800000, 0, b"configure_first"),
        struct.pack("<IIHHII76s", 42, 1250, 3, 1, 0, 0,
                    b"attach atrtc0 on isa1 drv atrtc "),
    ]
    header = struct.pack("<8sHHHHIIIIIIIIIIII64s", b"DBTRACE1", 1, 128, 96,
                         len(crumbs), 0, 7, status, flags, 42, 0xFFFFFFFF, len(msgs),
                         1250, 200, 150, 12, 0, b"FreeBSD 16.0-CURRENT #0 test")
    data = header + b"".join(crumbs) + msgs
    return data[:16] + struct.pack("<I", len(data)) + data[20:]


class Decoder(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(decoder.HEADER.size, 128)
        self.assertEqual(decoder.CRUMB.size, 96)

    def test_decode_and_report(self):
        rec = decoder.decode(record())
        self.assertEqual(rec["seq"], 7)
        self.assertEqual(rec["crumbs"][-1]["kind"], "attach")
        text = decoder.report(rec)
        self.assertIn("Status: INCOMPLETE", text)
        self.assertIn("Last step: #42 1.250s cpu1 attach: attach atrtc0 on isa1", text)
        self.assertIn("[sub 0x3800000 order 0x0]", text)
        self.assertIn("Couldn't map I/O", text)
        self.assertIn("200 KiB, 12 KiB written", text)
        self.assertIn("Persisted: coarse steps only", text)

    def test_rejects_truncation(self):
        with self.assertRaises(ValueError):
            decoder.decode(record()[:200])

    def test_vars_store_counts_copies(self):
        name = (decoder.VARNAME + "\0").encode("utf-16-le")
        data = record()
        def var(state, payload):
            hdr = decoder.VAR_HDR.pack(0x55AA, state, 0, 7, 0, bytes(16), 0,
                                       len(name), len(payload), decoder.GUID.bytes_le)
            blob = hdr + name + payload
            return blob + bytes(-len(blob) % 4)
        body = var(0x3C, record(status=1)) + var(0x3F, record(status=2))
        store = (decoder.AUTH_VAR_GUID.bytes_le + struct.pack("<I", 28 + len(body) + 64)
                 + bytes(8) + body + b"\xff" * 64)
        copies, live = decoder.scan_vars(b"\0" * 72 + store)
        self.assertEqual(copies, 2)
        self.assertEqual(decoder.decode(live)["status"], 2)


class Stick(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def run_cli(self, *argv):
        stick.main(list(argv))

    def test_parse_experiments(self):
        exps = stick.parse_experiments("[a]\nread-conf /boot/d/1\nx.y=1\n\n[b]\nunset z\n")
        self.assertEqual([e["name"] for e in exps], ["a", "b"])
        with self.assertRaises(ValueError):
            stick.parse_experiments("boot -s\n")
        with self.assertRaises(ValueError):
            stick.parse_experiments("[a]\nboot -s\n")

    def test_init_queue_and_traces(self):
        self.run_cli("init", self.dir)
        q = Path(self.dir, "q.txt")
        q.write_text("[one]\nread-conf /boot/d/1\n[two]\nhint.hpet.0.disabled=1\n")
        self.run_cli("queue", self.dir, str(q))
        self.assertEqual(Path(self.dir, "STATE.TXT").read_text(),
                         "next=1\ntraces=0\npending=\n")
        self.assertIn("hint.hpet.0.disabled=1",
                      Path(self.dir, "QUEUE", "0002.CNF").read_text())
        # A loader-filed trace stays across a requeue unless reset.
        Path(self.dir, "TRACES", "0001.TXT").write_text(
            "experiment: 0001\nStatus: INCOMPLETE: x\nLast step: #3 attach\n")
        Path(self.dir, "STATE.TXT").write_text("next=2\ntraces=1\npending=0001\n")
        self.run_cli("queue", self.dir, str(q))
        self.assertTrue(Path(self.dir, "TRACES", "0001.TXT").exists())
        self.assertEqual(Path(self.dir, "STATE.TXT").read_text(),
                         "next=1\ntraces=1\npending=\n")
        self.run_cli("queue", self.dir, str(q), "--reset-traces")
        self.assertFalse(Path(self.dir, "TRACES", "0001.TXT").exists())


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell is not installed")
class WindowsReader(unittest.TestCase):
    def test_format_matches(self):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d, "r.bin")
            raw.write_bytes(record())
            script = (ROOT / "tools/windows/read-boottrace.ps1").read_text()
            # Load only the formatter; the P/Invoke path needs Windows.
            body = script[script.index("function Get-CString"):script.index(
                "[DaemonarchyFirmware]::EnablePrivilege()")]
            body = "$VarName = 'DaemonarchyBootTrace'\n" + body + \
                f"\nFormat-BootTrace ([IO.File]::ReadAllBytes('{raw}'))\n"
            out = subprocess.run(["pwsh", "-NoProfile", "-Command", body],
                                 capture_output=True, text=True, check=True).stdout
            self.assertIn("Last step: #42 1.250s cpu1 attach: attach atrtc0", out)
            self.assertIn("[sub 0x3800000 order 0x0]", out)
            self.assertIn("Couldn't map I/O", out)
            self.assertIn("200 KiB, 12 KiB written", out)
            self.assertIn("Persisted: coarse steps only", out)


if __name__ == "__main__":
    unittest.main()
