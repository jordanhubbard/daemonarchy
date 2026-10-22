#!/usr/bin/env python3
"""Pinned catalogue closure, conflict, mutation and CLI refusal checks."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/package-dag.py"
spec = importlib.util.spec_from_file_location("package_dag", SCRIPT)
dag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dag)


def package(name, dependencies=(), version="1.0", origin=None):
    return dict(name=name, version=version, origin=origin or f"misc/{name}",
                abi="FreeBSD:16:amd64", sum="a" * 64, repopath=f"All/{name}-{version}.pkg",
                pkgsize=10, flatsize=100,
                deps={n: dict(origin=f"misc/{n}", version="1.0") for n in dependencies},
                annotations={"flavor": "default", "FreeBSD_version": "1600028"})


class PackageGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.selection = self.root / "selection.json"
        self.rows = [package("desktop", ("left", "right")), package("left", ("shared",)),
                     package("right", ("shared",)), package("shared"), package("gpu")]
        self.config = dict(schema=dag.SELECTION_SCHEMA, abi="FreeBSD:16:amd64", osversion=1600028, catalogues=[],
                           selections={"default": ["desktop"], "gpu": ["desktop", "gpu"]})
        self.catalogue("release", self.rows)

    def catalogue(self, name, rows):
        path = self.root / f"{name}.jsonl"
        data = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
        path.write_bytes(data)
        self.config["catalogues"] = [c for c in self.config["catalogues"] if c["id"] != name]
        self.config["catalogues"].append(dict(id=name, path=path.name,
                                              sha256=dag.digest(data), url=f"https://example.invalid/{name}"))

    def save(self):
        data = json.dumps(self.config).encode()
        self.selection.write_bytes(data)
        return dag.digest(data)

    def collect(self):
        return dag.collect(self.selection, self.save())

    def test_diamond_is_complete_deduplicated_and_dependency_first(self):
        report = self.collect()
        graph = report["selections"]["default"]
        self.assertEqual(graph["packages"], ["desktop", "left", "right", "shared"])
        self.assertEqual(graph["dependency_first_order"], ["shared", "left", "right", "desktop"])
        self.assertEqual(len(graph["edges"]), 4)
        self.assertEqual((graph["download_bytes"], graph["installed_bytes"]), (40, 400))
        self.assertEqual(report["selections"]["gpu"]["download_bytes"], 50)
        self.assertFalse(report["installation_authorized"])
        self.assertFalse(report["native_solver_qualified"])
        self.assertEqual(report["packages"]["shared"]["annotations"]["flavor"], "default")
        self.assertEqual(report["packages"]["shared"]["repository"], "release")

    def test_deterministic_catalogue_order_and_unused_entries(self):
        first = self.collect()
        self.catalogue("release", list(reversed(self.rows)) + [package("unused")])
        second = self.collect()
        self.assertEqual(first["packages"], second["packages"])
        self.assertEqual(first["selections"], second["selections"])
        self.assertNotEqual(first["catalogues"], second["catalogues"])

    def test_missing_transitive_dependency_refuses(self):
        self.catalogue("release", [r for r in self.rows if r["name"] != "shared"])
        with self.assertRaisesRegex(ValueError, "missing dependency"):
            self.collect()

    def test_cycle_refuses(self):
        self.rows[-2]["deps"] = {"desktop": dict(origin="misc/desktop", version="1.0")}
        self.catalogue("release", self.rows)
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            self.collect()

    def test_dependency_origin_mismatch_refuses(self):
        self.rows[-2]["origin"] = "other/shared"
        self.catalogue("release", self.rows)
        with self.assertRaisesRegex(ValueError, "origin conflict"):
            self.collect()

    def test_recorded_older_dependency_is_retained_as_unresolved(self):
        self.rows[-2]["version"] = "2.0,1"
        self.catalogue("release", self.rows)
        graph = self.collect()["selections"]["default"]
        self.assertEqual(len(graph["version_resolution_required"]), 2)
        self.assertEqual(graph["version_resolution_required"][0]["selected_version"], "2.0,1")

    def test_cross_repository_overlap_requires_explicit_binding(self):
        override = package("shared", version="2.0")
        self.catalogue("official", [override])
        with self.assertRaisesRegex(ValueError, "repository binding required"):
            self.collect()
        self.config["repositories"] = {"shared": "official"}
        self.assertEqual(self.collect()["packages"]["shared"]["repository"], "official")
        self.config["repositories"] = {"shared": "missing"}
        with self.assertRaises(ValueError):
            self.collect()

    def test_duplicate_record_refuses_even_if_identical(self):
        self.catalogue("release", self.rows + [self.rows[0]])
        with self.assertRaisesRegex(ValueError, "ambiguous package"):
            self.collect()

    def test_catalogue_mutation_refuses(self):
        pin = self.save()
        with (self.root / "release.jsonl").open("ab") as stream:
            stream.write(b"\n")
        with self.assertRaisesRegex(ValueError, "digest changed"):
            dag.collect(self.selection, pin)

    def test_selection_mutation_refuses(self):
        pin = self.save()
        self.selection.write_text("{}")
        with self.assertRaisesRegex(ValueError, "digest changed"):
            dag.collect(self.selection, pin)

    def test_invalid_package_metadata_refuses(self):
        for field, values in {"sum": [None, "b" * 63], "pkgsize": [-1, True, 1.5],
                              "flatsize": [None, 2**64], "abi": ["FreeBSD:15:amd64", "FreeBSD:16:aarch64"],
                              "repopath": ["../escape.pkg", "/absolute.pkg", "All/%2e%2e.pkg", "All/a.pkg?x", "All/./x.pkg"],
                              "deps": [[], {"shared": []}]}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    rows = copy.deepcopy(self.rows)
                    rows[0][field] = value
                    self.catalogue("release", rows)
                    with self.assertRaises((ValueError, TypeError)):
                        self.collect()

    def test_architecture_independent_package(self):
        self.rows[-1]["abi"] = "FreeBSD:16:*"
        self.rows[-1]["annotations"] = {}
        self.catalogue("release", self.rows)
        self.assertEqual(self.collect()["packages"]["gpu"]["abi"], "FreeBSD:16:*")

    def test_newer_or_unknown_native_osversion_refuses(self):
        for required in (None, "1600029", "invalid", 1600028):
            with self.subTest(required=required):
                self.rows[0]["annotations"] = {} if required is None else {"FreeBSD_version": required}
                self.catalogue("release", self.rows)
                with self.assertRaisesRegex(ValueError, "FreeBSD_version"):
                    self.collect()

    def test_target_osversion_matches_abi(self):
        for target in (True, 1500028, "1600028", -1):
            with self.subTest(target=target):
                self.config["osversion"] = target
                with self.assertRaisesRegex(ValueError, "OSVERSION"):
                    self.collect()

    def test_native_solver_constraints_remain_visible(self):
        self.rows[0].update(dep_formula="shared >= 1.0", conflicts=["alternate-*"],
                            shlibs_required=["libshared.so.1"], options={"X11": "on"})
        self.catalogue("release", self.rows)
        report = self.collect()
        self.assertEqual(report["packages"]["desktop"]["native_constraints"],
                         {k: self.rows[0][k] for k in ("dep_formula", "conflicts", "shlibs_required", "options")})
        self.assertFalse(report["native_solver_qualified"])

    def test_actual_native_catalogue_checksum_is_preserved_without_relabeling(self):
        checksum = '2$jn8h7m3joqhg8nukwytbh8fsymbg7wtwpwsiz9pcy6e39dymphje4ba88tetjf7aewat3ubb8a8jxfb7494amyu1hrmuf5bz8phjtab'
        self.rows[0]["sum"] = checksum
        self.catalogue("release", self.rows)
        row = self.collect()["packages"]["desktop"]
        self.assertEqual(row["archive_checksum"], dict(format="pkg-file-checksum", value=checksum))
        self.assertNotIn("sha256", row)
        for value in ['2$short', '2$' + 'a' * 102, '2$' + '!' * 103, 'type$' + 'a' * 103]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                dag.archive_checksum(value)

    def test_missing_roots_and_empty_selection_refuse(self):
        for roots in ([], ["missing"], "desktop", [None]):
            with self.subTest(roots=roots):
                self.config["selections"]["default"] = roots
                with self.assertRaises(ValueError):
                    self.collect()

    def test_credential_and_ambiguous_repositories_refuse(self):
        self.config["catalogues"][0]["url"] = "https://user:secret@example.invalid/"
        with self.assertRaisesRegex(ValueError, "credentials"):
            self.collect()
        self.config["catalogues"][0]["url"] = "https://example.invalid/"
        self.config["catalogues"].append(copy.deepcopy(self.config["catalogues"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate repository"):
            self.collect()

    def test_duplicate_json_keys_and_nonfinite_values_refuse(self):
        for data in (b'{"name":"a","name":"b"}', b'{"size":NaN}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                dag.decode(data)

    def test_symlink_and_byte_budget_refuse(self):
        pin = self.save()
        link = self.root / "link.json"
        link.symlink_to(self.selection)
        with self.assertRaises(OSError):
            dag.read_pinned(link, pin, dag.MAX_LINE)
        with self.assertRaisesRegex(ValueError, "byte budget"):
            dag.read_pinned(self.selection, pin, 1)

    def test_fifo_refuses_without_waiting_for_a_writer(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "regular file"):
            dag.read_pinned(fifo, "a" * 64, 100)

    def test_deep_dependency_chain_does_not_recurse(self):
        rows = [package(f"p{i}", (f"p{i+1}",)) for i in range(1500)] + [package("p1500")]
        self.catalogue("release", rows)
        self.config["selections"] = {"deep": ["p0"]}
        self.assertEqual(len(self.collect()["selections"]["deep"]["packages"]), 1501)

    def test_cli_preserves_previous_output_and_writes_nothing_on_refusal(self):
        pin = self.save()
        output = self.root / "graph.json"
        command = [sys.executable, str(SCRIPT), str(self.selection), "--sha256", pin, "--output", str(output)]
        subprocess.run(command, check=True, capture_output=True)
        saved = output.read_bytes()
        result = subprocess.run(command, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), saved)
        output.unlink()
        self.selection.write_text("{}")
        result = subprocess.run(command, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
