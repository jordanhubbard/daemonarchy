# Cross-repository retained input graph

`scripts/release-input-graph.py` locks exact Git selections, verifies canonical
retained input/profile records and separates build input changes from native
ABI requalification. It does not execute builds, declare a cache hit, create a
receipt or supply release authority. Issue #39 and the 1.4 roadmap own completion.

Use the interpreter from the matching retained-capable installed LitAI
configuration. The 2026-10-25 controller checks use the isolated release gate
runtime from framework `c345e652b91863e72526f25f8e31a03ec34bec01`, wheel SHA-256
`e3d8d2eb307c68dd1137025f6be0476bc790281b01d4ff995701f77f7897527b`.
The ambient older CLI lacks the ownership extension. No language Flavor is
created to accommodate that older installation. Those records are retained
unchanged. Later controller checks run under installed LitAI 1.4.0 (public git
`0a267a6646f20e3a635a1f870042b6b034f026a1`); the hosted
`release-14-controls` job installs that exact commit into a job virtual
environment rather than relying on the runner's bare `python3`.

```sh
"$LITAI_PYTHON" scripts/release-input-graph.py SELECTION.json \
  --repo daemonarchy=/path/to/product-object-store \
  --repo daemonarchy-src=/path/to/source-object-store \
  --repo daemonarchy-ports=/path/to/ports-object-store \
  --repo daemonarchy-desktop=/path/to/desktop-object-store \
  --repo omarchy-freebsd=/path/to/compatibility-object-store \
  --retained-root source:truncate=/path/to/reviewed-native-snapshot \
  --previous PRIOR_GRAPH.json --output /path/to/new-evidence/graph.json
```

The selected repositories must all be available locally to this invocation.
Bindings are controller-local arguments; private worker paths and addresses do
not belong in committed selections. Native snapshot bindings are optional for
units whose complete retained inputs are already tracked Git objects. Native
SDKs, captured compilers and generated profile records normally require an
explicit snapshot. Output is exclusive and must be outside inspected inputs.
Git lazy fetching and interactive credentials are disabled; absent objects are
an error, never permission to download a complete source tree implicitly.

## Records and ownership

`native/release-graph/selection.json` is a development input selection, not a
qualified release lock. It names all five required repositories at exact commits
and the source/ports upstream ancestry bases. `controller-input-lock.json` binds
three available controller-side Git trees. It explicitly omits native source and
ports proofs and selects zero units. That partial result must not be scheduled
as the full 1.4 graph.

Selection schema `daemonarchy/release-input-selection@1` has `repositories`
and `units`. Each repository has `id`, public `repository` URL, full `revision`
and an `upstream` record containing a public repository URL and exact ancestral
revision, or null for an independent root repository. The adapter verifies the
commit and tree objects and refuses an upstream revision that is not ancestral.
It never updates a checkout or fetches another branch.

Each unit has these fields:

- `id`, owning `repository`, `manifest` and `profile`; both references contain a
  repository/snapshot-relative `path` and exact byte `sha256`.
