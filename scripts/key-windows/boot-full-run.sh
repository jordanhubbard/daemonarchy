#!/bin/sh
# Full re-sign of the boot bundle for a release from newer inputs, on the build VM (mudflap), in one key window.
#
#   boot-full-run.sh RELEASE          e.g. 1.5.0
#
# boot-relabel-run.sh only re-labels an already signed tree. This one rebuilds the boot tree from the commit's inputs
# (prepare-boot-tree.sh), signs the boot manifest and loader (sign-boot-tree.py) and creates the bundle (bundle.py), so a
# changed input that the signed manifest covers (for 1.5.0: boot/lua/brand-daemonarchy.lua) ends up in the signature.
#
# It refuses unless the change is exactly the expected one, and nothing is replaced until every check has passed:
#   - the product tools and every input except the expected file are byte-identical to the product the previous tree used;
#   - the module inventory is the one the previous bundle was signed with (and lists the _3 kernel module);
#   - the freshly prepared tree differs from the previous signed tree only in the expected file(s) and the signing outputs;
#   - the new bundle differs from the previous bundle only in the expected members, bundle.json differs only in `files`,
#     the manifest lines that changed are only the expected ones, the certificate and every other entry are unchanged.
# The previous bundle and tree are kept (.previous / boot-tree.before-*). The key must be a file on a tmpfs at /var/keytmp
# (memory only, swap off); it is passed by path, never read, hashed into the log by value or printed, and is removed, the
# tmpfs unmounted and swap restored on every exit path. Run under the key-window lock:
#   lockf -t 0 /var/run/keywindow.lock /root/key-windows/boot-full-run.sh 1.5.0
# The SB_* variables exist for the throwaway mechanics test (SB_TEST=1 skips the tmpfs and swap checks).
set -eu
LC_ALL=C; export LC_ALL      # sort, join and comm below must agree on collation
REL=${1:?release, e.g. 1.5.0}
W=${SB_WORK:?SB_WORK: the release working directory (the source sets are read from $SB_WORK/inputs/source-sets)}
S=${SB_S:-/usr/daemonarchy/sb16}
B=${SB_BUILD:-$S/build}
PRODUCT=${SB_PRODUCT:?SB_PRODUCT: the inputs of the commit (secureboot/, scripts/import-apple-*, overlay brand lua)}
OLDPRODUCT=${SB_OLDPRODUCT:-$S/product}              # what the previous signed tree was prepared from
CACHE=${SB_CACHE:-$W/inputs/source-sets}
INV=${SB_INV:-$S/module-inventory.json}
INVSHA=${SB_INVSHA:?SB_INVSHA: sha256 of the module inventory the previous bundle was signed with}
KMOD=${SB_KMOD:?SB_KMOD: sha256 of a kernel module the inventory must list}
CERT=${SB_CERT:-/usr/daemonarchy/boot-replacement-candidate-public-20261024/daemonarchy-1.3.1.pem}
FW=${SB_FW:-/usr/daemonarchy/firmware-policy-guest-private-20261023/apple}
KT=${SB_KEYMNT:-/var/keytmp}
KEY=${SB_KEY:-$KT/boot.key}
OLDROOT=${SB_ROOT:-$S/boot-tree}
PRIOR=${SB_PRIOR:-$S/daemonarchy-$REL-boot.txz}
EXPECT=${SB_EXPECT:-boot/lua/brand-daemonarchy.lua}   # space separated: the only prepared files allowed to differ
PY=${SB_PY:-/usr/local/bin/python3.12}
P=$PRODUCT/secureboot
LOG=${SB_LOG:?SB_LOG: where to write the log}
STAMP=$(date -u +%Y%m%d%H%M%S)
NEWROOT=$S/boot-tree.new-$STAMP
NEWB=$PRIOR.new
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

