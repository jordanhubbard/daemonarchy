#!/usr/bin/env python3
"""The mirror plan follows catalogue priority, reports gaps and respects shard limits."""

import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("plan", Path(__file__).resolve().parents[1] / "scripts/package-mirror-plan.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def pkg(name, size, deps=(), licences=("MIT",)):
    return {"name": name, "pkgsize": size, "flatsize": size * 3,
            "deps": {d: {} for d in deps}, "licenses": list(licences)}


OWN = {"app": pkg("app", 10, ["lib", "tool"]), "tool": pkg("tool", 5)}
UPSTREAM = {"lib": pkg("lib", 100, ["base"]), "base": pkg("base", 200, licences=("BSD2CLAUSE",)),
            "tool": pkg("tool", 999), "unused": pkg("unused", 1)}


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.result = tool.plan(["app"], {"Own": OWN, "FreeBSD": UPSTREAM})

    def test_closure_and_priority(self):
        self.assertEqual(self.result["closure_packages"], 4)
        self.assertEqual(self.result["by_source"]["Own"]["packages"], 2)   # tool comes from Own, not FreeBSD
        self.assertEqual(self.result["by_source"]["FreeBSD"]["archive_bytes"], 300)

    def test_hosted_shard_covers_only_upstream_packages(self):
        self.assertEqual(self.result["shards"], [{"assets": 2, "bytes": 300}])

    def test_unsatisfied_root_is_reported(self):
        result = tool.plan(["app", "chromium"], {"Own": OWN, "FreeBSD": UPSTREAM})
        self.assertEqual(result["unsatisfied"], ["chromium"])

    def test_licences_counted(self):
        self.assertEqual(self.result["licences"], {"MIT": 3, "BSD2CLAUSE": 1})

    def test_shards_split_at_asset_limit(self):
        entries = [pkg(f"p{i}", 1) for i in range(tool.MAX_ASSETS + 1)]
        bins = tool.shards(entries)
        self.assertEqual([b["assets"] for b in bins], [tool.MAX_ASSETS, 1])


class DriftExitTests(unittest.TestCase):
    def catalogue(self, directory, name, packages):
        import subprocess
        site = Path(directory) / "packagesite.yaml"
        site.write_text("\n".join(json.dumps(p) for p in packages) + "\n")
        out = Path(directory) / name
        subprocess.run(["tar", "-cf", str(out), "-C", directory, "packagesite.yaml"], check=True)
        return out

    def test_fail_on_unsatisfied_reports_missing_dependency(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            own = self.catalogue(tmp, "own.pkg", [pkg("app", 10, ["gone"])])
            args = ["--root", "app", "--catalogue", f"Own={own}"]
            self.assertEqual(tool.main(args), 0)
            self.assertEqual(tool.main([*args, "--fail-on-unsatisfied"]), 1)
            ok = self.catalogue(tmp, "ok.pkg", [pkg("app", 10)])
            self.assertEqual(tool.main(["--root", "app", "--catalogue", f"Own={ok}", "--fail-on-unsatisfied"]), 0)


if __name__ == "__main__":
    unittest.main()
