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


def step(seq, index, text, kind=3, ms=None):
    return struct.pack("<IIIIIHH40s", seq, index, 0, 0, index * 10 if ms is None else ms,
                       kind, 0, text)


def loader_rec(**kw):
    f = dict(epoch=77, cycle=2, step=7, flags=0x9, method=1, write_status=0, verify=1,
             next=3, traces=1, pending=2, repeat=0, stick_next=2, stick_traces=0,
             stick_pending=1, text=b"booting 0002")
    f.update(kw)
    return struct.pack("<8s14I64s", b"DBTLDR01", *[f[k] for k in (
        "epoch", "cycle", "step", "flags", "method", "write_status", "verify", "next",
        "traces", "pending", "repeat", "stick_next", "stick_traces", "stick_pending")],
        f["text"])


def var_store(entries):
    """An EDK2 authenticated variable store holding (name, state, data)."""
    body = b""
    for name, state, payload in entries:
        n = (name + "\0").encode("utf-16-le")
        hdr = decoder.VAR_HDR.pack(0x55AA, state, 0, 7, 0, bytes(16), 0, len(n),
                                   len(payload), decoder.GUID.bytes_le)
        blob = hdr + n + payload
        body += blob + bytes(-len(blob) % 4)
    return b"\0" * 72 + (decoder.AUTH_VAR_GUID.bytes_le +
                         struct.pack("<I", 28 + len(body) + 64) + bytes(8) + body +
                         b"\xff" * 64)