cleanup() {
  status=$?
  if [ "${SB_TEST:-}" != 1 ]; then
    [ ! -e "$KEY" ] || { rm -P "$KEY" 2>/dev/null || true; rm -f "$KEY"; }
    if mount | grep -q "^tmpfs on $KT (tmpfs"; then umount "$KT" 2>/dev/null || true; fi
    rmdir "$KT" 2>/dev/null || true
    swapon -a 2>/dev/null || true
  fi
  [ "$status" = 0 ] || { rm -rf "$NEWROOT" 2>/dev/null || true; }
  rm -f "$NEWB" "$NEWB.sig" 2>/dev/null || true
  rm -rf "${WORK:-/nonexistent}" 2>/dev/null || true
  log "cleanup: key $( [ -e "$KEY" ] && echo PRESENT || echo gone ), $KT mounts: $(mount | grep -c " on $KT " || true); exit status $status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

mkdir -p "$(dirname "$LOG")"
: >"$LOG"
log "sign-boot-full start: release $REL; key sha256 (on VM): $(sha256 -q "$KEY" 2>/dev/null || echo none)"
case $REL in [0-9]*.[0-9]*.[0-9]*) ;; *) log "release must look like X.Y.Z"; exit 1 ;; esac
if [ "${SB_TEST:-}" != 1 ]; then
  mount | grep -q "^tmpfs on $KT (tmpfs" || { log "$KT is not a tmpfs"; exit 1; }
  [ -z "$(swapinfo 2>/dev/null | sed 1d)" ] || { log "swap is on"; exit 1; }
  [ "$(stat -f %Lp "$KEY")" = 400 ] || [ "$(stat -f %Lp "$KEY")" = 600 ] || { log "key file mode must be 0400 or 0600"; exit 1; }
fi
[ -f "$KEY" ] && [ -s "$KEY" ] || { log "no key file"; exit 1; }
[ -f "$PRIOR" ] && [ -f "$PRIOR.sig" ] || { log "no previous bundle $PRIOR"; exit 1; }
[ ! -e "$PRIOR.previous" ] && [ ! -e "$PRIOR.sig.previous" ] || { log "$PRIOR.previous already exists: preserve it, remove it deliberately first"; exit 1; }
[ ! -e "$NEWB" ] || { log "$NEWB exists"; exit 1; }
[ -d "$OLDROOT" ] || { log "no boot tree $OLDROOT"; exit 1; }
WORK=$(mktemp -d)

# 1. The previous signed tree and bundle belong together.
$PY "$OLDPRODUCT/secureboot/maintenance.py" verify "$PRIOR" --signature "$PRIOR.sig" --certificate "$CERT" --root "$OLDROOT" >>"$LOG" 2>&1 \
  || { log "the previous bundle does not match the current boot tree"; exit 1; }
log "previous bundle $(basename "$PRIOR") matches the current boot tree"

# 2. The module inventory is the one the previous bundle was signed with, and carries the _3 kernel module.
[ "$(sha256 -q "$INV")" = "$INVSHA" ] || { log "module inventory changed ($(sha256 -q "$INV")): a different re-sign is needed"; exit 1; }
grep -q "$KMOD" "$INV" || { log "the inventory does not list the if_brcmfmac.ko module $KMOD"; exit 1; }
log "module inventory unchanged (sha256 $INVSHA) and lists if_brcmfmac.ko $KMOD"

# 3. Freeze rule: every tool and input except the expected ones is byte-identical to the old product.
cmpfiles="secureboot/prepare-boot-tree.sh secureboot/sign-boot-tree.py secureboot/bundle.py secureboot/maintenance.py secureboot/boot/local.lua secureboot/boot/daemonarchy-secureboot.conf scripts/import-apple-bcm4364-firmware.py"
for f in $cmpfiles; do
  cmp -s "$OLDPRODUCT/$f" "$PRODUCT/$f" || { log "FREEZE: $f differs between the previous product and $PRODUCT: refusing"; exit 1; }
done
diff -rq "$OLDPRODUCT/secureboot" "$PRODUCT/secureboot" >/dev/null 2>&1 || { log "FREEZE: something under secureboot/ differs from the previous product: refusing"; exit 1; }
log "tools and inputs identical to the previous product except: $(cmp -s "$OLDPRODUCT/overlay/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua" "$PRODUCT/overlay/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua" && echo nothing || echo brand-daemonarchy.lua)"

