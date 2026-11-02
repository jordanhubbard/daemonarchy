# Draft retained profile (daemonarchy product repo): provenance and unknowns

DRAFT, unqualified. Nothing here asserts a build, test, signing, acceptance or release
result, and no key is read. Regenerate with `draft-retained-inputs.py` after staging
`sdk/bin` (untracked) on the worker.

## Grounded in the repository and its documents
- `draft-build-iso`: `sh build-iso.sh`, "Build the image" step 5 in `HACKING.md`.
- `draft-master-release-verify`: `bash scripts/master-release.sh verify`, the documented
  key-free verification step (xz test, hashes, size budget, version string, ISO
  contents). The `feed` (signs with the builder's release key), `qa`, `sticks`, `all`,
  `packages`, `secureboot` steps are deliberately not in the profile.
- `draft-docs-tests` (docs stage): `tests/docs-lifecycle.py` and
  `tests/docs-release-sync.py`, CI steps "Documentation graph matches the Literate AI
  authority gate" and "Documentation and release media agree"
  (`.github/workflows/release-14-controls.yml`). Mapping them to the docs stage is the
  drafter's choice.
- `draft-ci-tests`: the `python3 tests/X.py -v` steps of `release-14-controls.yml`
  (version-sync, release-check-1.4, package-mirror-plan, install-trace, gpu-report,
  build-timing-record, login-trace, parallel-fetch, package-feed-stage/upload/manifest,
  release-prepare-fill, install-trace-baseline, 96 case names found statically).
- `draft-ci-isolated-tests`: the `python3 -I tests/X.py -v` steps (visual-sdk,
  plugins-and-games, sdk-windows, extension-bundles, installer-extensions,
  installer-sdk-audit, installer-progress-stats, gui-package-manager/transaction/window,
  301 case names), run under `python -I` via `unittest-report.py`, which records the
  outcomes it observes at run time.
- Release policy: the existing tracked `literate.release.json`, unchanged. Its gate is
  `python3 scripts/release-check-1.4.py`.
- Tools: copies (untracked, staged on mudflap) of `/bin/sh`, `/usr/local/bin/bash`,
  `/usr/local/bin/python3.12`, `/bin/echo`. Dependency closure: zero members.
- `scale_limits`: not added. The tree (about 787 members, 31 MB) fits the defaults
  (1,024 pinned files, 4,096 catalog files, 64 MiB); all eight locks are current.

## UNKNOWN, with reason
- Toolchain closure: shared libraries, Python stdlib and everything `build-iso.sh`
  calls (poudriere, makefs, xorriso, mkisofs-class tools, `xz`) are not captured; the
  repository defines no bootstrap capture for this project.
- Worker facts: `JAIL`, `PTREE`, `ARCH`, `POUDRIERE_DATA`, `OUTDIR`, the master-release
  config file, `MAIN_COMMIT` and its state file are environment/config the repo leaves
  to the builder; none was inspected (poudriere, `/usr/daemonarchy` are out of bounds).
- Output mapping: `build-iso.sh` writes to the poudriere images directory, not a
  retained output root; `master-release.sh verify` works on that state. No document maps
  either onto `{output_root}`.
- The prerequisite packages build (`master-release.sh packages`, `poudriere bulk`), the
  secureboot step and the signed feed are outside this profile; whether `iso` can run
  without them is defined by the worker's existing state, which is unknown.
- Test coverage not in the inventory: the shell suites CI runs (`tests/*.sh`) have no
  per-case report format; `tests/gui-package-gtk.py` (CI says it skips without PyGObject
  and a display, and no skip is authorized); the pre-step `scripts/seal-games.py
  --check`; the `native-graph.yml` and `remote-worker.yml` suites.
- Test outcomes and skip reasons: nothing was run; some cases may skip or fail off
  FreeBSD or without network.
- Accept action and policy: independent VM/QEMU/physical acceptance (`test-qemu.sh` on a
  QA host, hardware runs) is not defined as a retained action; `echo` placeholder.
- Whether the retained execution may use root, which `build-iso.sh` requires.
