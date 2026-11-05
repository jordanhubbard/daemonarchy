# Daemonarchy marketing deck: narrative specification

## Audience and purpose

Prospective users and decision makers: people who know either FreeBSD or Omarchy (or
neither) and want to decide whether Daemonarchy is worth trying. They need to know what
it is, what is the same as FreeBSD, what is different, what they get, how it installs,
what has evidence behind it, and where it is honestly limited. The deck does not sell
beyond the evidence: every slide names the repository document it draws from.

## Thesis

Daemonarchy is the Omarchy desktop on FreeBSD: a finished, opinionated Hyprland desktop
on an operating system with ZFS boot environments, jails, bhyve and DTrace, installed by an
Omarchy-style installer. It is real, published and signed on amd64, community-validated on
aarch64, and candid about what has not been verified on physical hardware.

## Arc

1. **What it is** (slides 1 to 3): the one-sentence definition, the screenshot, and the union of two projects.
2. **Same and different** (slides 4 and 5): FreeBSD underneath, so the base, tools and hardware layer are FreeBSD's; the table of differences is the answer to "what is different from FreeBSD".
3. **What you get** (slides 6 and 7): the System > FreeBSD menu and what shipped in 1.5.0, each with its evidence status.
4. **How it installs and what it costs** (slides 8 and 9): the five-step install and the measured install weight, including the uncomfortable numbers.
5. **What is verified** (slides 10 to 12): evidence in hand against not verified, the architecture and hardware table, and the aarch64 screenshot labelled QEMU.
6. **Trust, updates and what is next** (slides 13 and 14): signing, what `pkg upgrade` does and does not do, and the 1.5.1 plan marked as plans.
7. **Call to action** (slide 15): download, read the limits, report results, hack on it.

## Tone rules

- State the limit next to the claim. Use the tags VERIFIED, NOT VERIFIED, LIMIT and PLANNED.
- Never imply a plan is shipped. 1.5.1 items are plans until evidence is retained.
- No benchmarks beyond those the repository records, each with its scope (one machine, one run, version measured).
- Do not claim physical-desktop evidence for aarch64 or the NVIDIA RTX Spark laptop.

## Claim ledger

| Claim | Source in the repository |
| --- | --- |
| Omarchy desktop on FreeBSD 16.0-CURRENT, OSVERSION 1600029, unaffiliated | `README.md`, `release/current.json` |
| What FreeBSD adds: boot environments, snapshots, jails, bhyve, DTrace | `README.md` (What FreeBSD adds) |
| Differences: installer, signed feed, owned source fork, own versioning, upgrade scope | `README.md`, `HACKING.md`, `docs/roadmap/release-1.5.1.md` |
| 1.5.0 features and their evidence | `docs/release-1.5.0.md` |
| Install weight and fetch-versus-install times (1.4.0 line) | `docs/install-weight-vs-omarchy.md` |
| aarch64 status, QEMU evidence, virtio-net stall | `docs/aarch64.md`, `docs/release-1.5.0.md` |
| virtio-net fix merged in daemonarchy-src PR #59, shipping in 1.5.1 | daemonarchy-src pull request 59 (merged 2026-11-04); 1.5.1 shipping is a plan |
| RTX Spark deferred; no physical-desktop evidence | `docs/application-note-rtx-spark.md`, `docs/release-1.5.0.md` |
| Trust and signing | `README.md`, `HACKING.md`, `docs/mastering-1.5.0.md` |

## Rebuild

`python3 ../build_deck.py marketing` reads `deck-specification.md` in this directory and writes
`daemonarchy-marketing.pptx`; add `--render` to also write the PDF. See `../README.md`.