# 4. Prepare the new tree and compare it with the previous signed tree.
$PY "$P/../scripts/import-apple-bcm4364-firmware.py" --verify-stage --model MacBookPro16,1 --destination "$FW" >>"$LOG" 2>&1 || { log "firmware stage check failed"; exit 1; }
/bin/sh "$P/prepare-boot-tree.sh" "$CACHE" "$B" "$NEWROOT" >>"$LOG" 2>&1 || { log "prepare-boot-tree.sh failed"; exit 1; }
hashes() { ( cd "$1" && find . -type f | sort | while IFS= read -r f; do printf '%s %s\n' "$(sha256 -q "$f")" "${f#./}"; done ); }
hashes "$OLDROOT" >"$WORK/old.h"; hashes "$NEWROOT" >"$WORK/new.h"
awk '{print $2}' "$WORK/old.h" | sort >"$WORK/old.n"; awk '{print $2}' "$WORK/new.h" | sort >"$WORK/new.n"
onlynew=$(comm -13 "$WORK/old.n" "$WORK/new.n" | tr '\n' ' ')
onlyold=$(comm -23 "$WORK/old.n" "$WORK/new.n" | tr '\n' ' ')
sort -k2 "$WORK/old.h" >"$WORK/old.h.s"; sort -k2 "$WORK/new.h" >"$WORK/new.h.s"
changed=$(join -1 2 -2 2 -o 0,1.1,2.1 "$WORK/old.h.s" "$WORK/new.h.s" | awk '$2!=$3{print $1}' | sort | tr '\n' ' ')
SIGNOUT="boot/manifest boot/manifest.certs boot/manifest.sig boot/runtime.manifest boot/runtime.manifest.certs boot/runtime.manifest.sig "
want_changed=$(printf '%s\n' $EXPECT boot/loader.efi | sort | tr '\n' ' ')
[ -z "$onlynew" ] || { log "the new tree has unexpected extra files: $onlynew"; exit 1; }
[ "$onlyold" = "$SIGNOUT" ] || { log "files missing from the new tree are not exactly the signing outputs: $onlyold"; exit 1; }
[ "$changed" = "$want_changed" ] || { log "files that differ from the previous signed tree: [$changed], expected [$want_changed] (the signed loader.efi is re-made): refusing"; exit 1; }
log "new tree differs from the previous signed tree only in: $EXPECT (and the loader, which is signed again); signing outputs are absent until signed"

# 5. Sign the tree and create the bundle.
$PY "$P/sign-boot-tree.py" "$NEWROOT" --loader "$B/loader_lua.efi" --build-receipt "$B/build.json" --kernel-path kernel.secure/kernel \
    --module-inventory "$INV" --firmware-stage "$FW" --certificate "$CERT" --key "$KEY" >>"$LOG" 2>&1 || { log "sign-boot-tree.py failed"; exit 1; }
$PY "$P/bundle.py" "$NEWROOT" --out "$NEWB" --release "$REL" --build-receipt "$B/build.json" --certificate "$CERT" --key "$KEY" >>"$LOG" 2>&1 \
  || { log "bundle.py failed"; exit 1; }
rm -f "$KEY"
log "key file removed after signing"
$PY "$P/maintenance.py" verify "$NEWB" --signature "$NEWB.sig" --certificate "$CERT" --root "$NEWROOT" >>"$LOG" 2>&1 || { log "the new bundle does not verify against the new tree"; exit 1; }
if tar -tf "$NEWB" | grep -E 'firmware/|\.key$|\.pem$'; then log "PRIVATE MATERIAL IN PUBLIC BUNDLE"; exit 1; fi

