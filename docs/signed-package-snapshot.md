# Signed catalogue and package payload checks

`scripts/signed-package-snapshot.py` uses native FreeBSD pkg to authenticate a
frozen catalogue with an explicitly pinned public key, then fetch and verify
selected package archives. It retains the exact catalogue inputs, command logs
and independent SHA-256 observations of fetched files in a fresh private case.
It performs no installation and issues no lifecycle or release receipt.

This complements the [dependency graph collector](package-dag.md) and
[native resolution checker](native-package-plan.md). Authentication and payload
integrity do not establish a complete install selection, package side effects,
kernel/module compatibility, final 1.2 input admission or safe parallel commit.

The [development checkpoint](../verification/signed-package-snapshot-development.json)
uses the immutable published `packages-16-amd64-1.1.1` feed as a regression fixture.
Native pkg authenticates its catalogue and verifies all 510 archives
(3,020,892,622 bytes). The final code repeats that verification through read-only
seed reuse, and every SHA-256/size matches the independently captured GitHub
asset identities. The [complete public inventory](../verification/signed-snapshot-1.1.1-payloads.json)
retains the exact package identities and hashes. Wrong-key, altered-signature and
corrupt-payload native controls refuse, including a diagnostic with native exit
zero. Twelve snapshot controls pass on both the controller and native FreeBSD.
This qualifies the tested pkg 2.8.4 active catalogue/payload path for this fixture;
auxiliary legacy-client compatibility and final 1.2 inputs remain unqualified.

## Reviewed inputs

Use an allocated native FreeBSD worker with enough free space for the selected
archives plus a 2 GiB reserve. The checker requires root for pkg's private
database ownership rules. Keep payloads on the native worker rather than copying
them to a controller under disk pressure. Never modify a published feed or its
tags while qualifying a new release.

Capture the three metadata files through the existing HTTPS acquisition path and
review their exact hashes against the expected release identities. Keep the
original acquisition evidence. Select the public trust key from reviewed product
authority, not from an untrusted catalogue. A hash pin alone does not establish
the key's authority; native pkg must verify the signature with that selected key.
The key must use PEM `PUBLIC KEY` form. PEM private-key forms are rejected before
case creation. Review the selected key as public material; never supply a private signing key.

Author a private JSON input file:

```json
{
  "schema": "daemonarchy/signed-package-snapshot-inputs@1",
  "pkg": {"path": "/usr/local/sbin/pkg", "sha256": "<reviewed executable SHA-256>"},
  "abi": "FreeBSD:16:amd64",
  "osversion": 1600028,
  "repository": {
    "id": "Published",
    "metadata": {
      "meta.conf": {"path": "snapshot/meta.conf", "sha256": "<reviewed SHA-256>"},
      "packagesite.pkg": {"path": "snapshot/packagesite.pkg", "sha256": "<reviewed SHA-256>"},
      "data.pkg": {"path": "snapshot/data.pkg", "sha256": "<reviewed SHA-256>"}
    },
    "public_key": {"path": "daemonarchy.pub", "sha256": "<reviewed key SHA-256>"},
    "payload_source": {"url": "https://example.invalid/versioned-repository"}
  },
  "packages": "all",
  "maximum_download_bytes": 4294967296,
  "fetch_timeout_seconds": 1200
}
```

Input paths are relative to that file or absolute. Final input components cannot
be symlinks. The pkg executable must be root-owned and unwritable by others, and
is pinned before and after execution. This identifies the installed native tool;
it does not supply source-built SDK provenance.

Use `packages: ["package-name"]` for a deliberately limited selection. Use
`packages: "all"` to require every package in the authenticated catalogue.
`maximum_download_bytes` bounds the signed size total before fetching; the
checker also checks actual free space. Fetch deadlines may be one to 3600 seconds.
For offline replay, replace `payload_source` with
`{"directory": "/absolute/retained-payload-directory"}`. Offline files are read
without modification and still undergo native checksum verification. A replay
does not weaken the public-key or metadata pin requirements.

Providing both `url` and `directory` reuses correctly sized, regular seed files
read-only and redirects missing or wrong-size files to the HTTPS publisher.
Reused bytes are checked again by native pkg; a same-size corrupt seed refuses
rather than being promoted to a passing archive. This supports a fresh retry
after a terminal failed attempt without modifying its evidence or redownloading
every completed payload. Never reuse a still-running attempt's output directory.
Results distinguish offline requests from HTTPS redirects; those counts are
transport observations, not proof of parallel installation or a performance gain.

## Bounded parallel acquisition

