# Post-mortem: the 1.4.0 image stopped installing (tigervnc-viewer)

Status: written 2026-11-01 from the evidence below and the git history. Facts are
marked as measured, taken from the history, or **unverified**. No individual is
at fault: the gap was in what the process checked.

## Summary

The published 1.4.0 image installed correctly when it was built and tested, and
stopped installing after pkg.FreeBSD.org changed underneath it. A fresh install
of 1.4.0 now fails at the package download with `pkg: daemonarchy has a missing
dependency: tigervnc-viewer`. The 1.4.1 image, which carries that package in
Daemonarchy's own feed, installs. A user report ("daemonarchy install fails
with cannot find tigervnc") matches the 1.4.0 failure; the reporter's image
version is **unverified**.

## Timeline (UTC)

| When | What | Source |
|---|---|---|
| 2026-10-29 18:51 | The 1.4.0 tag commit (`60850645`) | git |
| 2026-10-29 20:28 | 1.4.0 published | `gh release view` |
| before 2026-10-29 22:25 | pkg.FreeBSD.org's `FreeBSD:16:amd64/latest` moves `fltk` to 1.4.5 and no longer has `tigervnc-viewer`. The exact removal time is **unverified**; the catalogue file's `Last-Modified` was 2026-10-29 22:25:17 GMT when read on 2026-11-01, and it has no `tigervnc-viewer` | measured |
| 2026-10-30 05:26 | #147 merged: publishes `net/tigervnc-viewer` and `x11-toolkits/fltk` 1.3.11 in Daemonarchy's feed, resolves packages before downloading, and adds a daily upstream-drift workflow. Its message records the failure as seen on an MSI with the 1.4.1 candidate | git |
| 2026-10-30 07:44 | #159: the closure feed becomes a mandatory release and install step (`scripts/check-closure-feed.sh`) | git |
| 2026-10-31 06:08 | 1.4.1 published, carrying the package and a closure shard | `gh release view` |
| 2026-11-01 | Fresh QEMU installs of the published ISOs (below) | measured |

#147 is in the 1.4.1 tag and not in 1.4.0 (`git merge-base --is-ancestor`).

## Evidence (fresh installs, 2026-11-01, madmax, QEMU/OVMF, live feeds)

| Image | Result | `tigervnc-viewer` |
|---|---|---|
| 1.4.0 (published, sha256 `fcaf5e1d…`) | install fails, exit 1 | never installs |
| 1.4.1 (published, sha256 `ea0b6d9e…`) | installs in 8 minutes | 1.16.2_1 from `[Daemonarchy]`, with fltk 1.3.11; no `[FreeBSD]` packages |

The 1.4.0 log repeats `pkg: daemonarchy has a missing dependency:
tigervnc-viewer` five times, then prints `Downloading packages failed five
times; check the network and try again.` and `Installation exited with status
1.` The repositories it consulted were `Daemonarchy-Dependencies`, `FreeBSD` and
`Daemonarchy`. pkg.FreeBSD.org's `latest` catalogue today (38,331 packages)
has `fltk` 1.4.5, `tigervnc-server` and `tigervnc-viewer-java`, and no
`tigervnc-viewer`. Both release candidates built after 1.4.1 also installed it
from `[Daemonarchy]` in their QEMU QA installs. Logs are kept in
`~/p0-tigervnc/` on madmax.

## Root cause

The 1.4.0 installer resolved and downloaded its packages from three places: the
ISO's own repository, Daemonarchy's application feed, and **pkg.FreeBSD.org at
install time**. The `daemonarchy` package depends on `tigervnc-viewer`, which
neither the ISO nor Daemonarchy's feed carried: it was taken from upstream's
moving `latest`. When upstream dropped the package, every new 1.4.0 install
failed. The image had not changed; its inputs had.

## Why QA did not catch it

- QA ran before the drift, against the live upstream of that day, and passed.
  A passing install only says the package set resolved at that moment.
- There was no gate for "the installer works with pkg.FreeBSD.org unreachable".
  Nothing in 1.4.0's process required the upstream closure to be hosted.
- The closure was not hosted: nothing Daemonarchy published could replace a
  package upstream withdrew.

## Why it was not caught after publication

- 1.4.0 was not announced (stated by the coordinator; not checked here), so
  there was no early set of users to notice.
- No step re-installed the published release after publication. The first
  recorded sighting was on a different machine (an MSI, with the 1.4.1 candidate);
  its fix merged about nine hours after 1.4.0 was published.
- The daily upstream-drift workflow only exists from #147.

## The error text misled

The failure ended with "check the network and try again". The cause was a
missing package, which retrying never fixes, and the five identical retries
made it look like a flaky connection. The pkg line naming the package was
there, but a user would read the last line. #147 made the installer resolve the
selection first (`pkg install -n`) and fail at once with "The selected packages
cannot be resolved from the configured repositories (a package or dependency is
missing or conflicts). This is not a network fault; downloading again will not
help." That text is from the code; it has **not been triggered in a run**.

