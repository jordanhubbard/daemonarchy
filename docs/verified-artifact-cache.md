# Verified package retention and iterative installer cache

The package cache retains exact archive bytes in an append-only namespace and
checks them before every hit. `scripts/signed-package-snapshot.py` remains the
native authentication producer: it verifies the selected signed catalogue with
the pinned public key, lets native `pkg` verify fetched archives, then stores the
independently computed archive SHA-256. Cache transport does not qualify a build,
a changed ABI, package scripts, an application, an ISO or a release.

Preserve every existing package, port/object tree and cache. Select a fresh cache
namespace and fresh verification case; this implementation never replaces or
prunes existing entries. Failed pending copies remain available for diagnosis.
Duplicate successful content uses hard links. Concurrent identical publication
is atomic; conflicting content or selection records refuse instead of replacing
an earlier result. This does not coalesce compilation jobs or serialize package
transactions; the graph/dispatch coordinator owns those operations.

## Producer configuration

Add these optional top-level fields to the existing pinned signed-snapshot input:

```json
{
  "qa_mode": "iterative",
  "verified_cache_root": "/isolated/cache/daemonarchy-1.4"
}
```

The remaining [signed-snapshot inputs](signed-package-snapshot.md) and invocation
are unchanged. Use a small selected package list for bounded probes. A miss uses
the existing offline seed/public HTTPS fallback and native checksum verifier.
Only a successful native fetch/checksum result can reach cache publication.
A cache hit is rehashed and size-checked before serving and still passes through
native `pkg` verification. A corrupt entry fails closed with HTTP 502; it is not
silently replaced, repaired or redirected to a successful download.

Results include `verified_cache` with hits, misses, bytes saved, verification
seconds and per-selection events. The private case also retains
`verified-cache-events.json` when its frozen origin closes, including on a failed
native fetch. `bytes_saved` counts bytes served from verified cache instead of
fetching them from the publisher; it is not measured end-to-end speedup. Repeated
requests count as repeated transfers. No savings are claimed for compilation or
native acceptance, and no native execution is skipped because of a transport hit.

`qa_mode: "final-rc"` rejects a cache root or offline payload source and requires
the public GitHub/FreeBSD package publisher. The final QA driver must independently
acquire and verify the exact public ISO/boot assets and perform fresh installation
and installed boot against public signed feeds. This cache code does not perform
that VM/hardware matrix or authorize its publication.

## Stable cache API

`scripts/verified-artifact-cache.py` exposes:

```python
identity = selection_identity(
    {"meta.conf": meta_sha, "packagesite.pkg": catalogue_sha,
     "data.pkg": data_sha, "public_key": selected_key_sha},
    "obs-studio",
    {"version": "32.2.2_1", "abi": "FreeBSD:16:amd64",
     "archive_checksum": native_checksum,  # Opaque native pkg value, not SHA-256.
     "archive_path": "obs-studio-32.2.2_1.pkg", "download_bytes": 6517442})
cache = VerifiedCache(absolute_isolated_root)
stream = cache.lookup(identity)  # Verified open stream, or None on a genuine miss.
# After native catalogue/signature and archive-checksum verification succeeds:
cache.retain(identity, native_verified_archive, independent_archive_sha256)
metrics = cache.summary()
```

The selection schema is `daemonarchy/verified-cache-selection@1`. Exact signed
metadata and public-key hashes, package name/version/ABI, native checksum, archive
path and byte count all participate in the selection key. Cache entries use
`daemonarchy/verified-cache-entry@1`, binding the selection to the separately
observed archive SHA-256. Objects live at `objects/<archive-sha256>` and selection
records at `selections/<canonical-selection-sha256>.json`. Callers must not edit
these internals or treat the presence of a record as proof of runtime eligibility.
The trusted native producer owns admission. The API itself does not authenticate
arbitrary callers' assertions about signatures or dependency closure.

This key selects package transport bytes. It is deliberately separate from a
semantic compilation key, a lifecycle dispatch request, or a runtime compatibility
receipt. A changed signed catalogue can share unchanged object bytes after fresh
native verification but gets its own selection record. An archive envelope change
requires package review; compatible runtime/base changes require native
requalification; changed build inputs require graph-owned invalidation. The
[reuse inventory](package-reuse-inventory.md) records those separate decisions.

## Finite iterative cache service

