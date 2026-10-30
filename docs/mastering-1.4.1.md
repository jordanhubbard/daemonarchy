# Mastering a release image

How the next release image is built, checked and written to USB sticks, in resumable
steps. The driver is `scripts/master-release.sh`; the package half is
`scripts/build-release-packages.sh`. Both have a dry run that prints every command
without running it, and both are covered by `tests/master-release.sh` and
`tests/build-release-packages.sh`. Publishing to GitHub is a separate, approved step
that none of these scripts performs.

```
scripts/master-release.sh --dry-run --config master.env all     # show everything
scripts/master-release.sh --config master.env packages feed     # long steps, one at a time
scripts/master-release.sh --config master.env iso verify qa
scripts/master-release.sh sticks --iso X.iso.xz --raw-sha256 HEX --raw-size N \
    --device /dev/sdb:SERIAL --device /dev/sdc:SERIAL
```

`master.env` sets `WORK`, `MAIN_COMMIT` (the full 40-hex commit to master), and any
other variable at the top of `master-release.sh`. Each step records `ok` and a time in
`$WORK/master-state.tsv`; a rerun skips finished steps (`--force` redoes one, `status`
prints the file). The steps run on the amd64 builder, except `qa` (the QEMU host) and
`sticks` (the workstation the sticks are plugged into).

## The steps

| Step | What it does |
| --- | --- |
| `preflight` | Tools present, `MAIN_COMMIT` reachable on the remote, 30 GB free. |
| `packages` | Origins list, seeded package set, poudriere dry run and bulk, built list, module identity. |
| `secureboot` | Regenerates the Secure Boot module inventory for the rebuilt set; re-signs the boot bundle only if the inventory changed. |
| `feed` | Collects the application feed (`pkg-repo.sh build`), signs it on the builder, writes the upload plan. |
| `resolve` | `pkg install -n` of the MSI and MacBook selections against the ISO repository plus the two feeds, with pkg.FreeBSD.org not configured. |
| `catalogue` | Checks the checkout catalogue names the source and ports revisions being released. |
| `iso` | Builds the ISO from a clean checkout of `MAIN_COMMIT`. About 26 minutes. |
| `verify` | `xz -t`, both digests, the 2 GiB asset budget, and the installer version inside the image. |
| `qa` | Copies the image to the QA host and runs `test-qemu.sh` with the expected feed tag and the desktop check. |
| `sticks` | Writes the image to the named USB sticks and reads each one back against the digest. |

## Why the package build is not a plain poudriere bulk

The retained userland in the previous release's set was built against an older
`harfbuzz` than the pinned ports tree carries (`chromium`, `cef`, `tensaku` and
`hyprland-preview-share-picker` record `harfbuzz-14.2.1`; the tree has 14.6.0, and the
old package file is gone). A plain `poudriere bulk` over that set calls those packages
stale and would rebuild `chromium` from source, which this builder cannot do in
reasonable time or memory. The build therefore:

- seeds a new package directory by hard-linking the previous set and deleting only what
  must change: kernel-bound packages (`*kmod*`, the NVIDIA driver and libraries),
  `x11-wm/omarchy` and `x11-wm/daemonarchy`;
- runs `poudriere bulk -S`, which stops recursive rebuilds. The eleven Omarchy ports the
  previous release took from an overlay (`cliamp`, `herdr`, `omacalc`, `omacut`,
  `omarchy-nvim`, `omasnap`, `omawrite`, `owe`, `owe-lockfeed`, `ttfx`, `usage`) are in the
  pinned ports tree since daemonarchy-ports #31 (checked byte for byte against the overlay),
  so no overlay is needed; `OVERLAY=name` still adds one;
- lets any package whose version changed in the tree (for example `aquamarine` with a
  new port revision) rebuild as a normal stale package.

The dry run (`... build-release-packages.sh plan`) lists exactly what will be built and
deleted; read it before starting the bulk.

### Kernel-bound modules

Modules, firmware and the NVIDIA stack are rebuilt in the new jail for every new
kernel, even when the kernel's `sys/` sources did not change, so the evidence of what
they were built against is the new jail. `identity` writes `kmod-identity.tsv`: for each
module in a rebuilt package, the SHA-256 of the previous build's module and the new
one. Identical hashes mean the rebuild reproduced the old modules bit for bit; any
`DIFFERENT` row means the Secure Boot module inventory
(`secureboot/module-inventory.py`) must be regenerated and the boot bundle re-signed
before the ISO is built, because the signed boot manifest carries module hashes.

