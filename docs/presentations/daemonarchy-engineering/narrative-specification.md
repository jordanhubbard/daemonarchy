# Daemonarchy engineering deck: narrative specification

## Audience and purpose

Developers and contributors: people who build, test, package or release Daemonarchy, or
want to start. They know FreeBSD's `make buildworld installworld` and `make install` in a
port and need to know how Daemonarchy's pinned, signed, evidence-bound loop relates to
them, what role Literate AI (litai) plays in 1.5.x, what advantages it gives, and how to
contribute.

## Thesis

Daemonarchy is five repositories pinned together by full commit and shipped as signed
feeds and images. The upstream FreeBSD commands remain the reference; the daemonarchy way
wraps them in a build, test and release loop whose inputs and results are recorded. Literate
AI is adopted in place in 1.5.x: it validates authority, locks Component contracts, holds
the release gate and refuses to invent a receipt, while the original scripts remain the
implementation. Framework-executed native builds are the 1.5.1 work, and no speed-up is
claimed yet.

## Arc

1. **Orientation** (slides 1 and 2).
2. **Architecture** (slides 3 and 4): the five repositories, their pins, and where a change goes.
3. **The daemonarchy way** (slides 5 to 7): upstream make commands versus the pinned loop, the build and release loop, and inner loops by kind of change.
4. **Delivery and components** (slides 8 to 10): feeds and signing, the installer, native package resolution as a model of the evidence style.
5. **Literate AI** (slides 11 to 15): its role, the real `litai verify` gate output, advantages, limits, and a change from start to finish.
6. **Verification and operations** (slides 16 to 18): test harnesses and what they do not prove, diagnostics.
7. **Open work and joining in** (slides 19 to 21): aarch64, forking, how to contribute.

## Tone rules

- Run or read, do not assume: the gate table on slide 13 is the output of `litai verify .`
  on the branch (Literate AI 1.4.0, development source): authority pass, locks pass (8),
  receipt FAIL because `verification/current.json` has not been committed.
- Name what Literate AI is not yet: not the build executor, not a generator, no framework 1.4.0 release.
- Do not claim that `make buildworld` from the installed checkout is a supported Daemonarchy workflow; the repository does not say so.
- Plans are PLANNED, limits are LIMIT; evidence counts come from the queue as of the move to 1.5.1.

## Claim ledger

| Claim | Source in the repository |
| --- | --- |
| Five repositories, what each holds, where a change goes | `HACKING.md` (The repositories, Where a change goes) |
| Pins by full commit, release record, feed and tag naming | `HACKING.md`, `verification/release-1.5.0.json`, `release/current.json` |
| Build loop: poudriere, `pkg-repo.sh`, `build-iso.sh`, tests, release gate | `HACKING.md`, `origins.sh`, `pkg-repo.sh`, `build-iso.sh`, `scripts/release-check-1.4.py` |
| Inner loops: installer, ports, Omarchy link and sync | `HACKING.md` (Changing things, Working on Daemonarchy from Daemonarchy) |
| Signing discipline, one session per release | `HACKING.md` (Releasing), `docs/mastering-1.5.0.md` |
| Native package plan: 16 checks, 952 and 960 identities, unsigned | `docs/native-package-plan.md`, `verification/native-package-plan-development.json` |
| Literate AI role, nine goals, eight Components, original source retained | `PROJECT.md`, `SKILL.md`, `literate.project.json`, `components/` |
| Gate results | `litai verify .` run on this branch |
| Retained native checkpoint: 69 checks, 0 failures | `verification/native-retained-acceptance.json` |
| Deferred goals and evidence counts | `docs/roadmap/release-1.5.1.md` |
| aarch64 open work, virtio-net stall and fix (daemonarchy-src PR #59) | `docs/aarch64.md`, `docs/release-1.5.0.md` |
| Forking today | `HACKING.md` (Forking Daemonarchy), `docs/roadmap/release-1.5.1.md` |
| Contributing practice | `HACKING.md` (Contributing) |

## Rebuild

`python3 ../build_deck.py engineering` reads `deck-specification.md` in this directory and
writes `daemonarchy-engineering.pptx`; add `--render` to also write the PDF. See `../README.md`.
