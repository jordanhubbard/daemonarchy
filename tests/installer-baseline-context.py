#!/usr/bin/env python3
"""Portable retained-context controls; they perform no native authentication."""

import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "installer_baseline_context", ROOT / "scripts/installer-baseline-context.py"
)
context_builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context_builder)
IDENTITY = "sha256:" + "a" * 64


def target(link=1000, state="measured"):
    return {
        "schema": context_builder.TARGET_SCHEMA,
        "release": "1.4.0",
        "target": {
            "kind": "virtual", "machine_class": "qemu-kvm",
            "worker_id": "fixture-worker", "worker_identity": IDENTITY,
            "storage": "raw-zfs", "link_mbps": link,
            "link_measurement": state, "cache_mode": "network",
        },
    }


class BaselineContext(unittest.TestCase):
    def database(self, path, rows):
        database = sqlite3.connect(path)
        database.execute(
            "create table packages(name text,version text,arch text,origin text,"
            "pkgsize integer,flatsize integer,cksum text,path text)"
        )
        database.executemany("insert into packages values(?,?,?,?,?,?,?,?)", rows)
        database.commit()
        database.close()

    def fixture(self, root, *, duplicate=False, link=1000, state="measured"):
        image = root / "image.iso"
        image.write_bytes(b"exact image")
        manifest = root / "installed.txt"
        manifest.write_text(
            "FreeBSD fixture\n-- packages --\n"
            "a 1 FreeBSD:16:amd64 devel/a FreeBSD 100\n"
            "b 2 FreeBSD:16:amd64 devel/b Daemonarchy 200\n"
        )
        target_path = root / "target.json"
        target_path.write_text(json.dumps(target(link, state)))
        first = root / "first.sqlite"
        second = root / "second.sqlite"
        self.database(first, [
            ("a", "1", "FreeBSD:16:amd64", "devel/a", 10, 100, "sum-a", "All/a.pkg"),
        ])
        b_size = 21 if duplicate else 20
        self.database(second, [
            ("b", "2", "FreeBSD:16:amd64", "devel/b", b_size, 200, "sum-b", "All/b.pkg"),
        ])
        archive = root / "evidence.tar"
        with tarfile.open(archive, "w") as retained:
            retained.add(first, "var/db/pkg/repos/FreeBSD/db")
            retained.add(second, "var/db/pkg/repos/Daemonarchy/db")
            if duplicate:
                retained.add(second, "var/db/pkg/repos/Daemonarchy-Dependencies/db")
        return image, archive, manifest, target_path

    def packagesite(self, root, row):
        path = root / "packagesite.pkg"
        payload = (json.dumps(row, separators=(",", ":")) + "\n").encode()
        with tarfile.open(path, "w:xz") as retained:
            member = tarfile.TarInfo("packagesite.yaml")
            member.size = len(payload)
            retained.addfile(member, io.BytesIO(payload))
        return path

    def test_exact_image_catalogues_and_selection_are_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs = self.fixture(Path(temporary))
            inventory, context = context_builder.build(*inputs)
            self.assertEqual(inventory["package_count"], 2)
            self.assertEqual(inventory["download_bytes"], 30)
            self.assertEqual(inventory["installed_bytes"], 300)
            self.assertEqual(context["selection"]["identity"], inventory["identity"])
            self.assertEqual(context["image"]["size_bytes"], len(b"exact image"))
            self.assertEqual(inventory["packages"][1]["archive_path"], "All/b.pkg")

    def test_unknown_link_is_explicit_and_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            inputs = self.fixture(Path(temporary), link=None, state="unknown")
            _, context = context_builder.build(*inputs)
            self.assertIsNone(context["target"]["link_mbps"])
            self.assertEqual(context["target"]["link_measurement"], "unknown")

    def test_iso_packagesite_supplies_immutable_local_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = list(self.fixture(root))
            inputs[2].write_text(
                "-- packages --\nlocal 3 FreeBSD:16:amd64 devel/local Daemonarchy 300\n"
            )
            catalogue = self.packagesite(root, {
                "name": "local", "version": "3", "abi": "FreeBSD:16:amd64",
                "origin": "devel/local", "pkgsize": 30, "flatsize": 300,
                "sum": "native-sum", "repopath": "All/local.pkg",
            })
            inventory, _ = context_builder.build(*inputs, [f"ISO={catalogue}"])
            self.assertEqual(inventory["packages"][0]["source_catalogues"], ["ISO"])
            self.assertEqual(inventory["catalogue_databases"][2]["format"],
                             "packagesite.pkg")

    def test_install_time_catalogue_replaces_refreshed_same_id_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = list(self.fixture(root))
            inputs[2].write_text(
                "-- packages --\nb 3 FreeBSD:16:amd64 devel/b Daemonarchy 300\n"
            )
            catalogue = self.packagesite(root, {
                "name": "b", "version": "3", "abi": "FreeBSD:16:amd64",
                "origin": "devel/b", "pkgsize": 30, "flatsize": 300,
                "sum": "install-time-sum", "repopath": "All/b-3.pkg",
            })
            inventory, _ = context_builder.build(
                *inputs, [], [f"Daemonarchy={catalogue}"], []
            )
            self.assertEqual(inventory["package_count"], 1)
            self.assertEqual(inventory["packages"][0]["archive_checksum"],
                             "install-time-sum")
            daemonarchy = [row for row in inventory["catalogue_databases"]
                           if row["repository"] == "Daemonarchy"]
            self.assertEqual([row["format"] for row in daemonarchy],
                             ["packagesite.pkg"])

    def test_reviewed_repository_annotation_alias_selects_original_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = list(self.fixture(root))
            inputs[2].write_text(
                "-- packages --\na 1 FreeBSD:16:amd64 devel/a Relabelled 100\n"
            )
            inventory, _ = context_builder.build(
                *inputs, [], [], ["Relabelled=FreeBSD"]
            )
            self.assertEqual(inventory["packages"][0]["source_catalogues"],
                             ["FreeBSD"])
            self.assertEqual(inventory["repository_aliases"],
                             {"Relabelled": ["FreeBSD"]})

    def test_missing_ambiguous_and_duplicate_inputs_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = list(self.fixture(root))
            inputs[2].write_text(
                "-- packages --\na 1 FreeBSD:16:amd64 devel/a FreeBSD 100\n"
                "missing 1 FreeBSD:16:amd64 devel/m FreeBSD 1\n"
            )
            with self.assertRaisesRegex(ValueError, "absent"):
                context_builder.build(*inputs)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = list(self.fixture(root))
            inputs[2].write_text(
                "-- packages --\na 1 FreeBSD:16:amd64 devel/a FreeBSD 100\n"
                "a 1 FreeBSD:16:amd64 devel/a FreeBSD 100\n"
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                context_builder.build(*inputs)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalogue = self.packagesite(root, {
                "name": "escape", "version": "1", "abi": "FreeBSD:16:amd64",
                "origin": "devel/escape", "pkgsize": 1, "flatsize": 1,
                "sum": "native-sum", "repopath": "All/../escape.pkg",
            })
            with self.assertRaisesRegex(ValueError, "unsafe"):
                context_builder.package_catalogue(f"ISO={catalogue}")

    def test_redirected_database_and_existing_outputs_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = list(self.fixture(root))
            with tarfile.open(inputs[1], "w") as retained:
                member = tarfile.TarInfo("var/db/pkg/repos/FreeBSD/db")
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
                retained.addfile(member)
            with self.assertRaisesRegex(ValueError, "redirected"):
                context_builder.build(*inputs)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = self.fixture(root)
            inventory = root / "inventory.json"
            context = root / "context.json"
            inventory.write_text("occupied")
            with self.assertRaisesRegex(ValueError, "output already exists"):
                context_builder.main([
                    "--image", str(inputs[0]), "--package-evidence", str(inputs[1]),
                    "--installed-manifest", str(inputs[2]), "--target", str(inputs[3]),
                    "--inventory-output", str(inventory), "--context-output", str(context),
                ])


if __name__ == "__main__":
    unittest.main()
