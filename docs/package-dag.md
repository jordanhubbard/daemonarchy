# Pinned package dependency graphs

`scripts/package-dag.py` collects complete name/origin dependency closures from
reviewed, SHA-256-pinned `packagesite.yaml` JSON-lines catalogues. It records
separate graphs for installation selections, sharing transitive dependencies
once within each graph. Official and Daemonarchy repositories use the same
format. Root selections must explicitly include their GPU and optional packages.
This is the first PKG-001 implementation step; actual release catalogue captures,
native solver validation and transaction execution remain unfinished.

## Inputs and use

Capture catalogues through the existing trusted native repository workflow.
Retain its repository-signature verification evidence separately. Extract the
JSON-lines file from each exact retained repository archive without refreshing
the feed in place. A SHA-256 pin detects changed input bytes; it does not verify
a repository signature or authenticate its publisher.

Create a selection file beside the captured catalogues:

```json
{
  "schema": "daemonarchy/package-selection@1",
  "abi": "FreeBSD:16:amd64",
  "osversion": 1600028,
  "catalogues": [
    {
      "id": "Daemonarchy",
      "path": "daemonarchy-packagesite.yaml",
      "sha256": "<reviewed SHA-256 of those exact catalogue bytes>",
      "url": "https://example.invalid/versioned-daemonarchy-repository"
    },
    {
      "id": "FreeBSD",
      "path": "freebsd-packagesite.yaml",
      "sha256": "<reviewed SHA-256 of those exact catalogue bytes>",
      "url": "https://example.invalid/pinned-freebsd-repository"
    }
  ],
  "repositories": {"daemonarchy": "Daemonarchy"},
  "selections": {
    "desktop": ["daemonarchy"],
    "desktop-nvidia": ["daemonarchy", "nvidia-driver"]
  }
}
```

Replace the example roots, ABI, OSVERSION and repository URLs with the exact
release selection. Use `repositories` to bind every overlapping package name
explicitly; no repository priority or candidate version is guessed. There may
be only one record per package name in a given catalogue. Catalogue paths are
relative to the selection file, or absolute. Repository URLs must use HTTPS
without credentials. Retain source catalogue archives and their identity and
signature evidence with the native release inputs.

Pin the completed selection file itself, then collect to a fresh output:

```sh
python3.12 scripts/package-dag.py /absolute/selection.json \
  --sha256 <reviewed-selection-file-sha256> \
  --output /absolute/new-package-graph.json
python3.12 tests/package-dag.py -v
```

The collector performs no network requests or package operations. Existing
outputs refuse. Invalid input refuses before opening an output; a later output
I/O failure remains a failed attempt whose partial file must be preserved.
Catalogues are bounded to 256 MiB each, records to 2 MiB, combined packages to
100,000 and repositories to sixteen. Graph traversal is iterative and includes
deep transitive dependencies without a Python recursion-depth limit.

## Retained evidence and boundaries

The `daemonarchy/package-dag@1` result binds selection/catalogue hashes,
repository provenance, archive paths and hashes, exact package versions,
origins, ABI, flavour annotations, canonical manifest hashes, native constraints,
download bytes and installed-byte estimates. Each selection records roots,
edges and deterministic dependency-first order. Shared dependencies count once;
totals are metadata estimates, not measurements of actual peak disk use.

Missing dependencies, origin conflicts, cycles, ambiguous repository bindings,
duplicate JSON keys/records, unsafe archive paths, wrong ABI, newer OSVERSION
requirements, missing native OSVERSION annotations and changed pins refuse.
Architecture-independent packages may omit OSVERSION annotations. The native
kernel and external-module compatibility closure needs separate qualification.

Recorded dependency versions may differ from the selected catalogue versions.
These edges remain in `version_resolution_required` with both versions; a
newer version is not silently treated as compatible. Original native solver
constraints (including dependency formulas, shared-library requirements and
conflicts) remain visible. The collector does not implement pkg's solver, test
file/script side effects or grant transaction permission: every result retains
`native_solver_qualified: false` and `installation_authorized: false`.

Next integrate actual native pkg resolution and signed catalogue acquisition,
capture every real release selection, and qualify hash/installed-file evidence.
Then implement the shared transaction coordinator and progress events, with safe
parallel installation, failure/retry/recovery and measured native performance.
Graph independence alone does not authorize concurrent package commits.

The field mapping follows the upstream
[pkg manifest implementation](https://github.com/freebsd/pkg/blob/main/libpkg/pkg_manifest.c).
The collector preserves FreeBSD version strings without replacing
[pkg's native version comparison](https://github.com/freebsd/pkg/blob/main/docs/pkg-version.8)
with lexical or semantic-version ordering.
