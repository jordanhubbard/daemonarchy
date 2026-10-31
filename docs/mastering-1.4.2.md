# Mastering notes for 1.4.2

What changed in how an amd64 release image is mastered after 1.4.1, so the 1.4.2 run
starts from it. The steps themselves are in [mastering-1.4.1.md](mastering-1.4.1.md).

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