## What fixed it structurally

- **Own packages for what upstream dropped (#147):** `origins.sh` publishes
  `net/tigervnc-viewer` and `x11-toolkits/fltk` (1.3.11) in Daemonarchy's feed
  and on the ISO.
- **Own closure shards (PKG-002, #159):** a signed snapshot of the upstream
  packages the image needs is hosted as GitHub release feeds (for 1.4.1,
  `packages-16-amd64-1.4.1-upstream`). The image prefers it; pkg.FreeBSD.org is
  the fallback.
- **A gate (`scripts/check-closure-feed.sh`):** before an ISO is built, the
  installer's roots must resolve from the ISO repository, the application feed
  and the shards alone, with the FreeBSD repository disabled. The runbook
  requires the mirror (`REQUIRE_PACKAGE_MIRROR=yes`).
- **The FreeBSD repository is off during the install transaction while a shard
  answers (#204)**, because pkg takes the newest version across repositories
  and would otherwise let `latest` override the snapshot. The installed system
  keeps its default FreeBSD repository.
- **Release verification:** `scripts/verify-release-assets.py` checks the
  closure feeds a release records, and the runbook's `verify` and `qa` steps
  count `[FreeBSD]` packages in the install log.
- **A daily drift workflow (`upstream-drift.yml`):** resolves the installer's
  roots against the published application feed and today's upstream catalogue.
  One scheduled run is on record, on 2026-10-31 10:54, and succeeded.

## What can still go wrong

Honest list from the code. None is known to be failing.

- **The mirror shard may not answer.** Each shard is tried three times. If some
  shards answer and one does not, the install stops with "package mirror ...
  unreachable after 3 tries: check the network and retry; the installer will not
  mix in pkg.FreeBSD.org", rather than take that shard's packages from `latest`.
  If no shard answers at all, the install uses pkg.FreeBSD.org's `latest` and is
  exposed to the same kind of drift.
- **Installed-system updates.** The installed system keeps the FreeBSD
  repository; `pkg upgrade` and any later `pkg install` take `latest`. A
  package withdrawn upstream can break a later upgrade or a package that
  depends on it.
- **Installer fetches at install or run time:** the optional source and ports
  checkouts (GitHub release feeds and `github.com/freebsd/freebsd-ports`); the
  Apple firmware download for MacBook Wi-Fi (Apple's recovery download); the
  optional NVIDIA and CUDA parts (the Rocky Linux container image from
  `dl.rockylinux.org`, a CMake release from GitHub, `dnf` inside the container).
- **First-run apps that fetch:** `daemonarchy-cudalab` (clones
  `github.com/jordanhubbard/cudalab` and fetches SDL from GitHub, upstream tip),
  `daemonarchy-wine` and Steam (`pkg install` of `wine-devel` and friends from
  the FreeBSD repository on first launch, plus Wine Mono and DXVK downloads).
  These fail at first launch rather than at install.
- **GitHub itself:** the mirror, the application feed, the checkouts and the
  extensions feeds are all GitHub release assets.
- **Closure completeness:** the gate proves the installer's roots resolve. A
  package selected later by the user is not covered. Whether the shard covers
  every optional selection is **unverified** beyond the runbook's resolution
  checks.

## Recommended gates

1. **Scheduled re-install QA of the published Latest release** against the live
   feeds, daily or weekly on madmax, using the same unattended QEMU harness as
   release QA, with the result kept as an artifact and a failure reported. It
   would have turned "a user told us" into "we saw it in hours".
2. **A post-publication smoke install as a release step:** after the release is
   public, download the published `.iso.xz`, check its `.sha256`, and run the
   unattended install before the release is called done. 1.4.0 had no such step.
3. **A second QA install with pkg.FreeBSD.org unreachable** (the host's
   resolver or a firewall rule) against the mirror alone. It is what the closure
   is meant to guarantee, tested end to end rather than by the gate's dry run.
4. **Error text:** keep the "not a network fault" message for unresolved
   packages and name the first missing package in it, and fix the progress
   label that still says "Downloading Daemonarchy packages from
   pkg.FreeBSD.org" while the snapshot is in use.
5. **Say so on old releases:** a note on the 1.4.0 release and in the release
   notes that 1.4.0 no longer installs and that 1.4.1 or later should be used.
   Published tags are immutable, so this is a note, not a replacement.

## Harness note (not part of the cause)

The first 1.4.1 install run used the release harness without its display
settings (`VIRGL_RENDER_NODE`, the desktop check): QEMU ran with `-display none`
and no GPU. One check, `sddm running`, failed there while the rest passed.
Rerun with the display settings the release QA uses (virtio-vga-gl through
`/dev/dri/renderD128`, then the desktop check), the same published 1.4.1 ISO
passed everything: `sddm running` ok, and "graphical login, input, native
browser and package manager" passed. So the failure came from running the
harness without a GPU, not from a 1.4.1 defect. That sddm does not stay up
without a GPU is the likely mechanism but was **not examined** (no guest log was
kept from the first run).
