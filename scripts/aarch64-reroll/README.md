# aarch64 re-roll scripts

The scripts that produced the staged 1.4.1 aarch64 artifacts on 2026-10-30
([record](../../docs/aarch64.md#worker-record-aarch64-staging-at-the-post-14-base-2026-10-30)).
They are the exact commands that ran on the arm64 worker (`barmy`, a VMware
guest on Apple silicon) and on the amd64 signing host (`daemon.local`), kept so
the next roll can repeat them. Paths and revisions are hard-coded for that
roll; change `REV` (daemonarchy-src), `PREV` (daemonarchy-ports) and the
directory names before reusing them. Run each as root, in order, detached with
`daemon(8)`; each appends a line to `/home/jkh/a141/state` so a run can be
resumed.

| Script | Where | What |
| --- | --- | --- |
| `step1-base.sh` | worker | `/usr/src` to the selected revision, incremental `buildworld`, `buildkernel` and release sets into a set cache, checked against the MANIFEST |
| `step2-jail.sh` | worker | poudriere ports tree at the ports pin, a tar-method jail from the new sets, the previous package repository copied under the new jail, and a bulk dry run |
| `step3-bulk.sh` | worker | `poudriere bulk -b latest -J 2` of the arm64 package list |
| `step4-checkout.sh` | worker | the product checkout, the src and ports checkout packages and the checkout catalogue |
| `step5-collect.sh` | worker | the unsigned application feed from every package poudriere built (`pkg-repo.sh collect`) |
| `step6-iso.sh` | worker | the arm64 ISO with `build-iso.sh ARCH=aarch64` |
| `step7-iso-release.sh` | worker | the release ISO from a fresh clone of main with both published closure shards in `PACKAGE_MIRROR_URLS` and `REQUIRE_PACKAGE_MIRROR=yes` |
| `fetch-closure.sh` | signing host | the upstream archives of the closure shard, fetched with `parallel-fetch` for the aarch64 ABI |
| `aarch64-ports.list` | worker | the 34 origins `step3-bulk.sh` builds (the aarch64 `ISO_ORIGINS`, the live packages and the installer set); `x11-themes/aether` is on it and fails, as documented |

A later addition to the installer's roots (Epiphany, the aarch64 default browser) is a
delta shard, not a new run: resolve with the extra root, keep only the packages absent
from the published shard, fetch them with `parallel-fetch`, and stage them under the next
tag (`-upstream-2`) with `package-feed-stage.py stage`. Published tags are immutable.

Signing never happens on the worker: the release key stays on the signing host.
Move the unsigned feed there, run `pkg repo FEED KEY`, and bring back only the
catalogue files (`meta`, `meta.conf`, `packagesite.pkg`, `data.pkg`).

**Trap (step 2).** A tar-method jail records its version as `16.0-CURRENT`; the
older src-method jails recorded `16.0-CURRENT 1600029`. When the reused
repository's `.jailversion` differs from the new jail's, poudriere says "newer
version of jail, cleaning all packages" and would rebuild every package (763 of
1,404 here, including LLVM at over two hours). The OSVERSION is the same, so set
the copied repository's `.jailversion` to the new jail's string and re-run the
dry run: it then queues only the ports that changed (13).
