#!/usr/bin/env python3
"""build-timing-record turns a pipeline's step markers into a labelled baseline record."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/build-timing"
loader = importlib.machinery.SourceFileLoader("record", str(ROOT / "scripts/build-timing-record.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
tool = importlib.util.module_from_spec(spec)
loader.exec_module(tool)


class Record(unittest.TestCase):
    def args(self, *extra):
        return tool.argparse.Namespace(label="rev2", host="daemon.local", revision="303b364", jobs=8, ncpu=8, incremental="yes",
                                       world_log=str(FIXTURES / "rev2-world-tail.txt"), note=["a note"], extra=list(extra))

    def record(self, *extra):
        return tool.build_record((FIXTURES / "rev2-pipeline.out").read_text(), self.args(*extra))

    def test_each_step_lasts_until_the_next_marker(self):
        seconds = {s["step"]: s.get("seconds") for s in self.record()["steps"]}
        self.assertEqual(seconds["source"], 51)
        self.assertEqual(seconds["world"], 878)          # 06:26:20 -> 06:40:58
        self.assertEqual(seconds["kernel"], 622)
        self.assertEqual(seconds["sets"], 601)
        self.assertEqual(seconds["jail"], 154)
        self.assertEqual(seconds["secureboot-build"], 442)
        self.assertEqual(seconds["checkout"], 387)
        self.assertIsNone(seconds["done-pipeline"])     # nothing follows the last marker

    def test_total_exit_world_log_and_limits(self):
        record = self.record()
        self.assertEqual(record["total_seconds"], 3518)  # 06:25:29 -> 07:24:07
        self.assertEqual((record["pipeline_exit"], record["world_build_seconds"], record["schema"]), (0, 874, tool.SCHEMA))
        self.assertTrue(any("Incremental" in limit for limit in record["limits"]))
        self.assertTrue(any("One run on one machine" in limit for limit in record["limits"]))

    def test_separate_phases_are_timed(self):
        record = self.record("iso-build=2026-10-30T05:27:23Z,2026-10-30T05:54:04Z")
        self.assertEqual(record["separate_phases"], [{"step": "iso-build", "start": "2026-10-30T05:27:23Z",
                                                      "end": "2026-10-30T05:54:04Z", "seconds": 1601}])

    def test_clean_build_carries_no_incremental_caveat(self):
        args = self.args()
        args.incremental = "no"
        record = tool.build_record((FIXTURES / "rev2-pipeline.out").read_text(), args)
        self.assertFalse(any("Incremental" in limit for limit in record["limits"]))

    def test_output_without_markers_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "empty.out"
            out.write_text("nothing here\n")
            self.assertEqual(tool.main([str(out), "--label", "x", "--host", "h", "--revision", "r", "--jobs", "1"]), 1)


if __name__ == "__main__":
    unittest.main()
