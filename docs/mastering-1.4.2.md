# Mastering notes for 1.4.2

What changed in how an amd64 release image is mastered after 1.4.1, so the 1.4.2 run
starts from it. The steps themselves are in [mastering-1.4.1.md](mastering-1.4.1.md).

## The re-roll sequence

The order the 1.4.2 release will follow. Publishing anything (a feed, an image, the
release) is the release owner's step and happens only after approval; the steps before it
write files and nothing else. amd64 is built on mudflap and aarch64 on barmy; keys stay on
madmax (`~/daemonarchy-keys`, never copied into a VM, never printed).

1. **Pin the ports revision.** One daemonarchy-ports revision for both architectures, then
   fast-forward `main` to it. Merge the ports that the pin depends on first: `x11-wm/daemonarchy`
   needs `ports-mgmt/daemonarchy-pkg`
   ([daemonarchy-ports #39](https://github.com/jordanhubbard/daemonarchy-ports/pull/39)),
   which a `main` without it cannot resolve. `graphics/drm-612-kmod` on aarch64
   ([#36](https://github.com/jordanhubbard/daemonarchy-ports/pull/36)) is a draft that moves
   only when the arm64 feed pin carries it.
2. **List what changes.** `scripts/diff-release-packages.sh OLD_PORTS NEW_PORTS FEED.tsv
   net/if_brcmfmac-kmod ports-mgmt/daemonarchy-pkg` against the last release's application
   feed and the new pin, on mudflap (`make -V PKGNAME` only). Against the 1.4.1 feed, ports
   `dd277aff` to `main` plus #39, it found exactly: `x11-wm/daemonarchy` 1.4.1,1 to
   1.4.1_1,1 (the new dependency); `ports-mgmt/daemonarchy-pkg-0.1.0` new; and, on the ISO
   only, `net/if_brcmfmac-kmod` `_2` to `_3`. Nothing else in the 209-package feed moved
   (`omarchy` stays 4.0.4_28). Re-run it at the real pin.
3. **Rebuild** in one poudriere run (`poudriere -e $WORK/poudriere-etc bulk -S -C ...`, see
   [mastering-1.4.1.md](mastering-1.4.1.md#why-the-package-build-is-not-a-plain-poudriere-bulk)):
   the changed feed packages, the new one, and the kernel-bound module. Add
   `ports-mgmt/daemonarchy-pkg` to `OMARCHY_ORIGINS` in `origins.sh` so the feed carries it.
4. **Secure Boot.** A rebuilt kernel module moves the signed module inventory
   ([the Wi-Fi driver notes below](#rebuilding-a-kernel-bound-module-on-mudflap-the-wi-fi-driver-2026-10-31)):
   regenerate it with `resign-boot-bundle.sh check`; `sign` needs the boot signing key and
   is an operator decision. The re-signed bundle and its `.sig` replace the 1.4.1 ones in the
   release assets.
5. **Application feeds.** A full signed feed for each architecture, `packages-16-amd64-1.4.2`
   and `packages-16-aarch64-1.4.2` (a suffix such as `-r2` only when a published tag must be
   superseded; published tags are never replaced). `master-release.sh feed` builds it on the
   builder with the key already there, `package-feed-manifest.py` stages it, and the
   release owner uploads with `package-feed-upload.py` (never `--clobber`) and verifies by
   re-download. The installer reads one application repository per tag, so a feed is a
   complete one, not a delta.
6. **Checkout feeds.** `checkouts-16-ARCH-1.4.2`: the ports checkout package and catalogue at
   the pin (the source checkout stays at the base revision unless the base moved). The
   overlay `checkouts.json` becomes the published catalogue, byte for byte, in the release
   pull request.
7. **Closure shards.** Run `scripts/package-mirror-plan.py --fail-on-unsatisfied` against the
   current upstream catalogue and the published shards, with the new roots. The dependency
   closure of `daemonarchy-pkg` (107 packages with GTK 4) was checked against the published
   `packages-16-amd64-1.4.1-upstream` shard and the 1.4.1 feed and is already covered, so
   amd64 needs no new shard for it. A gap becomes a delta shard,
   `packages-16-ARCH-1.4.2-upstream` (published tags are immutable, so a gap cannot join
   an old shard); aarch64 is checked the same way on barmy, including `py312-sqlite3`, the
   live-image gap of 1.4.1. List every shard in `PACKAGE_MIRROR_URLS`, new and old, and
   stage its record in `verification/closure-feeds/`.
8. **Build the images.** amd64 on mudflap, aarch64 on barmy, from `main` at one commit, with
   `PACKAGE_REPOSITORY_TAG` and the catalogue of the new feeds and `REQUIRE_PACKAGE_MIRROR=yes`
   (`master-release.sh iso`; the setup notes below).
9. **Verify** (`master-release.sh verify`): the digests, `_sqlite3` in the live root, the
   embedded mirror and tag, the catalogue byte for byte, and the overlay launchers and
   desktop entries against the files on `main` (sha256).
10. **QEMU QA** against the public URLs from a workstation (`master-release.sh qa`, with the
    config's own `WORK` and a `QA_DIR` of its own). Count `[FreeBSD]` in the install log: it
    must be 0, or list each package absent from our feeds.
11. **Sticks.** The operator gives the serials. `master-release.sh sticks` writes both,
    refuses the scratch disk and anything mounted, and reads each back against the digest.
12. **Publish** (release owner): the feeds, then the release with the eight assets,
    verified with `scripts/verify-release-assets.py --published`.
13. **Fill the records.** The draft release pull request is made once the template is
    reviewed: `scripts/prepare-release.py --version 1.4.2 --source-commit SHA40` copies
    `release/templates/release-1.4.2.md` to `docs/release-1.4.2.md`, writes the
    `verification/release-1.4.2.json` skeleton and moves `release/current.json` to the new
    release with `TODO` digests. Write the prose sentences it lists (README, HACKING,
    PROJECT, CHANGELOG, `docs/aarch64.md`), keep the pull request a draft (the docs
    guard fails by design until it is filled), and after publication run
    `scripts/fill-release.py` (below). `tests/release-prepare-fill.py` runs the whole
    flow on a scratch tree.

### Filling the records

```
python3 scripts/fill-release.py --version 1.4.2 --assets ASSETS --dry-run ...   # same arguments
python3 scripts/fill-release.py --version 1.4.2 --assets ASSETS \
    --installer-commit INSTALLER40 --ports-commit PORTS40 \
    --packages-amd64 packages-16-amd64-1.4.2 --packages-aarch64 packages-16-aarch64-1.4.2 \
    --checkouts-amd64 checkouts-16-amd64-1.4.2 --checkouts-aarch64 checkouts-16-aarch64-1.4.2 \
    --aarch64-final-qemu "..." --physical-status "..." --set GUI001_EVIDENCE="..." \
    [--published-at 2026-11-07T00:00:00Z]
python3 tests/docs-release-sync.py -v
python3 scripts/verify-release-assets.py --record verification/release-1.4.2.json \
    --assets ASSETS --closure-assets CLOSURE_DIR      # CLOSURE_DIR/<tag>/ for each closure shard
```

It generalises `fill-release-1.4.1.py`: the version is an argument, the closure shards are
the record's `closure_feed_records`, and a release-specific token is given with `--set`. The
assets directory holds exactly the eight files; sizes and digests are computed from them.
After publication use `scripts/release-current.py update` and `check-published`.

## The amd64 build VM (mudflap)

`daemon.local` is retired. All amd64 build work runs in a FreeBSD 16.0-CURRENT VM on
madmax (Linux, 32 cores, KVM): host name `mudflap`, kernel `#3 303b3646270f`, 16 CPUs,
48 GB RAM, a 500 GB sparse virtio disk, poudriere-devel 3.4.99 and xorriso. It is a
Daemonarchy install made from the 1.4.1 candidate image, in
`~/daemonarchy-builder-vm/recovery-virtio-20261031T004143Z/disk.img` on madmax.

```
ssh madmax.local '~/daemonarchy-builder-vm/ssh-worker.sh "uptime"'     # root, key-only
ssh madmax.local sh ~/daemonarchy-builder-vm/start-vm.sh                # boot it if it is off
```

`scripts/start-build-vm.sh` is the copy of `start-vm.sh` kept here. It does nothing if
the VM is running, otherwise it copies the last `OVMF_VARS.fd`, starts QEMU in a new
`boot-<time>` directory and forwards `127.0.0.1:22461` to the guest's ssh. **The VM is
off after the supervisor's six-hour window ends or when madmax restarts; say so
whenever you restart it.** It takes about 15 seconds to answer ssh.

The VM has no signing keys and does not need them: feeds that are already signed and
published are only read, and the signed Secure Boot bundle and its public certificate are
copied in. The signing keys stay on madmax in `~/daemonarchy-keys` (mode 0400); a step that
really needs them (`pkg repo` for a new feed) is a decision for the operator.

### Setting it up for a release (what 1.4.1 needed)

- `rev2-*/` inputs: `poudriere-data/packages/<jail>-<tree>` (the package set),
  `poudriere-etc`, `inputs/source-sets` (`base.txz`, `kernel.txz`, `lib32.txz`), the
  product checkout, and `/usr/daemonarchy/sb16` with the signed bundle and `.sig`.
- The jail registration that came with the copied metadata had no root filesystem. Remove
  it (`poudriere jail -d -j NAME -y`) and create it natively:
  `poudriere jail -c -j NAME -v 16.0-CURRENT -a amd64 -m tar=.../base.txz`, then
  **extract `kernel.txz` and `lib32.txz` into the jail root**: `poudriere image` needs
  `boot/kernel/kernel`.
- Make `distfiles` (`DISTFILES_CACHE`) and `stage` (`ISO_STAGE_PARENT`) directories, and
  register the ports tree: `git clone --depth 1` the pinned ports revision, then
  `poudriere ports -c -p TREE -m null -M PATH`.
- `build-iso.sh` then takes about 35 seconds for the image and about 3 minutes to compress it.

### Pitfalls found

- The installer hung without output when the CIDATA drive was on the AHCI bus (a
  known product problem with a workaround in the VM recovery notes: a read-only virtio
  CIDATA drive). A QEMU guest that prints nothing after `staging 0x...` for two minutes
  is stuck; do not wait hours.
- Not a plain bulk: `poudriere bulk -n` on the new host proposes rebuilding the
  kernel-bound and Omarchy ports whose files are in the set (probably because the
  original poudriere cache was not copied; not confirmed). The decisive check is that
  `poudriere image` assembles.

## The runbook fixes since 1.4.0

- `iso` requires the closure feed: `PACKAGE_MIRROR_URLS` and `REQUIRE_PACKAGE_MIRROR=yes`.
- A revision tag (`packages-16-amd64-1.4.1-r2`) names its own feed directory, and the
  closure shard keeps the release's tag. `feed` refuses a non-empty output directory:
  `pkg-repo.sh build` empties it first.
- `verify` exits 0 (a leaked RETURN trap used to make it exit 1 after recording `ok`);
  `qa` passes the desktop check by absolute path and keeps its state file under the
  configured `WORK`.
- Run `qa` from the workstation against the QA host with a config whose `WORK` is a
  local directory holding `out-<short>/*.iso.xz`; give each QA run its own `QA_DIR`.
- A `suffixed` application feed is a **full** feed (every package the installer needs
  from our feed), not a delta: the installer reads one application repository per tag.
- The install transaction turns pkg.FreeBSD.org off while a closure shard answers; the
  count of `[FreeBSD]` lines in the install log must be 0.

## Rebuilding a kernel-bound module on mudflap (the Wi-Fi driver, 2026-10-31)

`net/if_brcmfmac-kmod` is on the ISO only, so merging a change to it moves the Secure Boot
module inventory and the signed boot bundle. This is what was done for
[daemonarchy-ports #37](https://github.com/jordanhubbard/daemonarchy-ports/pull/37)
(merge commit `e136408d799d0cee1aec5e168ced06cea8309bb8`), and what the next kernel-bound
change needs.

**Restore the Secure Boot work dir first.** The full `/usr/daemonarchy/sb16` tree (`build/`
with `build.json` and `loader_lua.efi`, `boot-tree/`, `module-inventory.json`, `product/`,
`src/`) came from the daemon.local evacuation copy on madmax
(`~/daemon-local-evac/usr/daemonarchy/sb16`, 242,151 files, 5.2 GB). mudflap has no
`rsync`; stream it: `tar -cpf - . | ssh-worker.sh "tar -C /usr/daemonarchy/sb16 -xpf -"`.
Restore it at exactly that path, because `build/*-obj` contains symlinks with absolute
`/usr/daemonarchy/sb16/...` targets. The tree holds no private key (its `*.pem` hits are
public certificates; the signing key is not in it).

Verify it file by file, and expect noise if you hash in parallel: `xargs -P8 sha256sum`
output interleaves and gave 6,568 false mismatches. Recompute the mismatched paths
serially on both sides; all matched. The bundle and signature match
`release/current.json` (`ce1c485d…`, `fa67149e…`), and regenerating the inventory from the
1.4.1 package set with `secureboot/module-inventory.py` reproduces the restored
`module-inventory.json` byte for byte (1,942 lines, `d768de48…`).

**Use `-e`.** On mudflap a bare `poudriere jail -l` or `bulk` stops with `ZPOOL variable is
not set`. Always run `poudriere -e $WORK/poudriere-etc ...`.

**The release jail cannot build a kernel module.** `16r2303b36` has an empty `/usr/src`,
so `net/if_brcmfmac-kmod` fails with `Unable to locate the kernel source tree`. The module
reproduces the release only when `/usr/src/sys` is the 303b364 kernel source. Do not alter
the release jail: create a sibling from the same `base.txz` and copy the source in.

```
poudriere -e $WORK/poudriere-etc jail -c -j 16r2303b36s -v 16.0-CURRENT -a amd64 \
    -m tar=$WORK/inputs/source-sets/base.txz
mkdir -p /usr/local/poudriere/jails/16r2303b36s/usr/src
cp -a /usr/daemonarchy/sb16/src/sys /usr/local/poudriere/jails/16r2303b36s/usr/src/sys
```

The jail is not a ZFS dataset here, so there is no `@clean` snapshot to refresh. Its packages
go to `poudriere-data/packages/<jail>-<tree>`, separate from the release set.

**Control first.** Build the unpatched port from the release ports tree in the same jail
before trusting a difference: `if_brcmfmac-kmod-20260402.1600029_2` reproduced
`333bb3ae77b2b264a18a7822b5255b9a34bf4dc8b5023d154678ac00da919d1e`, the module on the 1.4.1
ISO, bit for bit.

**Result.** The merged port (`_3`, package `ca4cc84f8cfc42e950611b16d0828a0bd05db2cd9841b090b8dd4debf3f6f44d`)
builds `/boot/modules/if_brcmfmac.ko` with SHA-256
`c784ccde397db3772206ba27809c25715aa00f86babdadcf20ad26af44427492`, the same module that
was built and tested on the MacBook. That is the single `DIFFERENT` row. Extract a module
from a package with `tar -xOf PKG /boot/modules/if_brcmfmac.ko | sha256`; without the leading `/`
the member is not found and the hash is that of empty input (`e3b0c442…`).

**Check the inventory without signing.** Stage a package directory that is the release set
with the rebuilt kmod swapped in (`cp -al` the release `All/`, replace the one package), then
run the script from `main` (the restored `product/` predates it):
`PACKAGES=<staged All> REV=303b3646270ffa4bf7cec65c5c1d28bd8000cbce /bin/bash resign-boot-bundle.sh check`.
It exits 1 and writes `module-inventory.json.new`. The diff against the current inventory
was exactly two hunks: the package entry (`_2` to `_3`) and the module hash. `sign` is the
step that needs the signing key and is an operator decision.
