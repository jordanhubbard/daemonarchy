#!/usr/bin/env bash
# resign-boot-bundle.sh rebundle: a new release label over an already signed boot tree, one signature, nothing else.
# secureboot/bundle.py and maintenance.py are replaced by small stand-ins, so this checks the script's own logic
# (preconditions, refusals, the only-the-label-changed check) on any machine, with no key and no FreeBSD builder.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
script=$here/scripts/resign-boot-bundle.sh
bash -n "$script"
work=$(mktemp -d)
trap '[ -n "${KEEP:-}" ] || rm -rf "$work"' EXIT
S=$work/sb16
P=$S/product/secureboot
mkdir -p "$P" "$S/build" "$S/boot-tree/boot/lua" "$S/boot-tree/usr/local/sbin"
echo '{}' >"$S/build/build.json"
printf 'cert\n' >"$work/cert.pem"; printf 'key\n' >"$work/key"; chmod 600 "$work/key"
for f in boot/loader.efi boot/manifest boot/manifest.sig boot/lua/brand.lua usr/local/sbin/tool; do echo "$f v1" >"$S/boot-tree/$f"; done

cat >"$P/bundle.py" <<'PY'
import argparse, hashlib, io, json, os, tarfile
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("root", type=Path); ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--release", required=True); ap.add_argument("--build-receipt"); ap.add_argument("--certificate"); ap.add_argument("--key", type=Path, required=True)
a = ap.parse_args()
sha = lambda b: hashlib.sha256(b).hexdigest()
names = sorted(str(p.relative_to(a.root)) for p in a.root.rglob("*") if p.is_file())
meta = {"release": a.release, "base_source": "x", "files": {n: sha((a.root / n).read_bytes()) for n in names}}
with tarfile.open(a.out, "w:xz") as t:
    data = json.dumps(meta).encode(); i = tarfile.TarInfo("bundle.json"); i.size = len(data); t.addfile(i, io.BytesIO(data))
    for n in names:
        data = (a.root / n).read_bytes()
        if os.environ.get("STUB_TAMPER") and n == "boot/loader.efi": data += b"tampered"
        i = tarfile.TarInfo(n); i.size = len(data); t.addfile(i, io.BytesIO(data))
Path(str(a.out) + ".sig").write_text("sig:" + sha(a.out.read_bytes()) + ":" + sha(a.key.read_bytes()) + "\n")
PY
cat >"$P/maintenance.py" <<'PY'
import argparse, hashlib, json, sys, tarfile
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("bundle", type=Path)
ap.add_argument("--signature", type=Path); ap.add_argument("--certificate"); ap.add_argument("--root", type=Path)
a = ap.parse_args()
sha = lambda b: hashlib.sha256(b).hexdigest()
if not a.signature.read_text().startswith("sig:" + sha(a.bundle.read_bytes()) + ":"): sys.exit("Signature does not verify")
with tarfile.open(a.bundle) as t: meta = json.load(t.extractfile("bundle.json"))
for n, h in meta["files"].items():
    if sha((a.root / n).read_bytes()) != h: sys.exit(f"Managed boot file mismatch: {n}")
PY