The explicit input schema `daemonarchy/signed-package-snapshot-inputs@2` adds
`fetch_workers` (one to sixteen) and optional `fetch_batch_packages` (one to 128,
default 32). Keep every trust, executable, metadata, selection, budget and timeout
field from version 1. Version 1 retains its serial operation and result shape;
parallel options on version 1 refuse instead of silently selecting another mode.

After native authentication and selection, one coordinator schedules bounded
batches against separate private copies of the native database and cache. Every
fetch keeps the same frozen repository URL and uses native pkg's checksum
verification. Each completed batch must also pass exact file inventory, size,
independent SHA-256, unchanged catalogue and empty installed-database/cache checks
before its files become available in the case's shared payload directory.
Retained batch copies use exclusive hard links to avoid duplicating payload
bytes. Database copies and retained command-log limits are included in the disk
reserve check. All fetch children share one deadline; failure, diagnostic,
deadline or interruption stops queued work and reaps the owned children.

The case's `events.jsonl` is an ordered
`daemonarchy/package-progress-event@1` journal, bound to the exact input and
authenticated database pins. It records actual started, verified, failed and
cancelled batches. Verified-byte counts include seed reads and describe archive
verification, rather than network throughput. Consumers continue to show a
waiting/finalization state after the last batch until the final result exists.
The atomically published `daemonarchy/signed-package-snapshot@2` result binds the
closed journal and records actual peak concurrency. The journal alone never
establishes completed acquisition or installation permission.

Failed batches, partial payloads and logs remain in their original private case.
Retry into a new case, optionally selecting a terminal attempt's `payloads`
directory as a read-only seed. The new run still authenticates the catalogue and
reverifies every selected archive through native pkg. Do not reuse a live case.
Parallel acquisition does not establish parallel installation, final-release
selection, an installer/GUI integration, a lifecycle receipt or a performance gain.
Controller command-protocol fixtures exercise scheduling and failure guards;
native signature, corruption, concurrency and serial-parity acceptance remain
required before this new mode is qualified.

Pin the completed input file and run from reviewed source:

```sh
sudo python3.12 scripts/signed-package-snapshot.py /absolute/inputs.json \
  --sha256 <reviewed-input-file-sha256> \
  --case /absolute/fresh-private-case
python3.12 tests/signed-package-snapshot.py -v
```

Occupied cases refuse. The case holds copied metadata, the selected public key,
input description, separate database/cache/configuration, command stdout/stderr,
fetched payloads and a result only after all required checks pass. Earlier and
failed cases must remain retained. Command failures, diagnostics even with exit
zero, timeout, interruption and missing/extra/incorrect-size archives refuse.

## Frozen origin and native verification

pkg 2.8.4 binds its imported repository database to the repository URL. Switching
from a frozen file URL to a remote payload URL invalidates that database even
when repository refresh is disabled. The checker therefore owns a finite
loopback-only HTTP origin for the entire operation. It serves only the pinned
metadata bytes. After successful native public-key import, it allowlists the
authenticated package paths and redirects those paths to the selected HTTPS
publisher, or streams the matching offline files read-only. Unknown paths refuse.
No signing material or arbitrary local file is served.

The same native repository URL remains in place through import and fetch.
`REPO_AUTOUPDATE` and plugins are disabled, and every command uses case-local
configuration and state. The native operation is `pkg fetch -Uy`, optionally
with `-a`; no installation, scripts, triggers or competing package transactions
are requested. Native pkg validates the archives using their authenticated
catalogue checksums, including its tagged checksum formats. Each fetched file
must have its exact authenticated path and size, and receives an independent
SHA-256 observation. The authenticated repository database must remain unchanged
during fetching, the private installed-package count must remain zero, and the
separate private cache must remain empty.

The origin is closed at completion or failure. The shared command runner
enforces internal deadlines and handled signal cleanup for its owned process
group while preserving partial output. An observation timeout is not permission
to restart a still-live attempt; inspect its process handle and retained case.

## Evidence boundary

A passing `daemonarchy/signed-package-snapshot@1` result records the selected
public-key and metadata hashes, native executable/version, exact fetched archive
inventory, observed SHA-256 hashes and phase timings. `verified_all_catalogue_payloads`
is true only for a successful all-package run. A subset is never relabeled as
complete. `dependency_plan_qualified` and `installation_authorized` remain false,
and no lifecycle receipt is minted. These observations must be renewed for the
exact final release selection and composed with its other required evidence.

The implementation uses the native
[pkg fetch contract](https://github.com/freebsd/pkg/blob/main/docs/pkg-fetch.8).
It deliberately delegates signature and checksum verification to pkg rather
than replacing native checksum encodings with a new cryptographic convention.
