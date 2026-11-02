# Draft retained profile (daemonarchy product repo): provenance and unknowns

DRAFT, unqualified. Nothing here asserts a build, test, signing, acceptance or release
result, and no key is read, named or copied. The `authority-reviewed` marker and every
`--authorize-*` flag belong to the operator and were not used.

Regenerate in this order, on the amd64 builder (mudflap), from the project root:

1. `python3.12 tools/retained-draft/closure-inventory.py --spec tools/retained-draft/closure-spec.json --output tools/retained-draft/closure-inventory.json`
2. `python3.12 tools/retained-draft/stage-closure.py --inventory tools/retained-draft/closure-inventory.json --root .`
   (writes the untracked `closure/`; add it to `.git/info/exclude`)
3. `litai-venv/bin/python tools/retained-draft/draft-retained-inputs.py --manifest-out /abs/outside/tree/manifest.json`

## What changed from the first draft

- Toolchain closure is real: 79 captured tools (every command named by `build-iso.sh` and
  the scripts it runs, the `poudriere image`/jail/common helper commands found by grepping
  poudriere 3.4.99, `python3.12`), their 56 shared libraries (observed with `ldd`), the
  Python 3.12 stdlib subset the retained scripts import, and poudriere's `share/` and
  `libexec/`. Owners (pkg name/version or "base-system"), sizes, modes and sha256 are in
  `closure-inventory.json`. The old `sdk/bin` was four copies and no libraries; the tracked
  product `sdk/visual` tree is no longer mislabelled `toolchain` (it is `source` now).
- `runtime_library_paths` is `closure/toolchain/lib`, so captured binaries load captured
  libraries first.
- Ambient inputs that cannot live in the captured tree are recorded by identity and
  re-observed by the first action, `draft-ambient-preflight` (17 entries: the dynamic
  linker, the `/bin/sh` shebang interpreter of `poudriere`, the poudriere registry, jail
  anchors, the ports tree `daports141`, the package catalogue, release sets, the checkout
  catalogue and the public secure-boot bundle, signature and certificate).
- Environment and output mapping: `run-build-iso.sh` plus `build-iso.env` (below).
- Docs: `draft-docs-tests` (the two CI docs suites) plus `draft-docs-tree`, a whole-tree
  check of all 138 project-authored Markdown files (`docs/**`, root, `components/**`,
  `secureboot/**`, `overlay/**`, `skills/**`, `workflows/**`, `sdk/**`, `tools/**`):
  UTF-8, relative links and images present, fragments match a heading.
- Accept: `draft-accept-image` (`accept-image.py`), a static image verifier separate from
  `build-iso.sh` and `master-release.sh verify`. `master-release.sh verify` is no longer an
  action: it reads `$WORK/out-<MAIN_COMMIT[0:12]>` under a bash config file and cannot be
  mapped onto `{output_root}`.
- `python -I` actions now also pass `-B`: `-I` ignores `PYTHONDONTWRITEBYTECODE`, so the
  isolated suites would have written `.pyc` files into the frozen input snapshot.

## Environment and output mapping for build-iso.sh

The profile cannot pass environment variables (the retained command environment is PATH of
captured tool directories, private HOME/TMPDIR, `LANG=C`, plus `LD_LIBRARY_PATH` from
`runtime_library_paths`). `run-build-iso.sh OUTDIR` therefore sources `build-iso.env` and
sets: `ARCH=amd64 JAIL=16r2303b36 PTREE=daports141`, `POUDRIERE_ETC`/`POUDRIERE_DATA` and
`PACKAGES_DIR` under `/usr/daemonarchy/rev2-20261030`, `SET_CACHE_DIR` (the release sets),
`CHECKOUT_CATALOG` (`checkout-feed-1.5.0/checkouts.json`),
`PACKAGE_REPOSITORY_TAG=packages-16-amd64-1.5.0`, the closure-feed
`PACKAGE_MIRROR_URLS` with `REQUIRE_PACKAGE_MIRROR=yes`, the public
`PACKAGE_REPOSITORY_PUBLIC_KEY` (tracked `keys/pkg-repo-1.3.1.pub` in the snapshot) and the
public `SECUREBOOT_BUNDLE`/`SIGNATURE`/`CERTIFICATE`. Values follow `master-release.sh`
`step_iso` and its defaults. `OUTDIR` is `{output_root}/images` and `ISO_STAGE_PARENT` is the
run's private `TMPDIR`; the ISO, `.xz` and `.sha256` files are the sealed output `images`.
No signing key path is set anywhere.

