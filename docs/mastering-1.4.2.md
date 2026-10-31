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