A previously completed, reviewed native signed-snapshot case can serve an
iterative installer. Pin its exact `result.json` and original input configuration;
the service refuses missing authentication flags, mismatched input/key/catalogue
bindings or changed copied metadata, and verifies archive bytes before use. It copies retained products
into the selected cache namespace without modifying the native case.

```sh
python3 scripts/signed-package-snapshot.py /isolated/inputs.json \
  --sha256 INPUT_SHA256 --case /isolated/completed-native-case \
  --serve-result-sha256 RESULT_SHA256 --cache-root /isolated/cache/daemonarchy-1.4 \
  --bind CACHE_LISTEN_ADDRESS --port 8089 --serve-seconds 3600
```

Use an owned finite supervisor and retain service output. The default bind is
loopback; choose an explicit reachable address for a guest. The service freezes
the pinned signed metadata, serves verified selected objects, and redirects
missing selected archives to the configured public HTTPS publisher. The client
still authenticates the catalogue and verifies every fetched archive. The service
uses the result-bound authenticated repository database to allowlist signed
packages not included in an earlier limited payload fetch, so those become
verified-client public misses. Older results without a database binding can
serve only their recorded package subset. The service stops on a corrupt entry
and reports its failure and counters; it issues no new
native qualification. It rejects a `final-rc` configuration.

## Bhyve and installer selection

For iterative testing only, set `PACKAGE_CACHE_URL` to that service and supply
all three selected metadata hashes:

```sh
PACKAGE_QA_MODE=iterative \
PACKAGE_CACHE_URL=http://CACHE_HOST:8089 \
PACKAGE_CACHE_META_SHA256=META_SHA256 \
PACKAGE_CACHE_PACKAGESITE_SHA256=PACKAGESITE_SHA256 \
PACKAGE_CACHE_DATA_SHA256=DATA_SHA256 \
sh test-bhyve.sh /isolated/candidate.iso
```

The harness validates before host mutation or VM launch, then writes those fields
into its private CIDATA configuration. The installer validates and retains fresh
metadata preflight downloads before any disk changes, rejects changed metadata,
and keeps `signature_type: "pubkey"` and the image's selected public key. Use the
owned frozen service so the catalogue cannot move between preflight and native
import. The override applies only to the versioned signed Daemonarchy dependency
feed; the ISO's kernel-matched packages and FreeBSD upstream policy retain their
existing sources. Installed production repository configuration retains the public
versioned feed URL. This is a transport override, not an authentication override.

Use `PACKAGE_QA_MODE=final-rc` with no cache URL for final public QA. Both harness
and installer reject an override in that mode before destructive work. This
option alone does not prove that the supplied ISO came from the public release;
the final QA driver must record public binary acquisition and verification.

## Retained evidence and current qualification boundary

A scoped read of the retained 1.3.1 native assembly manifest recovered 1,463 archive
identities totaling 8,686,389,815 bytes. Its SHA-256 is
`eb27534e2c75a78fc7d18a0d652911f8f25108e055966c7339df4d1ae34bc2d7`.
It binds the historical qualified-provenance document with SHA-256
`db65b7ad849da846a08035ac5b6489dfbd4f2e4c4f0860a45c9b09154fdfc196`.
That document admits five retained archives for 1.3.1: CEF, Chromium, the Hyprland
preview share picker, OBS and tensaku. Its scope includes the FreeBSD 1600029
installed-root dependency/file checks, Chromium/OBS version probes and CEF dynamic
loading. Final ISO/VM/public checks are separately scoped. These records are
available for targeted provenance recovery; missing public fields do not require
blanket rebuilds. They do not independently qualify unchanged payloads for 1.4.

A bounded native-host-independent retention probe used the existing published
OBS archive, verified its exact public SHA-256, and checked source hash/mtime
preservation. With all three selected catalogue hashes, the selected public-key
hash and opaque native checksum bound, it recorded one miss, one rehashed hit,
6,517,442 bytes served from cache and approximately 0.022 seconds for retention
plus lookup. This is transport evidence, not fresh native signature/ABI testing
or measured release speedup. Existing artifacts and caches remained available.

Controller regressions exercise same-size corruption rejection without fallback,
selection/ABI/version mismatch refusal, immutable duplicate retention, verified
HTTP hits and public miss redirects, selected metadata corruption, authentication
preservation, and final-RC rejection before VM launch. A new native signature/cache
run and exact VM installation/public-distribution acceptance remain required;
the active kernel worker's capacity is coordinated separately.