## Retained execution and root

- `build-iso.sh` documents "run as root" and the wrapper refuses a non-root user: poudriere
  `image` mounts and runs in a jail. The retained executor itself has no general root
  refusal (only the optional FreeBSD `secondary_access` views and ACL custody require root
  and a disposable-allocation inspector, neither of which this profile uses), so this
  action may run as root if the operator runs `litai build ... --allow-host-execution` as
  root. Root runs trusted project code unconfined: the framework states its same-user
  workspace "is not an OS sandbox". Running `litai` as root, on which worker, and whether
  the private run root and caches are acceptable under root is the operator's call.
- Contrast: `daemonarchy-src` `build.py` refuses root, so that repo's run must be
  unprivileged. The two cannot share one invocation.

## UNKNOWN, with the evidence examined

- Which JAIL/PTREE/CHECKOUT_CATALOG produced the 1.5.0 ISO already on mudflap
  (`out-5dd9da334d93`, state file 2026-11-01). `master-release.sh` defaults
  (`JAIL=16r2303b36`, `PTREE=daports141`), the only populated release package set
  (`poudriere-data/packages/16r2303b36-daports141`, 1470 packages) and the 1.4.1 `master.env`
  agree, but the config for the 1.5.0 run was not found (the `/root` scripts were not read).
- Whole-jail identity. `/usr/local/poudriere/jails/16r2303b36` has root-only directories, so a
  full tree digest needs root; only `param.h`, the kernel and `libc` are anchored. The
  package set (8.1 GB) is identified by its catalogue `packagesite.pkg` (which carries each
  package digest) and a names-and-sizes listing, not by hashing every package.
- Poudriere's complete helper-command set. The 79 tools are grep-derived from
  `image*.sh`, `jail.sh`, `common.sh` and `include/*.sh`; `bulk.sh`/`repo.sh`/`pkg` helpers
  were not enumerated. `run-build-iso.sh` appends `/sbin:/bin:/usr/sbin:/usr/bin` to PATH for
  anything missed, so the closure is not hermetic. `share/poudriere/MANIFESTS` (an absolute
  symlink to `/usr/local/share/freebsd/MANIFESTS`, used by jail creation) is not captured.
- Relocation. Nothing captured was executed for acceptance. `python3.12 -I` from `closure/`
  was only used to check that the stdlib subset resolves relative to its prefix, and
  `bsdtar`, `jq`, `xorriso`, `poudriere version` start. Whether `poudriere image` works from
  a relocated prefix is untested.
- Whether `poudriere image` writes under `POUDRIERE_DATA` (logs, cache) outside the retained
  output root. `poudriere-data/{cache,images,logs,packages}` exist; nothing was run.
- Network: `REQUIRE_PACKAGE_MIRROR=yes` makes the build resolve the closure feed on GitHub
  releases (`packages-16-amd64-1.4.1-upstream`); those bytes have no retained identity.
- Secure Boot: the bundle, signature and certificate are public artifacts hashed by the
  preflight. The 1.5.0 bundle is whatever the operator's key window last produced; this
  draft does not change `secureboot/*` or any boot artifact.
- Acceptance. `verification/retained-project-acceptance.json` (the withheld independent
  policy) is not authored: its cases must run executable build exports, and the product's
  output is an ISO. `draft-accept-image` is a static check only, and the ADR says a legacy
  zero-exit command labelled acceptance produces no independent acceptance observation.
  VM/QEMU acceptance (`test-qemu.sh`, run by `master-release.sh qa` on the QA host
  madmax.local) is not possible on mudflap (no `/dev/vmm`, no KVM in the guest) and is not
  a retained action; physical hardware acceptance is the operator's.
- Test coverage not in the inventory: the shell suites (`tests/*.sh`, no per-case report
  format), `tests/gui-package-gtk.py` (skips without PyGObject and a display; no skip is
  authorized), `scripts/seal-games.py --check`, the `native-graph.yml` and
  `remote-worker.yml` suites.
- Test outcomes and skip reasons: nothing was run in the retained lifecycle. Read-only
  observations made while authoring (scratch outputs, not evidence): `accept-image.py` over
  the existing 1.5.0 image reported every check true; `docs-tree-check.py` reported 138
  files and no findings; `ambient-preflight.py` reported all 17 entries unchanged.
- `scale_limits`: not added. 1,624 members, 82 MB are within the defaults.
