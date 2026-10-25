# Package reuse provenance inventory

`scripts/package-reuse-inventory.py` creates a metadata inventory and compares
all previous and selected package names before compilation. This is an advisory
preflight for [PERF-002](roadmap/release-1.4.0.md), not a lifecycle adapter,
compilation scheduler, native qualification receipt or cache admission service.
It writes JSON to stdout and never modifies installed packages, archives,
caches or previous products. Retain every existing installed/prebuilt package,
port output and cache for 1.4; put new products in isolated output roots.

## Public feed inventory

Export `gh release view TAG --json assets,url` to a new JSON file and extract
`packagesite.yaml` from the existing or metadata-only downloaded
`packagesite.pkg`. The catalogue contains JSON lines despite its filename.

```sh
python3 scripts/package-reuse-inventory.py catalogue \
  --catalogue /isolated/metadata/packagesite.yaml \
  --assets /isolated/metadata/release-assets.json > /isolated/metadata/previous.json
python3 scripts/package-reuse-inventory.py compare \
  --previous /isolated/metadata/previous.json \
  --selected /isolated/metadata/selected.json > /isolated/metadata/ledger.json
python3 tests/package-reuse-inventory.py
```

The importer joins exact archive paths and sizes to public asset SHA-256
metadata. It refuses missing, duplicate, malformed or unlisted payloads. Only
`meta`, `meta.conf`, `packagesite.pkg` and `data.pkg` are excluded as repository
metadata. This does not verify catalogue signatures or hash payload bytes;
use the existing signed-package-snapshot tooling on the native worker for that.

The `daemonarchy/package-reuse-inventory@1` schema contains a `packages` list.
Each row requires `name`, `origin`, `version`, `identities`, and an optional
`artifact` containing `path`, `sha256` and `bytes`. Names must uniquely identify
the selected package variant; conflicting variants must be resolved explicitly.
All rows in the union are reported, including additions and removals.

`identities` separates build inputs (`source_inputs`, `port_inputs`, `options`,
`flavor`, `generated_inputs`, `toolchain`, `sysroot`, `build_dependencies`,
`command`, `environment`, `output_format`) from runtime constraints (`abi`,
`osversion`, `runtime_dependencies`, `runtime_abi_contracts`). Missing or null
means unknown; an empty mapping/list is an explicit known-empty input. Producers
must supply exact identities and complete transitive closure. Free-form values
are compared structurally; the tool cannot certify their authenticity or closure.
The importer deliberately does not infer a complete port input identity from a
Git annotation, a known flavor from a package name, empty dependencies from an
absent `deps` field, or ABI compatibility from matching ABI text.

## Decision boundaries

| Decision | Meaning |
| --- | --- |
| `new_package` / `removed_package` | Added to or removed from the selected closure; no existing-byte admission implied. |
| `rebuild_required` | A known build input or origin changed; retain the old archive. |
| `needs_package_review` | Package version changed; inspect source changes and envelope before scheduling compilation. |
| `needs_requalification` | Known runtime constraints or OSVERSION changed without a known build-input change. |
| `blocked_missing_provenance` | Unknown inputs prevent determining unchanged action identity. |
| `blocked_missing_artifact` | No retained archive identity is recorded. |
| `needs_retained_byte_verification` | Complete declared identities match; signatures, bytes and evidence still require verification. |

Unknown identities remain explicit even when another known input supplies a
rebuild or requalification reason. OSVERSION alone never requests recompilation.
Requalification requires actual selected-base installation, ABI and package-script
checks, executable/application tests and evidence bound to retained payload
bytes. Failed compatibility or changed headers/static dependencies can then
require a rebuild. The tool never claims a cache hit and reports unmeasured
bytes/time savings as null. It does not yet validate native requalification
receipts or distinguish payload changes from changed archive envelopes.

## Observed published 1.3.1 baseline, 2026-10-25

The [published feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64-1.3.1)
listed **208 assets**: 204 application archives totaling **1,884,661,660 bytes**,
plus four repository metadata assets. The downloaded `packagesite.pkg` SHA-256
was `b4d298a49b8c9542847a592bbd7cddb35ad2fcf8da8a60c378cb2d0e61246437`,
matching its GitHub asset digest. No application archive was downloaded or
independently hashed during this metadata-only observation.

| Payload | Published size | Published SHA-256 |
| --- | ---: | --- |
| `chromium-154.0.8037.57_2.pkg` | 151,274,247 | `e81a45507040c957303138f6c837a01873157827f8f3e3b578c6833a52a72177` |
| `cef-152.0.6.pkg` | 121,530,309 | `31dcd655bab385a5a134f54d4c28414a1f71bd0bb798151035879be8897a72b3` |
| `obs-studio-32.2.2_1.pkg` | 6,517,442 | `a3444865cf47768cdd86b7a0107f5087242864c0f942231d2c4c3532ddd56b30` |
| `libreoffice-26.8.1.1.pkg` | 150,449,188 | `d6ae7a70a93f4fbc22b2abde1665e5b15bff87da6c3e28d7fefa0eba7ed373c2` |

Catalogue OSVERSION annotations were `1600029` for 184 packages, `1600028`
for five and absent for 15. Public catalogue metadata supplies options and
runtime dependency names/versions where present, but lacks complete source,
transitive build, toolchain, generated-input and runtime ABI identities.
Consequently a metadata-only unchanged-feed comparison reports **204
`blocked_missing_provenance`**, **zero admitted hits**, and unknown savings.
This does not revoke historical 1.3.1 qualification or mean the retained bytes
are unusable. It identifies the evidence still needed for future cross-release
admission. The historical
[1.1.1-to-1.3.1 inventory](evidence/release-1.3.1-package-reuse-inventory.md)
remains a distinct 510-package pre-publication observation.

Retained native staging records can supply provenance absent from the public
catalogue. A scoped read of the existing 1.3.1 package assembly manifest found
1,463 retained archive identities, selected source `d63d77f4eb3cc29e16510f7bdec73602e27c2844`,
ports `b785784219af455a9ce4fd70c59bc96ba77f469f`, jail OSVERSION `1600029`,
and bindings to image-install and reuse-provenance evidence. Its assembly kind
is `selected-base-installed-reuse`. This is a larger staged package inventory,
not the 204-package public application feed. Those records remain available
for targeted provenance recovery and requalification; missing public fields
are not a reason to blanket-rebuild retained outputs. This tool does not yet
import or validate that native manifest or its referenced receipts.

The linked historical qualified-provenance document records five archives as
`admitted_for_release`: CEF, Chromium, the Hyprland preview share picker, OBS
and tensaku. Its CEF, Chromium and OBS SHA-256 values match the public metadata
above. Those are recorded 1.3.1 decisions, not new 1.4 admissions; this
metadata-only pass did not rerun or independently validate the referenced
native probes. The retained ad hoc staging inventory producer is also available
for recovering its earlier tree comparisons; it is not an installed release
planner or a replacement for current native evidence.