def record(status=1, flags=0, msgs=b"atrtc0: Warning: Couldn't map I/O.\n"):
    crumbs = [
        struct.pack("<IIHHII76s", 41, 1200, 1, 0, 0x3800000, 0, b"configure_first"),
        struct.pack("<IIHHII76s", 42, 1250, 3, 1, 0, 0,
                    b"attach atrtc0 on isa1 drv atrtc "),
    ]
    header = struct.pack("<8sHHHHIIIIIIIIIIII64s", b"DBTRACE1", 1, 128, 96,
                         len(crumbs), 0, 7, status, flags, 42, 0xFFFFFFFF, len(msgs),
                         1250, 200, 150, 12, 3, b"FreeBSD 16.0-CURRENT #0 test")
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
        self.assertIn("200 KiB, 12 KiB written, 3 breadcrumbs", text)
        self.assertIn("Persisted: coarse before debug.boottrace.from_sub", text)

    def test_breadcrumb_is_newer(self):
        step = struct.pack("<IIIIIHH40s", 9, 57, 0x4800000, 0, 2000, 1, 0, b"initclocks")
        text = decoder.report(decoder.decode(record()), decoder.decode_step(step))
        self.assertIn("Last step: #57 2.000s cpu0 sysinit: initclocks [sub 0x4800000", text)
        self.assertIn("breadcrumb #9; the full record below is from step #42", text)

    def test_ring_sorted_by_sequence(self):
        # Slots hold breadcrumbs 18, 19 and 17 (ring of 3 after wrapping).
        ring = decoder.decode_ring([step(18, 60, b"attach hpet0"),
                                    step(19, 61, b"probe acpi_lid0"),
                                    step(17, 59, b"attach atrtc0"), None, b""])
        self.assertEqual([s["seq"] for s in ring], [17, 18, 19])
        text = decoder.report(decoder.decode(record()), ring)
        self.assertIn("Last step: #61 0.610s cpu0 attach: probe acpi_lid0", text)
        self.assertIn("NVRAM breadcrumb ring, 3 newest (oldest first):\n"
                      "  b17 #59", text)
        self.assertLess(text.index("b18 #60"), text.index("b19 #61"))

    def test_vars_ring_old_single_and_loader(self):
        store = var_store([
            (decoder.VARNAME, 0x3F, record()),
            ("DBTStep00", 0x3C, step(1, 50, b"stale copy")),
            ("DBTStep00", 0x3F, step(3, 52, b"attach c")),
            ("DBTStep01", 0x3F, step(2, 51, b"attach b")),
            ("DBTLoader", 0x3F, loader_rec()),
        ])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "vars.fd")
            path.write_bytes(store)
            out = self.run_main([str(path), "--vars"])
            self.assertIn("Last step: #52", out)
            self.assertIn("NVRAM breadcrumb ring, 2 newest", out)
            self.assertNotIn("stale copy", out)
            self.assertIn("Loader self-report (EFI variable DBTLoader): cycle 2 (epoch 77) "
                          "reached 'booting'; stick via raw blocks (SLOTS.MAP); "
                          "flags running,block-map", out)
            self.assertIn("wrote next=3 traces=1 pending=0002, status 0, read-back ok", out)
            # An old kernel's single DBTStep still decodes.
            path.write_bytes(var_store([(decoder.VARNAME, 0x3F, record()),
                                        ("DBTStep", 0x3F, step(9, 57, b"initclocks", 1))]))
            out = self.run_main([str(path), "--vars"])
            self.assertIn("Last step: #57", out)

    def test_efivarfs_reads_siblings(self):
        g = str(decoder.GUID)
        with tempfile.TemporaryDirectory() as d:
            attr = struct.pack("<I", 7)
            Path(d, f"DaemonarchyBootTrace-{g}").write_bytes(attr + record())
            Path(d, f"DBTStep05-{g}").write_bytes(attr + step(40, 90, b"attach nvme0"))
            Path(d, f"DBTStep06-{g}").write_bytes(attr + step(41, 91, b"probe xhci0"))
            Path(d, f"DBTLoader-{g}").write_bytes(attr + loader_rec(
                flags=0x2, step=8, text=b"STICK WRITES ARE NOT PERSISTING."))
            out = self.run_main([str(Path(d, f"DaemonarchyBootTrace-{g}")), "--efivarfs"])
            self.assertIn("Last step: #91", out)
            self.assertIn("flags NOT-PERSISTING", out)

    def run_main(self, argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            decoder.main(argv)
        return buf.getvalue()

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
        ino = Path(self.dir, "STATE.TXT").stat().st_ino
        self.run_cli("queue", self.dir, str(q))
        state = Path(self.dir, "STATE.TXT").read_text().rstrip("\n")
        self.assertRegex(state, r"^next=1\ntraces=0\npending=\nepoch=\d+$")
        self.assertEqual(Path(self.dir, "STATE.TXT").stat().st_size, stick.STATE_SIZE)
        # Rewritten in place, not replaced (its clusters must not move).
        self.assertEqual(Path(self.dir, "STATE.TXT").stat().st_ino, ino)
        self.assertEqual(Path(self.dir, "TRACES", "0200.TXT").stat().st_size, stick.SLOT_SIZE)
        self.assertIn("hint.hpet.0.disabled=1",
                      Path(self.dir, "QUEUE", "0002.CNF").read_text())
        # A loader-filed trace stays across a requeue unless reset.
        Path(self.dir, "TRACES", "0001.TXT").write_text(
            "experiment: 0001\nStatus: INCOMPLETE: x\nLast step: #3 attach\n")
        Path(self.dir, "STATE.TXT").write_text("next=2\ntraces=1\npending=0001\n")
        self.run_cli("queue", self.dir, str(q))
        self.assertTrue(Path(self.dir, "TRACES", "0001.TXT").exists())
        self.assertRegex(Path(self.dir, "STATE.TXT").read_text().rstrip("\n"),
                         r"^next=1\ntraces=1\npending=\nepoch=\d+$")
        self.run_cli("queue", self.dir, str(q), "--reset-traces")
        self.assertTrue(Path(self.dir, "TRACES", "0001.TXT").read_bytes().startswith(stick.EMPTY))
        self.assertEqual(Path(self.dir, "TRACES", "0001.TXT").stat().st_size, stick.SLOT_SIZE)


    def test_summarize_old_and_new_traces(self):
        old = ("Daemonarchy hardware trace 0001\nexperiment: 0001\nnvram: write #3\n\n"
               "Status: INCOMPLETE: x\nLast step: #3 attach\nRecent steps (oldest first):\n"
               "  #3 attach\n")
        self.assertEqual(stick.summarize(old), ("0001", "INCOMPLETE: x", "#3 attach", ""))
        self.assertEqual(stick.ring(old), [])
        new = ("Daemonarchy hardware trace 0002\nexperiment: 0002\n"
               "loader now: cycle 3, stick via raw blocks (SLOTS.MAP) (ok)\n"
               "Status: INCOMPLETE: y\nLast step: #9 probe\n"
               "NVRAM breadcrumb ring, 2 newest (oldest first):\n  b4 #8 attach\n"
               "  b5 #9 probe\nLast kernel messages:\n  z\n")
        self.assertEqual(stick.summarize(new)[3],
                         "cycle 3, stick via raw blocks (SLOTS.MAP) (ok)")
        self.assertEqual(stick.ring(new), ["b4 #8 attach", "b5 #9 probe"])

    def test_parse_map(self):
        files = [("STATE.TXT", 8192, 512), ("TRACES/0001.TXT", 16384, 16384)]
        text = stick.make_map(2048, 4096, 4096, files)
        m = stick.parse_map(text + "\n" * 100)
        self.assertEqual(m["files"]["TRACES/0001.TXT"], (16384, 16384))
        bad = [text.replace("part_lba=2048", "part_lba=2049"),          # checksum
               stick.make_map(2048, 4096, 4096, files + [("X", 8192, 512)]),  # overlap
               stick.make_map(2048, 4096, 4096, [("X", 8193, 512)]),     # unaligned
               stick.make_map(2048, 20, 4096, [("X", 8192, 4096)]),      # outside
               stick.make_map(2048, 4096, 4096, [("X", 2048, 512)]),     # metadata
               stick.make_map(2048, 4096, 4096, [])]
        for b in bad:
            with self.assertRaises(ValueError, msg=b):
                stick.parse_map(b)


@unittest.skipUnless(all(shutil.which(t) for t in ("sgdisk", "mkfs.fat", "mcopy")),
                     "sgdisk, mkfs.fat and mtools are needed")
class BlockMap(unittest.TestCase):
    """SLOTS.MAP on a real FAT32 GPT image, as the loader will use it."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.img = str(Path(self.dir, "stick.img"))
        with open(self.img, "wb") as f:
            f.truncate(1 << 20)
        with contextlib_quiet():
            stick.main(["add-partition", self.img, "--size-mib", "64"])
            stick.main(["init", self.img])

    def raw(self, name):
        m = stick.check_map(self.img)
        off, size = m["files"][name]
        with open(self.img, "rb") as f:
            f.seek(m["part_lba"] * 512 + off)
            return f.read(size)

    def test_map_points_at_the_files(self):
        m = stick.check_map(self.img)
        _, first, count = stick.gpt_partition(self.img)
        self.assertEqual((m["part_lba"], m["part_sectors"]), (first, count))
        self.assertEqual(len(m["files"]), 1 + stick.SLOTS)
        vol = stick.Volume(self.img)
        self.assertEqual(self.raw("STATE.TXT"), vol.read("STATE.TXT"))
        self.assertEqual(self.raw("TRACES/0200.TXT"), vol.read("TRACES/0200.TXT"))
        self.assertTrue(self.raw("TRACES/0007.TXT").startswith(stick.EMPTY))

    def test_queue_rewrites_in_place(self):
        before = stick.check_map(self.img)
        q = Path(self.dir, "q.txt")
        q.write_text("[one]\nread-conf /boot/d/1\n")
        with contextlib_quiet():
            stick.main(["queue", self.img, str(q)])
        self.assertEqual(stick.check_map(self.img), before)
        state = self.raw("STATE.TXT")
        self.assertRegex(state.decode(), r"^next=1\ntraces=0\npending=\nepoch=\d+\n")
        self.assertEqual(stick.Volume(self.img).read("STATE.TXT"), state)
        # What the loader writes raw, mtools (any FAT reader) sees.
        m = stick.check_map(self.img)
        off, size = m["files"]["TRACES/0001.TXT"]
        with open(self.img, "r+b") as f:
            f.seek(m["part_lba"] * 512 + off)
            f.write(stick.padded(b"Daemonarchy hardware trace 0001\n", size))
        self.assertTrue(stick.Volume(self.img).read("TRACES/0001.TXT").startswith(
            b"Daemonarchy hardware trace 0001\n"))

    def test_corrupt_map_is_rejected_and_rewritten(self):
        m = stick.check_map(self.img)
        fat = stick.Fat32(open(self.img, "rb"), m["part_lba"] * 512)
        off, _ = fat.extent(stick.MAP_NAME)
        with open(self.img, "r+b") as f:
            f.seek(m["part_lba"] * 512 + off + 60)
            f.write(b"9")
        with self.assertRaises(ValueError):
            stick.check_map(self.img)
        with self.assertRaises(SystemExit):
            stick.Volume(self.img)
        with contextlib_quiet():
            stick.main(["write-map", self.img])
        stick.check_map(self.img)

    def test_fragmented_file_is_refused(self):
        spec = "%s@@%d" % (self.img, stick.gpt_partition(self.img)[1] * 512)
        env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
        big = Path(self.dir, "c")
        big.write_bytes(b"c" * 8192)
        subprocess.run(["mcopy", "-i", spec, str(big), "::/C"], check=True, env=env,
                       capture_output=True)
        part = stick.gpt_partition(self.img)[1] * 512
        with open(self.img, "rb") as f:
            fat = stick.Fat32(f, part)
            fat.extent("C")
            first = fat.lookup("C")[0]
            at = part + fat.reserved * fat.bps + first * 4
        # Skip one cluster: C now jumps from its first cluster to its third.
        with open(self.img, "r+b") as f:
            f.seek(at)
            f.write(struct.pack("<I", first + 2))
        with open(self.img, "rb") as f:
            with self.assertRaisesRegex(ValueError, "not contiguous"):
                stick.Fat32(f, part).extent("C")


def contextlib_quiet():
    import contextlib
    import io
    return contextlib.redirect_stdout(io.StringIO())


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
                f"\nFormat-BootTrace ([IO.File]::ReadAllBytes('{raw}')) $null\n"
            out = subprocess.run(["pwsh", "-NoProfile", "-Command", body],
                                 capture_output=True, text=True, check=True).stdout
            self.assertIn("Last step: #42 1.250s cpu1 attach: attach atrtc0", out)
            self.assertIn("[sub 0x3800000 order 0x0]", out)
            self.assertIn("Couldn't map I/O", out)
            self.assertIn("200 KiB, 12 KiB written, 3 breadcrumbs", out)
            self.assertIn("Persisted: coarse before debug.boottrace.from_sub", out)

    def test_ring(self):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d, "r.bin")
            raw.write_bytes(record())
            slots = []
            for i, (seq, idx, text) in enumerate(((8, 70, b"attach b"), (9, 71, b"probe c"),
                                                  (7, 69, b"attach a"))):
                Path(d, f"s{i}.bin").write_bytes(step(seq, idx, text))
                slots.append(f"[IO.File]::ReadAllBytes('{Path(d, f's{i}.bin')}')")
            script = (ROOT / "tools/windows/read-boottrace.ps1").read_text()
            body = script[script.index("function Get-CString"):script.index(
                "[DaemonarchyFirmware]::EnablePrivilege()")]
            body = "$VarName = 'DaemonarchyBootTrace'\n" + body + \
                f"\n$slots = @({', '.join(slots)}, $null)\n$ring = Sort-Ring $slots\n" \
                f"Format-BootTrace ([IO.File]::ReadAllBytes('{raw}')) $null $ring\n"
            out = subprocess.run(["pwsh", "-NoProfile", "-Command", body],
                                 capture_output=True, text=True, check=True).stdout
            self.assertIn("Last step: #71 0.710s cpu0 attach: probe c", out)
            self.assertIn("NVRAM breadcrumb ring, 3 newest (oldest first):", out)
            self.assertLess(out.index("b7 #69"), out.index("b9 #71"))


if __name__ == "__main__":
    unittest.main()
