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

## Not changed

Fresh installs, signature and feed verification, the physical matrix and
publication remain 1.4 acceptance.
