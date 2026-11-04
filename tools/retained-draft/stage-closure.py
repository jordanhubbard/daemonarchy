#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""DRAFT: copy the observed closure into the untracked closure/ staging directory.

Reads closure-inventory.json (see closure-inventory.py), copies each tool, library and
data tree to closure/<role>/{bin,lib,<dest>} under the project root, and verifies every
copied file against the inventory digest.  It refuses to overwrite a file whose bytes
differ.  It runs nothing it copies and changes nothing outside closure/.

    python3.12 stage-closure.py --inventory closure-inventory.json --root .
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def put(src, dst, digest, mode):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if sha256_file(dst) != digest:
            raise SystemExit("refusing to overwrite differing file: %s" % dst)
        return
    shutil.copyfile(src, dst)
    os.chmod(dst, mode)
    if sha256_file(dst) != digest:
        raise SystemExit("copy does not match inventory (host file changed?): %s" % src)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    inv = json.loads(Path(args.inventory).read_text())
    if inv["problems"]:
        raise SystemExit("inventory has unresolved problems: %s" % inv["problems"])
    root = Path(args.root).resolve() / "closure"
    for t in inv["tools"]:
        put(t["realpath"], root / t["role"] / "bin" / t["name"], t["sha256"], 0o755)
    for lib in inv["libraries"]:
        put(lib["realpath"], root / lib["role"] / "lib" / lib["soname"], lib["sha256"], 0o755)
    for tree in inv["trees"]:
        excluded = set(tree["exclude"])
        dest = root / tree["role"] / tree["dest"]
        for base, dirs, names in os.walk(tree["source"]):
            dirs[:] = sorted(d for d in dirs if d not in excluded)
            rel = os.path.relpath(base, tree["source"])
            for d in dirs:
                (dest / rel / d).mkdir(parents=True, exist_ok=True)
            for n in sorted(names):
                src = Path(base) / n
                out = dest / rel / n
                out.parent.mkdir(parents=True, exist_ok=True)
                # File symlinks are captured as regular files holding the target's bytes
                # (the stdlib links lib-dynload/_sqlite3 into site-packages, which is
                # not captured); os.stat/copyfile follow the link.
                mode = 0o755 if os.stat(src).st_mode & 0o111 else 0o644
                put(src, out, sha256_file(src), mode)
    # Scripts and test fixtures start `python3` through the search path, which holds only the
    # captured directory; give it a relative link (also a manifest symlink, so the dependency
    # observer inspects the native executables instead of walking the whole tree).
    link = root / "toolchain" / "bin" / "python3"
    if not link.is_symlink():
        os.symlink("python3.12", link)
    # `python -I` ignores PYTHONDONTWRITEBYTECODE, but `site` still imports sitecustomize from the
    # captured prefix: a child interpreter started by a test then cannot write .pyc files into the
    # frozen snapshot either.
    for pydir in sorted((root / "toolchain" / "lib").glob("python3.*")):
        site = pydir / "site-packages"
        site.mkdir(exist_ok=True)
        (site / "sitecustomize.py").write_text(
            "# Daemonarchy retained closure: never write bytecode into the frozen inputs.\n"
            "import sys\nsys.dont_write_bytecode = True\n")
    # The captured interpreter must not write bytecode into the frozen snapshot (a child
    # `python -I` ignores PYTHONDONTWRITEBYTECODE).  Precompile the staged stdlib with
    # unchecked-hash pycs (never rewritten) and a fixed recorded path, so they are deterministic.
    # -B -f: the interpreter's own startup imports must not leave timestamp pycs that compileall skips.
    lib = root / "toolchain" / "lib"
    for pydir in sorted(lib.glob("python3.*")):
        subprocess.run([str(root / "toolchain" / "bin" / "python3.12"), "-B", "-m", "compileall", "-q", "-f",
                        "--invalidation-mode", "unchecked-hash", "-d", "lib/" + pydir.name,
                        str(pydir)], check=True)
    print(json.dumps({"staged_under": str(root)}))


if __name__ == "__main__":
    sys.exit(main())