run() { S=$S PY=python3 CERT=$work/cert.pem KEY=${KEY:-$work/key} "$@" bash "$script" rebundle; }
fail() { echo "FAIL: $*" >&2; exit 1; }
sums() { (cd "$S" && ls | sort | grep -E 'boot\.txz' | while read -r f; do printf '%s %s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "$f"; done); }

# The prior bundle (release 1.4.2) and the tree belong together.
python3 "$P/bundle.py" "$S/boot-tree" --out "$S/daemonarchy-1.4.2-boot.txz" --release 1.4.2 --key "$work/key"
before=$(sums)

# 1. Happy path: a new label, the prior untouched, no leftovers.
out=$(run env PRIOR=$S/daemonarchy-1.4.2-boot.txz RELEASE=1.5.0 2>&1) || fail "rebundle did not succeed: $out"
[[ $out == *"only bundle.json differs, and only in release"* ]] || fail "no confirmation line: $out"
[[ -f $S/daemonarchy-1.5.0-boot.txz && -f $S/daemonarchy-1.5.0-boot.txz.sig ]] || fail "new bundle or signature missing"
[[ ! -e $S/daemonarchy-1.5.0-boot.txz.new && ! -e $S/daemonarchy-1.5.0-boot.txz.new.sig ]] || fail "leftover .new files"
[[ $(sums | grep 1.4.2) == $(grep 1.4.2 <<<"$before") ]] || fail "the prior bundle changed"
python3 - "$S/daemonarchy-1.5.0-boot.txz" <<'PY'
import json, sys, tarfile
with tarfile.open(sys.argv[1]) as t: assert json.load(t.extractfile("bundle.json"))["release"] == "1.5.0"
PY
python3 "$P/maintenance.py" verify "$S/daemonarchy-1.5.0-boot.txz" --signature "$S/daemonarchy-1.5.0-boot.txz.sig" --root "$S/boot-tree" || fail "the new bundle does not verify"
after=$(sums)

# 2. It never replaces an existing bundle.
! run env PRIOR=$S/daemonarchy-1.4.2-boot.txz RELEASE=1.5.0 >/dev/null 2>&1 || fail "replaced an existing bundle"
[[ $(sums) == "$after" ]] || fail "an existing bundle changed"

# 3. Bad input is refused and writes nothing.
! run env RELEASE=1.5.1 >/dev/null 2>&1 || fail "ran without PRIOR"
! run env PRIOR=$S/daemonarchy-1.4.2-boot.txz RELEASE=banana >/dev/null 2>&1 || fail "accepted a bad release label"
! run env PRIOR=$S/nonexistent-boot.txz RELEASE=1.5.1 >/dev/null 2>&1 || fail "accepted a missing prior bundle"
! KEY=$work/nokey run env PRIOR=$S/daemonarchy-1.4.2-boot.txz RELEASE=1.5.1 >/dev/null 2>&1 || fail "ran without a key"
[[ $(sums) == "$after" ]] || fail "a refused run wrote a bundle"

# 4. A tree that changed since PRIOR needs a full re-sign, not a relabel.
echo changed >>"$S/boot-tree/boot/lua/brand.lua"
msg=$(run env PRIOR=$S/daemonarchy-1.4.2-boot.txz RELEASE=1.5.1 2>&1) && fail "relabelled a changed tree" || true
[[ $msg == *"full re-sign is needed"* ]] || fail "wrong refusal for a changed tree: $msg"
sed -i '$d' "$S/boot-tree/boot/lua/brand.lua"
[[ $(sums) == "$after" ]] || fail "the changed-tree run wrote a bundle"

# 5. A bundle that differs from PRIOR in anything but the label is refused and not kept.
msg=$(STUB_TAMPER=1 run env PRIOR=$S/daemonarchy-1.4.2-boot.txz RELEASE=1.5.2 2>&1) && fail "accepted a bundle that differs beyond the label" || true
[[ $msg == *"does not verify"* || $msg == *"unexpected differences"* || $msg == *"mismatch"* ]] || fail "wrong refusal for a tampered bundle: $msg"
[[ ! -e $S/daemonarchy-1.5.2-boot.txz && ! -e $S/daemonarchy-1.5.2-boot.txz.new ]] || fail "a refused bundle was kept"

# 6. check and sign still need the package set; unknown commands print usage.
! S=$S PY=python3 CERT=$work/cert.pem KEY=$work/key bash "$script" check >/dev/null 2>&1 || fail "check ran without PACKAGES and REV"
! bash "$script" nonsense >/dev/null 2>&1 || fail "an unknown command succeeded"
echo 'resign-boot-bundle rebundle checks passed'
