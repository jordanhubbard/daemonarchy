# 1.4.1 plan: deferred from 1.4

**Status:** planned. Opened on 2026-10-29 by operator decision. Work starts when
1.4 is published.

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
  longer.** First measurement, from the live8 GPU-backed QEMU install on
  madmax (one run, `work8/install.log`): the fetch phase took 2565 s and the
  package install 141 s of a 2715 s install. 784 of 930 archives and 3.78 GB
  had been fetched when the log ends at the install phase, about 1.5 MB/s
  through QEMU user networking; 1186 packages (16 GiB installed) are
  installed. So on that run the time is the download, not the install, and
  the DAG-ordered install above would save little by itself; parallel fetch
  and a smaller or local package set matter more. The ISO already carries
  the Daemonarchy repository (`file://`); the bulk comes from
  `pkg.FreeBSD.org`. Things to compare against Omarchy before drawing
  conclusions: its package count and download size, parallel downloads and
  nearby mirrors on the Arch side, and compression. Hours on real hardware
  (Wi-Fi, one connection) are reported but not measured here; the next step is
  timing a fetch on the MSI and MacBook, then choosing between parallel
  fetch, a smaller default set, and shipping the large packages on the ISO.

## Not changed

Fresh installs, signature and feed verification, the physical matrix and
publication remain 1.4 acceptance.