# 6. Compare the new bundle with the previous one, member by member.
mkdir "$WORK/o" "$WORK/n"; tar -xf "$PRIOR" -C "$WORK/o"; tar -xf "$NEWB" -C "$WORK/n"
cat >"$WORK/cmp.py" <<'PYEOF'
import json, sys, hashlib
from pathlib import Path
o, n, cert, expect, kmod = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4].split(), sys.argv[5]
allowed = set(expect) | {"bundle.json", "boot/manifest", "boot/manifest.sig", "boot/loader.efi", "boot/runtime.manifest", "boot/runtime.manifest.sig"}
must = set(expect) | {"bundle.json", "boot/manifest", "boot/manifest.sig"}
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
names = sorted(str(p.relative_to(n)) for p in n.rglob("*") if p.is_file())
assert names == sorted(str(p.relative_to(o)) for p in o.rglob("*") if p.is_file()), "member lists differ"
diff = {m for m in names if h(o / m) != h(n / m)}
bad = diff - allowed
if bad: sys.exit(f"unexpected members differ: {sorted(bad)}")
if must - diff: sys.exit(f"expected members did not change: {sorted(must - diff)}")
a, b = json.loads((o / "bundle.json").read_text()), json.loads((n / "bundle.json").read_text())
fa, fb = a.pop("files"), b.pop("files")
if a != b: sys.exit("bundle.json differs beyond `files`: " + ", ".join(k for k in set(a) | set(b) if a.get(k) != b.get(k)))
fdiff = {k for k in fa if fa[k] != fb[k]}
if fdiff != {m for m in diff if m != "bundle.json"}: sys.exit(f"bundle.json files digests {sorted(fdiff)} do not match the changed members {sorted(diff - {'bundle.json'})}")
def lines(p): return {l.split(" sha256=")[0]: l for l in (p).read_text().splitlines() if " sha256=" in l}
la, lb = lines(o / "boot/manifest"), lines(n / "boot/manifest")
if set(la) != set(lb): sys.exit("boot manifest lists different files")
ch = {k for k in la if la[k] != lb[k]}
okm = {m[len("boot/"):] for m in expect if m.startswith("boot/")} | {"loader.efi", "runtime.manifest", "runtime.manifest.sig"}   # manifest paths are relative to boot/
if not ch <= okm: sys.exit(f"manifest lines changed beyond the expected: {sorted(ch - okm)}")
for k in lb:
    if k.endswith("if_brcmfmac.ko") and kmod not in lb[k]: sys.exit("if_brcmfmac.ko entry differs from the _3 module in the manifest")
if (n / "boot/manifest.certs").read_bytes() != cert.read_bytes() or (n / "boot/runtime.manifest.certs").read_bytes() != cert.read_bytes():
    sys.exit("the certificate in the bundle is not the release certificate")
print("members changed: " + ", ".join(sorted(diff)))
print("manifest lines changed: " + ", ".join(sorted(ch)))
print("modules, kernel, certificate and every other entry unchanged; bundle.json differs only in files")
PYEOF
res=$($PY -I "$WORK/cmp.py" "$WORK/o" "$WORK/n" "$CERT" "$EXPECT" "$KMOD" 2>&1) || { log "comparison with the previous bundle failed: $res"; exit 1; }
echo "$res" | while IFS= read -r l; do log "  $l"; done

# 7. Everything passed: replace, keeping the previous bundle and tree.
mv "$PRIOR" "$PRIOR.previous"; mv "$PRIOR.sig" "$PRIOR.sig.previous"
mv "$NEWB" "$PRIOR"; mv "$NEWB.sig" "$PRIOR.sig"
mv "$OLDROOT" "$S/boot-tree.before-$STAMP-$REL"; mv "$NEWROOT" "$OLDROOT"
log "previous bundle kept as $(basename "$PRIOR").previous (sha256 $(sha256 -q "$PRIOR.previous")) and previous tree as boot-tree.before-$STAMP-$REL"
log "created $(basename "$PRIOR") $(stat -f %z "$PRIOR") bytes sha256 $(sha256 -q "$PRIOR")"
log "created $(basename "$PRIOR").sig $(stat -f %z "$PRIOR.sig") bytes sha256 $(sha256 -q "$PRIOR.sig")"
log "PASS: boot bundle re-signed from the commit's inputs and verified"