## Feeds and what may be published

The application feed is the packages named by `OMARCHY_ORIGINS` plus the packages the
bulk built from source, minus anything kernel-bound (those stay on the ISO). `feed`
writes `$FEED_OUT.plan.txt` with the asset count, sizes and SHA-256 of every file. The
catalogue is signed on the builder with the key already there; the key never leaves it,
and its public half is `keys/pkg-repo-1.3.1.pub`, the key installed images pin.

Publishing the feed, the closure shard and the ISO is done by the operator or with the
operator's approval from the plan, using the upload and verification tools
(`scripts/package-feed-upload.py`, `scripts/verify-release-assets.py`). A feed tag is
new and never replaces an existing release.

## Writing the sticks

`sticks` refuses to write unless every named device passes all of these:

- it is a whole disk path (`/dev/sdX`, `/dev/nvmeXnY`, `/dev/mmcblkN`), never a partition;
- the kernel reports a USB transport and type `disk`;
- its serial is not on the deny list (the 239 GB scratch disk, serial
  `03A0423110011698`, is there by default) and matches the serial the operator named;
- it is no larger than `STICK_MAX_BYTES` (128 GiB) and at least as large as the image;
- nothing on it is mounted.

One bad device stops the run before any write. Each device is written from the verified
`.xz` and read back; the read-back digest must equal the raw image digest the operator
passes in. `verify` prints that digest and size.

## When the ports revision is declared final

One daemonarchy-ports revision serves both architectures: `release/1.4.1-ports-final`, a
descendant of the previous pin with the aarch64 desktop-dependency changes (#28, #30,
#31), `omarchy` 4.0.4_27 (#29's omarchy-freebsd commit), `daemonarchy` 1.4.1 and the
`aquamarine` exit-time logger fix (#35), and none of the upstream sync. The builder's
tree is `ports-141` (poudriere ports tree `daports141`). Evidence that the aarch64
changes leave the amd64 packages alone: the eleven ports from #31 are byte-identical to
the overlay the previous release built from, `poudriere bulk -n` against the final tree
reports nothing to build, and `hyprland`, `omarchy` and `daemonarchy` were rebuilt at the
final revision and compared with the earlier builds (`evidence/final-compare.txt`).

If the revision is final as it stands:

```
# 1. stage the signed feed for the uploader (hard links; nothing is copied off the builder)
python3 scripts/package-feed-manifest.py --feed $WORK/feed-packages-16-amd64-1.4.1 \
    --tag packages-16-amd64-1.4.1 --out $WORK/feed-stage --title "Daemonarchy packages for FreeBSD 16 (amd64)"
# 2. publish (operator-approved; a new tag, never the latest, nothing replaced)
python3 scripts/package-feed-upload.py upload --out $WORK/feed-stage --notes-file feed-notes.md
python3 scripts/package-feed-upload.py verify --out $WORK/feed-stage
```

If another ports change lands first (for example the MacBook Wi-Fi driver,
`net/if_brcmfmac-kmod`), add its commits to `release/1.4.1-ports-final`, fast-forward
daemonarchy-ports `main` to the new tip, and on the builder fetch and check out that tip in
`$WORK/ports-141`, then:

```
scripts/build-release-packages.sh plan                    # read what it will rebuild
poudriere -e $WORK/poudriere-etc bulk -S -C -b latest -j $JAIL -p $PTREE -f changed-origins.txt
scripts/build-release-packages.sh built identity          # with BUILT_OUT and PREVIOUS_BUILT as in the packages step
scripts/resign-boot-bundle.sh sign                        # a rebuilt module changes the signed inventory
```

A kernel-bound package such as `if_brcmfmac-kmod` is on the ISO only, so the application
feed's files do not change and its tag stays valid. If a package that is in the feed does
change, stage and publish a new, suffixed tag (for example `packages-16-amd64-1.4.1-r2`) and
point the ISO build at it with `PACKAGE_REPOSITORY_TAG`; never replace an asset. Then rebuild
the ports checkout package and catalogue at the new tip, update
`overlay/usr/local/share/daemonarchy-installer/checkouts.json` by pull request, and run
`scripts/master-release.sh iso verify qa`.

## Not covered here

The arm64 image and its packages have their own plan (`docs/aarch64.md`). The closure
shard refresh is `scripts/package-mirror-plan.py --fail-on-unsatisfied` against the
current upstream catalogue.