- `architecture`: exactly one typed variant, `amd64` or `aarch64`
  ([ARCH-001](roadmap/active-work.md#arch-001-add-aarch64-as-a-second-supported-architecture-for-140)).
  The variant table is recorded in
  [`native/release-graph/architectures.json`](../native/release-graph/architectures.json)
  and must equal the adapter's own table. A profile `target` that names an
  architecture (`amd64`, `x86_64`, `aarch64`, `arm64` or a package ABI) must name
  the unit's.
- `options`, native port `flavor` or null, `compiler`, `sysroot`, and
  `execution_identity`. Compiler is an exact tool identity from the canonical
  profile. Sysroot is the canonical retained `sdk` role closure identity.
- `generated_inputs`: exact retained paths/digests, `producer` references in
  `UNIT#ACTION` form and declared producer `output` paths. Missing units, actions,
  output ownership and cross-unit build edges refuse graph construction. A
  producer reference still requires native output/closure admission.
- `dependencies`: typed `build`, `runtime` or `test` edges with `unit`, `identity`,
  `artifact_identity`, `members`, `selected_version`, and `version_constraint`,
  plus optional ordered `declarations` (`declaration`, `requirement`, `target`)
  recording every producer variable merged into the edge. A `test` edge is a
  separate qualification edge: it is bound into `qualification_inputs` only,
  never into a build key or build order, and a changed or requalifying test
  producer moves its consumer to native ABI requalification.
  Build identity means relevant producer payload contents; runtime identity means
  the selected ABI contract. Artifact identity retains exact archive/output
  provenance. Every retained `dependency` member needs a typed edge. Shared
  libraries used for linking require a build edge for their actual link inputs;
  they cannot simply be labeled runtime to avoid invalidation.
- `base_abi`: positive FreeBSD `osversion`, exact `contract` identity and
  `kernel_bound` boolean. `unresolved_inputs` explicitly names known closure gaps.

The manifest/profile are actual framework `RetainedProjectManifest` and
`RetainedProjectProfile` records. Canonical `component_ownership` is mandatory;
lexical tree discovery is insufficient. SDK/toolchain and dependency role
identities must match the profile, and tools must be byte members of its declared
SDK/toolchain closure. For snapshots, the framework's
`verify_retained_project_inputs` checks actual bytes, modes and links. Tracked
members additionally match the exact selected Git blobs. Untracked source/build
inputs require explicit generated producers.

Every owner is registered against the product's real Component catalog: the
adapter loads the authored `components/` catalog through the installed
framework (`project_component_roots` and the locked-generation catalog reader,
the same authority `litai project validate` uses) and applies
`require_registered_retained_owners`. An owner whose Component coordinate is not
declared, or whose authoring identity is stale, refuses the unit. Each unit
records its `registered_owners`, and the graph records the exact
`component_catalog` it was checked against. Registration is not admission: full
retained/native admission remains a separate required gate.

Admission is exact across units, not only within one unit. Every retained
member resolves to one canonical Component owner. When several selected units
in one repository retain the same path, they must agree on its owner, authoring
identity and bytes; a disagreement refuses the graph as an ambiguous owner.
Within a unit, each dependency member belongs to exactly one producer unit; a
member claimed by edges to two different units refuses as an ambiguous edge.
The collected report is a deep snapshot that never aliases caller selection
values.

## Translating producer observations

`release-input-graph.py translate REQUEST --request-sha256 SHA --output NEW` turns
the source fork's `daemonarchy/source-unit-input-observation@1` and the ports
fork's `daemonarchy/ports-unit-input-observation@1` records into graph units.
The request (`daemonarchy/release-input-translation@1`) pins every observation
and optional hosted summary by digest, relative to the request's directory, and
names each unit's repository, owning Component and optional retained bindings.

- Unit ids are `REPOSITORY:UNIT[@FLAVOR]:ARCHITECTURE`. The architecture comes from
  the observation (`target`/`target_arch` for source, `architecture` for ports)
  and must be a typed variant.
- Options carry every selected native setting: source `WITH_`/`WITHOUT_`
  options, `FLAG:` overrides, configuration digests and payload scope; ports
  Boolean options, `MAKE:` variables and the package database context.
- Ports edges are grouped by origin and kind, so an origin declared in several
  variables (`BUILD_DEPENDS` and `LIB_DEPENDS`) becomes one typed edge with all
  its declarations. `LIB_DEPENDS` keeps both its build and runtime edges.
- The request's `test_edges` decision is mandatory. `qualification` keeps
  `TEST_DEPENDS` as typed test edges, and `exclude` records them as excluded in
  the provenance. Neither refuses the observation, and both decisions are
  explicit.
- Edges become graph edges only through explicit bindings (identity, artifact,
  members, version). An unbound edge becomes an `unresolved_inputs` entry, as do
  every producer unresolved input (absolute native paths are reduced to their
  basename), an incomplete recursive or compiler/header closure and a diagnostic
  package database. A unit with an unresolved input never receives a reuse
  recommendation.
- Owners must be registered Components. Observations claiming admission or
  ownership, untyped edges, bindings for unobserved or excluded edges, revision
  mismatches and hosted summaries that do not corroborate the unit, commit, tree
  and architecture all refuse.

Units with retained manifest/profile bindings form a `selection` that
`collect` accepts directly. Otherwise the result holds `draft_units` that list
the missing retained records, and `selection` is null. The result is never an
admission.

[`translation-example-request.json`](../native/release-graph/translation-example-request.json)
and its [result](../native/release-graph/translation-example-result.json)
translate `usr.bin/truncate` and `archivers/liblz4`. The hosted summaries above
corroborate their unit, commit, tree and architecture. The hosted runs retained
the decoded make values only by digest, so the observation files under
`translation-example/` are schema fixtures modelled on those Makefiles, not
native output. Both units remain drafts because no retained profile exists for
them yet. The focused test checks that the result is reproducible.

## Architecture variants

The architecture is part of both `build_inputs` (with its package ABI) and
`qualification_inputs`, so no build key, ABI qualification or retained product
can be shared between amd64 and aarch64 even when every other input is equal.
Dependency edges between units of different architectures refuse graph
construction and comparison. A previous unit whose architecture differs from the
current unit with the same id is reported as `architecture-differs-no-reuse`,
a changed state that also blocks its build consumers; it is never a hit, a
requalification or a verified reuse. Package archive retention already keys on
the package ABI (`scripts/verified-artifact-cache.py`), so an amd64 archive
cannot satisfy an aarch64 selection there either. Only the amd64 variant has
qualified native workers; [the aarch64 plan](aarch64.md) owns the rest.

## Invalidation and qualification

`build_inputs_identity` is a canonical content identity over relevant retained
members, build/generate actions, tool bytes, compiler/toolchain/sysroot,
execution identity, native options/flavor, generated inputs and build dependency
payloads. Runtime-only dependency members are excluded. Git commit labels,
worker identity and test/release policy envelope fields do not independently
force compilation. The full profile/manifest identities remain recorded.
A producer repair or changed build dependency blocks dependent output reuse until
its resulting payload identity is proved.

Comparison re-derives every unit's `build_inputs_identity` and
`qualification_inputs_identity` from its typed records in both the previous and
current graph and refuses a forged identity, an unknown schema or a dependency
edge to a unit absent from that graph. A unit whose previous or current closure
named `unresolved_inputs` never receives an unchanged recommendation. Changes
propagate conditionally by edge kind: a new, rebuilt, blocked or unresolved
build producer blocks consumer output reuse; any changed or requalifying
producer reached over runtime edges, including runtime cycles, moves an
otherwise unchanged consumer to native ABI requalification.

`qualification_inputs_identity` binds exact OSVERSION/base ABI provenance,
all dependency versions/constraints, contracts, archive identities and dependency
members. A compatible userland OSVERSION/runtime-only change therefore asks for
fresh native ABI qualification instead of automatic recompilation. Kernel-bound
units include base ABI/OSVERSION in build inputs. Changed headers, SDKs,
compilers, static build inputs and relevant generated inputs invalidate builds.
This separation does not prove ABI compatibility or validate a version constraint.
Native installation/scripts/executable/application tests and verified payload
custody must establish those facts before any retained output is admitted.

Every unit remains `admitted: false` with `native_receipt: null`. The comparison
reports conservative recommendations, including unchanged-input verification,
ABI requalification, build-input changes and unresolved closures. They are not
cache-admission decisions. The framework dispatcher owns execution identities,
resource policy, verified output production and fresh per-request admission;
the artifact transport owns verified byte movement.

## Current evidence and remaining producer work

The selected desktop port pins desktop `ec2a00824ec95b342c0c095657ac725c56f0528b`;
`x11-wm/omarchy` pins compatibility
`800bf89b6ec6d0cfaaebb46a2440f56c3f997c8a` and fetches upstream
`basecamp/omarchy` version 4.0.4. It does not select the owned
`jordanhubbard/omarchy` fork. Keep that fork excluded unless producer selection
changes. The upstream Omarchy distfile remains a separately pinned external
source input; admission must preserve the port's distinfo identity.

The owned source's existing `prepare-retained-profile.py` prepares a selected
header/parser/utility closure, including captured bootstrap tools. It is not a
complete source-unit producer graph. Existing product tree discovery and signed
package DAG tools retain useful inventories, but cannot establish conditional
native build edges, all ports options/flavors, generated outputs or ABI contracts.

Still required: native source/ports Git ancestry renewal; authoritative per-unit
producer metadata across the selected closures; all Component registration;
compiler/header/sysroot/generator observations; Chromium/CEF native ABI evidence;
complete retained native profiles, receipts and output custody; full package
comparison and cache decisions; distributed execution and equivalent timing;
exact feed/ISO/native/VM/hardware/release qualification. A first bounded native
ancestry probe timed out during an active kernel build. The admitted repeat on
the idle primary FreeBSD worker ([record](../native/release-graph/native-ancestry-probe-20261026.json),
[script](../native/release-graph/ancestry-probe.sh); no fetch, no repository
writes, 60-second deadlines) shows source upstream `a3d1d4e8` is an ancestor of
selected `d63d77f4` (exit 0). The ports check fails: selected
`b785784219af455a9ce4fd70c59bc96ba77f469f` is absent from the worker's
`/usr/ports` object store (exit 128). An admitted single-commit fetch
([record](../native/release-graph/native-ancestry-probe-20261026-fetch.json))
then hit its 1800-second deadline (exit 124). `/usr/ports` is a shallow clone,
so fetching the commit without a bound deepens far past the 224-commit range
GitHub reports. HEAD, branch, refs and tracked files are unchanged; an
incomplete temporary pack remains in place. The rerun probe still fails for
ports (exit 128) and passes for source. GitHub's compare result is hosted
reference only, not native evidence. A separately admitted bounded fetch
([record](../native/release-graph/native-ancestry-probe-20261026-bounded.json))
fell back to `--depth=300` after the server refused `--shallow-exclude` with a raw
commit ID. It completed in 32 seconds (exit 0). It rewrote `.git/shallow`,
deepening all six previous boundaries; HEAD, branch, refs and tracked files are
unchanged and the earlier temporary pack remains. The rerun probe, using the same
script with no fetch, now passes for both repositories: ports upstream `a7c9a97b`
is an ancestor of selected `b7857842` (exit 0), and source still passes. A shallow
boundary can only hide ancestry, so the positive result is a real parent path. No private-worker compilation or
VM was launched by this stream; private producer/profile work stays scheduled
centrally. The hosted metadata observations below have their own bounded scope.

Portable checks use the matching installed interpreter:

```sh
"$LITAI_PYTHON" tests/release-input-graph.py -v
```

These use temporary Git object stores, canonical framework contracts and actual
CLI subprocesses. They verify byte/ownership/closure refusal, typed dependency
projection, changed source/generated/header/compiler/options/flavor/executor
invalidation, kernel/userland OSVERSION distinction, stable unrelated commits
and policy envelopes, and preservation of existing output/input trees. They also
refuse ambiguous cross-unit owners and dependency edges, forged previous-graph
identities and unknown edges, and check runtime-edge requalification
propagation and non-reuse of a previously unresolved closure.


## Scoped actual-command projections

The source fork's observer can inspect retained bmake/filemon records through the
existing immutable trace-capture helper. `release-input-graph.py trace` joins those
exact read/exec facts to current canonical retained snapshot members and owners:

```sh
"$LITAI_PYTHON" scripts/release-input-graph.py trace \
  --manifest SNAPSHOT/manifest.json --manifest-sha256 MANIFEST_SHA256 \
  --profile SNAPSHOT/profile.json --profile-sha256 PROFILE_SHA256 \
  --trace TRACE_OBSERVATION.json --trace-sha256 OBSERVATION_SHA256 \
  --snapshot SNAPSHOT --action CANONICAL_ACTION_ID \
  --bind /native/input/root=retained/prefix --output NEW_PROJECTION.json
```

Projection files are created exclusive mode `0600`. Literal native command/path
facts remain private evidence; publish only safe IDs/digests and allowlisted
semantics, and never commit real raw trace/config/environment captures.

The whole snapshot is verified with the installed canonical byte/mode/link
verifier before projection. Native root bindings resolve ownership; command/cwd
paths remain literal because paths can change `__FILE__`, debug info or generated
output. The result includes a canonical per-action retained submanifest and a
separate projected identity. Unknown accesses, directories, relative/dirfd paths
and uncaptured environment remain explicit gaps. Shared-library reads stay input
candidates even during compilation; file suffixes do not establish independence.

A package-only plist/install/envelope change can alter the package projection
without altering compile projection when actual complete phase traces prove those
usage boundaries. The regression exercises this with canonical snapshots and
actual scoped access records. It is not native acceptance. The original broad
unit comparison remains conservative until producer facts close its action split.
A changed compile/header/static/generated/command input still invalidates the
corresponding phase. Neither a directory-tree hash nor a filename classification
can authorize an unchanged-compilation claim.

The raw trace scope (`compile`, `link`, `generate`, `package`) is an observation
phase. It is not the new framework semantic contract's userland/kernel payload
scope. New semantic-payload re-admission and trusted signed-release binary-input
adoption need their distinct qualified installed contracts, current policies and
native proofs. This adapter does not import a WIP source tree or replace the
selected c345 lifecycle binding. Prior immutable build evidence is never rewritten.


## Hosted native metadata observations

The source and ports producer branches now exercise their production invocation
factory and decoder against actual native BSD make in a hosted FreeBSD
15.0-RELEASE-p13 amd64 VM, actual OSVERSION 1500068. The source probe queries
`usr.bin/truncate`; the ports probe queries `archivers/liblz4` using explicitly
empty diagnostic package state, not selected-release installed facts. Existing
package database bytes are unchanged and no build targets are requested.

Safe summary records retain exact Git checkout/tree, compiler digest, input and
driver identities, hosted run URLs and original artifact summary byte digests:

- [Source observation](../native/release-graph/hosted-source-40249878784.json):
  [run 40249878784](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/40249878784) passes.
- [Original ports failure](../native/release-graph/hosted-ports-40249884809.json):
  [run 40249884809](https://github.com/jordanhubbard/daemonarchy-ports/actions/runs/40249884809)
  failed because an isolated make search path omitted system `sys.mk`.
- [Renewed ports observation](../native/release-graph/hosted-ports-40250211477.json):
  [run 40250211477](https://github.com/jordanhubbard/daemonarchy-ports/actions/runs/40250211477)
  passes after adding `/usr/share/mk` alongside the owned ports Mk directory.

The exact hosted image has no Python or Git. The controller therefore renders a
base-shell probe with the production invocation factory and checks its output
with the production decoder; the full Python observer does not execute in the
guest. Actual host/compiler facts are reported without overriding OSVERSION.
Raw private commands/environment/configuration are not committed. These are
native metadata invocation/parser controls, not compiler execution, complete
filemon byte-at-build-time closure, selected-release context or admission.
Every summary keeps recursive closure, selected-release context, native profile
and cache admission false. The summary records are not lifecycle receipts.
