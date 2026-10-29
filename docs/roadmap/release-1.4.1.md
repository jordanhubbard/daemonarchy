# 1.4.1 plan: deferred from 1.4

- **Status:** active
- **Owning queue item:** [INSTALL-PERF-001](active-work.md#install-perf-001-make-exact-image-installation-at-least-10x-faster)
- **Supporting queue items:** [PKG-001](active-work.md#pkg-001-implement-the-release-package-dag-and-safe-parallel-transactions),
  [NET-001](active-work.md#net-001-make-the-installer-network-bring-up-proactive-and-robust)
- **Completion / archival evidence:** pending exact-image MSI, MacBookPro16,1
  and VM baselines; 10x physical improvement; exact network matrix; integrity,
  desktop and failure/recovery acceptance.

Opened on 2026-10-29 by operator decision; 1.4.0 is published.

The measured installation target is tracked as
[INSTALL-PERF-001](active-work.md#install-perf-001-make-exact-image-installation-at-least-10x-faster)
and [issue #134](https://github.com/jordanhubbard/daemonarchy/issues/134).

1.4 supports forward installs and `pkg`-based upgrades of a running system. The
items below were 1.4 acceptance rows. They moved here so they no longer block
1.4. None of them is claimed as done by 1.4.

## Scope

- **Exact-image installer network matrix** ([ledger A14](1.4-coverage-ledger.md),
  [NET-001](active-work.md#net-001-make-the-installer-network-bring-up-proactive-and-robust)).
  VM runs on the final image for several NICs with one DHCP server, broken DHCP
  DNS, blocked public DNS with a user resolver, blocked ICMP, a wrong clock
  (fixed by NTP, then by hand) and an unattended CIDATA install, with the
  retained `/tmp/daemonarchy-network/log`. Then the no-cable MacBookPro16,1
  run. No VM-level harness exists yet; `tests/network-bringup.sh` covers each
  case only against shimmed commands.
- **Upgrade of an existing Daemonarchy system through the installation image,
  and rollback** (part of [ledger A11](1.4-coverage-ledger.md)). Nice to have.
  `pkg upgrade` of a running system is unaffected and stays in scope for every
  release.
- **Faster package installation in the installer.** Installing packages takes
  hours, and `pkg install` fetches and extracts them largely in sequence. The
  plan: fetch in parallel up front (a worker pool over the whole closure,
  since downloads have no ordering constraint), then install along the
  dependency DAG from the leaves up, so a package never waits on one that is
  not yet installed and independent subtrees run together. The catalogue
  closure tooling in `tests/package-dag.py` and `scripts/` already computes the
  DAG. Open questions to settle first: whether `pkg add` of many packages
  concurrently is safe (it takes a database lock, so extraction may need to be
  parallel while registration is serialised), where the time actually goes
  (network fetch, ZFS extraction, post-install scripts or `ldconfig` runs;
  measure on the installer before designing), and whether to ship a
  pre-extracted tree for the largest packages instead.
- **Why an Omarchy install takes about ten minutes and ours takes much
  longer.** The retained live8 GPU-backed QEMU disk now has a
  [content-identified recovered observation](../../verification/installer-live8-recovered-baseline-development.json):
  the fetch phase took 2,565 s and package installation 141 s of a 2,747 s
  terminal diagnostic interval. The event pipe measured 784 of 930 network
  archives and 3,778,340,358 bytes; exact native catalogues identify the 1,189
  installed packages as a 5,553,478,434-byte archive closure and 16,847,424,955
  installed bytes. The original run did not measure its host link, so this is a
  historical design observation, not the required equivalent-link VM baseline.
  On that run the time is the download, not the install, and
  the DAG-ordered install above would save little by itself; parallel fetch
  and a smaller or local package set matter more. The ISO already carries
  the Daemonarchy repository (`file://`); the bulk comes from
  `pkg.FreeBSD.org`. Things to compare against Omarchy before drawing
  conclusions: its package count and download size, parallel downloads and
  nearby mirrors on the Arch side, and compression. Hours on real hardware
  (Wi-Fi, one connection) are reported but not measured here; the next step is
  timing a fetch on the MSI and MacBook, then choosing between parallel
  fetch, a smaller default set, and shipping the large packages on the ISO.
- **Target: install at least 10 times faster.** Baseline first: time the
  whole install (fetch, extraction, registration, post-install) on the MSI,
  the MacBookPro16,1 and a VM, with a fixed package set and a recorded link
  speed, and keep the numbers in `docs/`. The 10x is measured against that
  baseline, not against the 45 minutes of the one VM run above. The VM run
  shows why a faster scheduler alone cannot reach it: 3.78 GB at 1.5 MB/s is
  most of the time. The plan, in order of expected gain: (1) take the
  download out of the install path by carrying the closure on the ISO or an
  attached local cache, so a first install reads from media; (2) fetch
  whatever remains in parallel from a nearby mirror; (3) extract in parallel
  along the dependency DAG and serialise only registration; (4) trim the
  default package set (1186 packages, 16 GiB installed) so the install does
  less. Acceptance: the 10x figure on both physical machines, the signed-feed
  verification unchanged, and the package set still installing a working
  desktop.

- **Loose ends found in 1.4.0.** The MSI touchpad runs in polling mode (the I2C-HID
  interrupt is not wired through). Only I2C controller 0 (`8086:7f4c`) of the
  Arrow Lake-S PCH is recognised in `ig4`, so a touchpad on another function would
  not attach. Linux's ARL004 interrupt-ordering workaround for the VMD controller
  is not ported; stress the RAID-mode NVMe path before relying on it. The VMD-
  disabled mode was not retested. CUDA Unified Memory (`cudaMallocManaged`)
  crashes through the Linuxulator, and cudalab builds against SDL 3.2 because 3.4
  needs a newer libXi than Rocky 9. The CUDA step of the installer ran only by
  hand on a running system; run it inside the installer on an NVIDIA machine.
  Physical reruns of the exact 1.4.0 image on the MSI and MacBook are still owed.

## Not changed

Fresh installs, signature and feed verification, the physical matrix and
publication remain 1.4 acceptance.
