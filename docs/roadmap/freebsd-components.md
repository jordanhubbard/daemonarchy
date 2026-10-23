# Complete FreeBSD source and ports Component coverage

- **Status:** active
- **Owning queue item:** [COMP-001](active-work.md#comp-001-model-complete-freebsd-source-and-ports-trees-as-components)
- **Completion / archival evidence:** pending canonical full-tree coverage, native lifecycle and exact release receipts

The operator requires all of `/usr/src` and all of `/usr/ports` to be represented
as Literate AI Components. G8 in [PROJECT.md](https://github.com/jordanhubbard/daemonarchy/blob/main/PROJECT.md)
owns this requirement. Two opaque checkout inputs or two whole-tree build
wrappers cannot satisfy it. Preserve the upstream implementations and normal
Git contribution workflow while putting their complete inventories, selected
dependencies and evidence under canonical Component authority.

## Boundaries and composition

| Area | Component boundary and required relationships |
| --- | --- |
| Ports | Each real `category/origin` is represented, including origins not installed in the release. Native metadata supplies build, run, library, fetch, extraction, patch and test dependencies. |
| Port variants | Architecture, OS version/ABI, FLAVOR, OPTIONS and toolchain selections qualify the origin's lock and outputs. A single origin can produce multiple packages; an installed package list is not the complete ports catalog. |
| Base userland | Native buildable programs, libraries and shared build units have Component contracts. Source directory layout helps discovery; native make metadata and reviewed mappings determine actual boundaries and dependencies. |
| Kernel | Core, architecture/platform support, drivers and modules have explicit ownership and relationships. The configured kernel composes a target selection; shared compilation/link constraints do not imply every driver can be built independently. |
| Loader and boot | Loader variants, boot libraries and platform support compose the boot products and their trust/symbol inputs. They retain their actual pre-kernel execution and testing constraints. |
| Shared inputs | Build rules, scripts, generators, tests, configuration, patches, distinfo, vendored sources, firmware references, assets, documentation and repository metadata all have authoritative owners. Consumers reference shared inputs without copying their authority. |
| System products | World, kernel, base/source packages, installer sets and images compose the selected Components. Their aggregate results cannot silently become independent per-component acceptance. |

No tracked input may disappear because it lacks a Makefile, is imported/vendor
code, or is not selected for the current release. Vendored subprojects and
overlapping build inputs need reviewed ownership. Source identity, license,
content/mode/symlink treatment and external downloads belong to admission; a
directory label or Git object inventory alone is not a Component qualification.

Every compositional unit must produce a versioned pkg artifact with complete
source/build provenance and typed dependency information. Source/build packages
account for units linked into larger artifacts; runtime installation may select
the composed kernel or system packages. Canonical Component registration or an
upstream pkgbase grouping does not by itself satisfy this invariant. It remains
unimplemented for the complete trees.

## Native dependencies and execution

Resolve conditional dependency edges for the exact target, options and source
revision on an appropriate native worker. Text searches over Makefiles cannot
establish a complete graph. Host/bootstrap tools, generated inputs, shared kernel
linking and build cycles need explicit semantics; do not conceal a cycle by
omitting an edge or advertise all source builds as an automatically parallel DAG.

The ports catalog and each selected release closure serve different purposes.
The entire catalog must be visible, but a release builds/admits the exact
required closure rather than implicitly compiling every port. Unsupported,
unselected, unbuilt and untested entries remain visible with truthful states.
The selected package graph also supplies PKG-001's installer/UI planning; its
runtime installation dependencies do not replace the broader build dependency
graph.

Preserve FreeBSD source, target/ABI, dependency and installation semantics.
Make/pkgbase and ports/poudriere are the baseline, but replacing the build
executor with Bazel, Buck2 or another suitable system is authorized. Literate AI
must bind their actions, inputs, output products, source/resolved BOMs, tests,
independent acceptance and packaging through its actual retained lifecycle.
The source-build controller is preparation for that binding, not a substitute
receipt or a second Component protocol. Conversion that retires or regenerates
upstream implementation is not implied by catalog admission.

## Coverage and evidence gates

Maintain separate counts and identities for:

1. Discovered build units/origins and every selected tracked source/support input.
2. Registered canonical Component contracts and complete input ownership.
3. Admitted source/variant inputs and selected current locks/dependency closure.
4. Actual native build and test results, including explicit skips and failures.
5. Independent acceptance, packaged products and exact release admission.

Discovery does not imply registration, and registration does not imply a build
or acceptance pass. Require zero unowned inputs and explicit shared-consumer
relationships for both pinned trees. Addition, deletion, rename or changed source,
options, toolchain, dependency or artifact must invalidate the relevant state.
Coverage must fail closed on incomplete enumeration, ambiguous ownership,
unresolved dependencies or stale bindings.

Large catalogs need bounded deterministic enumeration, useful queries and clear
per-component status; emitting thousands of placeholder specifications is not
evidence that native dependency or behavioral contracts are complete. Reuse the
framework's canonical catalog/Component/Flavor/lock owners instead of claiming
that a custom inventory JSON is equivalent to those contracts.

## Full source input custody checkpoint

The [native traversal checkpoint](../../verification/native-input-traversal-development.json)
checks every tracked path in source fork `d98e6c2da7571295bb3c70236afe637a987370e0`
on FreeBSD: 114,710 members, 9,887 directories and 138 symlinks. The observed
inventory matches tracked paths, executable modes and link-target text, with
manifest identity `sha256:6bcececf720ac6a21c12e5ebf3f04eedbc2c22438bf04c28be1ae38ce770a406`.
All 27 source-level input checks pass without skips, including actual replacement,
mutation, descriptor-limit, alias and snapshot-cleanup cases. The first harness
attempt omitted a shared test fixture and is preserved separately.

This extends the bounded traversal candidate through discovery and copying. A
balanced four-sample native SDK comparison preserves the same 5,141-member
manifest. Median discovery is 4.776245 versus 4.471518 seconds; median capture is
12.602876 versus 10.549773 seconds. A separate native world build was running, so
these are operation-level development observations with shared resource load.
The preceding traversal commit `bfc5bcb5` now passes its complete Python 3.11
regression (1,912 passes, 81 skips) and exact controller wheel qualification;
the wheel embeds that commit and binds distribution identity
`sha256:c1e9b8cb66bf42332e98336354ffe18f4dc61edf0ae67e90b94ea44683e38e2c`.
Native installed lifecycle renewal remains open, as does qualification of the
later private-prefix access repair. Full input custody does not register or admit
the complete Component catalog, resolve
its build graph, qualify every unit's pkg, or demonstrate whole-build acceleration.

## First native source composition proof

The first executable fixture must build an original-source application and its
library dependency during the recorded retained run. Existing retained
export/receipt fixtures copy an already compiled helper; those tests exercise
custody, observers, independent cases, SDK integration and archive consumers.
They do not establish that application source is compiled with an admitted
compiler, resource directory, headers and sysroot. Keep that distinction when
reporting framework acceptance or moving the system onto the operator workstation.

| Boundary | Required evidence before calling the fixture qualified |
| --- | --- |
| Canonical composition | Application, library and shared support inputs resolve through actual authored Component contracts, selected locks and explicit dependency edges. A separate inventory or two opaque tree wrappers cannot replace them. |
| Original-source compilation | Recorded commands compile the retained source and link the actual dependency. Bind compiler/linker binaries, resource files, standard headers, sysroot and libraries to exact SDK/toolchain provenance. Exercise normal native headers and runtime libraries; a freestanding example alone cannot qualify the source/ports build path. |
| Original tests | Tests run the newly built products and derive reports from their observed outcomes. Prewritten success reports or exporting a precompiled executable do not prove compilation of the admitted source. |
| Independent acceptance | Separate verifier authority exercises sealed products and their library closure. A successful compiler exit or successful original test run cannot stand in for this acceptance. |
| Per-unit packages | Actual versioned pkg products bind each selected unit's source/build provenance, both BOMs and typed dependencies. Inspect native package metadata and reopened payloads; a project-wide archive does not establish per-unit package coverage. |
| Incremental invalidation | Measure clean and unchanged runs, then change application source, a dependency implementation, a shared header, build options and the toolchain separately. Observe the actual affected action closure and outputs; stale plans, receipts and package reuse must refuse. |
| Relocation and installation | Retire scratch and original build paths, reopen retained products, then test installation, update and rollback in a disposable VM. Compilation and loading must use declared resources rather than an ambient compiler installation or library search path. |

This fixture is the first integration proof, not a replacement for complete
source/ports catalogs, native conditional dependency resolution or whole-system
acceptance. Grow the same canonical path to real source units and port origins,
including target/options variants, then to the selected ISO closure. Keep
unselected, unsupported and unqualified units visible throughout that expansion.

### Bootstrap compiler closure

A read-only native probe of the initial C compiler seed found Clang 21.1.8,
target `x86_64-unknown-freebsd16.0`, resource directory `/usr/lib/clang/21`,
system headers `/usr/include` and startup/link inputs under `/usr/lib`.
Both `cc` and `ld.lld` also depend on shared LLVM and system libraries. Their
installed bytes are bootstrap inputs with unknown source-build provenance;
they must not be attributed to the selected source fork or represented as
newly built LLVM Components.

The seed inventory includes linker-script references, not only ELF `NEEDED`
entries. On this worker `/usr/lib/libc.so` is a `GROUP` script referencing
`/lib/libc.so.7` and `/usr/lib/libc_nonshared.a`; `/usr/lib/libgcc_s.so` references
`/lib/libgcc_s.so.1` and `/usr/lib/libgcc.a`. The latter archive is a relative
symlink to `libcompiler_rt.a`. Omitting those inputs would leave linking
dependent on ambient host files despite capturing the compiler and headers.

The diagnostic inventory contains 4,114 regular files (237,147,193 bytes),
273 directories and 15 symlinks, with SHA-256
`74e7e4ba1241de799e24296633644b8ac1a67b7196ce8e3cd65d7b2506bb1864`.
It records observed paths, modes, file hashes, link text and linker-script
references; it does not capture file bytes, establish complete compiler
provenance or admit an SDK. The execution fixture must acquire and revalidate
the actual seed bytes, bind its resource/sysroot/linker selection explicitly,
and prove that linker scripts resolve inside the declared sysroot after
relocation. Set bounded input budgets from the actual closure and reject
unexpected growth; do not reuse the smaller helper fixture's limits or weaken
custody to fit them. This initial inventory covers the C proof, not every
compiler language, target or ports toolchain.

The source-fork seed-capture helper now acquires these exact reviewed bytes in
an isolated native workspace. Its ten custody/refusal checks pass on FreeBSD;
the [checkpoint](../../verification/bootstrap-seed-capture.json) binds the
producer, inventory and capture log identities. The helper retains relative
links and verifies linker-script references without executing installed tools.
Framework input capture now also passes, binding 4,129 file/link members and
279 directories to manifest identity
`sha256:5219f23b38a181354c13eb88bffb7cfb9407d5f50ab9e060c2b37de54572e377`.
Original and promoted snapshot trees both reverify. The checkpoint retains an
earlier observation timeout and a timing-record serialization failure separately
from the successful re-verification. SDK admission and relocated compilation
remain open; the installed seed still has unknown source-build provenance.

There is also a distinct typed SDK boundary to complete. The selected toolchain
inventory has 28 internal links, including `ar -> llvm-ar` and header aliases.
The preceding regular-file SDK protocol still refuses aliases. Framework
[issue #93](https://github.com/jordanhubbard/literate-ai/issues/93) owns faithful
alias provenance through source-built SDK capture, producer admission,
materialization and consumer scopes. Preserve existing SDK identities and
refusals unless the new tree capability is explicitly selected. The
[installed public tree microfixture](../../verification/native-sdk-tree-public-cli-development.json)
now passes on exact candidate `23d0b678`, preserving a real hard-link group and
exact symlink text through the live recipe and C consumer. Three original tests,
two acceptance cases and all 28 retained records verify. Its receipt is only
local-runtime; the completed run still reports SDK admission false. Actual
compiler SDK, per-unit package and release admission remain open.

Read-only inspection of the completed source-built pkgbase artifacts now verifies
524 package manifests against their recorded artifact hashes. The candidate
compiler/sysroot package dependency closure is `FreeBSD-clang`,
`FreeBSD-clang-dev`, `FreeBSD-clibs`, `FreeBSD-clibs-dev`,
`FreeBSD-libcompiler_rt-dev` and `FreeBSD-lld`. Archive listings locate the compiler
resource headers, C++ headers and runtime, startup objects and linker within this
closure. These observations identify candidate inputs; they do not establish that
those inputs are sufficient for every compiler language, target or ports build.

The initial six archives are insufficient for a closed compiler runtime. Their
manifests require five SONAMEs with no provider in that set. The
[runtime metadata closure](../../verification/source-compiler-runtime-closure-development.json)
resolves declared package and shared-library dependencies to 18 exact packages
(86,885,560 archive bytes), with one provider per required SONAME. All package
manifests remain bound to the retained source build and artifact hashes. All 18 archives are now collected and reverified against the original build's
artifact inventory and current native bytes. The read clone shuts down normally;
QMP observes both original backing layers read-only. Full package payloads also
contain two unsuitable OS-configuration aliases (`etc/termcap` and
`etc/os-release`), which remain explicit diagnostic refusals. The declared
compiler-resource selection covers headers, libraries, resource files and the
compiler/linker-owned executable roots while excluding OS configuration and
manual pages. It retains `CC` and `cc`, 28 symbolic aliases and nine hard links;
all selected alias targets close within the inventory. Its 3,563 regular files
contain 333,420,987 bytes. No alias is flattened. The [native C diagnostic](../../verification/source-compiler-relocation-development.json)
now revalidates all selected file bytes, symbolic target text and hard-link
inodes, then compiles and runs before and after retiring the initial SDK path.
Compiler/linker/application loader observations stay inside that tree; the linker
trace uses its startup objects and libraries plus a retained owned object. Both
runs produce the expected C result. The guest kernel and ELF interpreter remain
platform dependencies. The uppercase `CC` wrapper and other language/target
entrypoints are not exercised. This is unprivileged diagnostic evidence, not live
source-producer or SDK admission, complete license qualification, per-unit package
provenance or a product receipt.

The actual clang package has 15 hard links for executable aliases. The clang
development package has two library symlinks; the C-library development package
has 22 symlinks and 1,820 hard links. Faithful SDK custody therefore needs both
symbolic alias text and hard-link equivalence with canonical physical ownership.
Original archive target text remains package provenance, distinct from an observed
filesystem hard-link group. Do not silently duplicate those files to bypass this
boundary. The [development record](../../verification/native-sdk-build-development.json)
binds the package and observation identities. No packages were installed. Those initial inspection results do not establish
SDK admission; the subsequent C relocation diagnostic below has separate evidence.

The six exact package archives are also retained as an 80,774,773-byte diagnostic
corpus. Read-only archive inspection finds 4,396 regular file entries, 29 symlinks,
1,839 hard links and 221 explicit directories; the full ancestor closure needs
247 directories. Relative alias targets close within the selected inventory.
This does not capture or admit a filesystem SDK. Three name groups differ only
by case: `CC`/`cc`, their manual pages, and `execvP`/`execvp` manual pages. Faithful
SDK materialization must explicitly require a case-sensitive filesystem and
preserve these names. The portable default's case-fold collision refusal remains
appropriate unless the new target capability is selected; do not remove aliases
or flatten hard-link groups to bypass it.

### Original-source candidate and remaining test boundaries

The pinned source tree supplies a useful initial application/library pair:
`usr.bin/truncate/truncate.c` calls the number parser in
`lib/libutil/expand_number.c` through the original `libutil.h`. The utility's
Makefile declares `LIBADD=util`. A parser-only compositional unit must expose
its precise signed/unsigned public surface and source/header ownership; building
that file alone must not be represented as a complete libutil build. Retain the
original source, Makefiles, manual pages and test definitions in the input closure.

The original parser suite registers four ATF-C cases. The utility suite registers
20 ATF shell cases, including size changes, reference files, rounding, refusal
and deallocation. Its `deallocate` case explicitly requires root. Execute the
complete selected inventory with its actual prerequisites; an unprivileged
worker cannot silently drop that case or bypass ATF's declared user requirement.
Qualify the privileged case in the disposable acceptance environment before
claiming complete original-suite coverage.

The initial native worker already supplies `/usr/libexec/atf-sh`,
`/usr/libexec/atf-check`, `/usr/share/atf/libatf-sh.subr`, ATF headers and private
ATF libraries. Their absence from the default command search path does not mean
the test framework needs installation. Capture exact tool/support/library
inputs and their bootstrap provenance. The retained ATF implementation supports
explicit shell, helper and data-directory selection; bind those selections to
the captured closure and test relocation instead of using ambient absolute paths.

Kyua is also present on the initial native worker and enforces ATF's original
user prerequisites. Preserve its schema-v3 SQLite results rather than inferring
test state from its lossy JUnit export: that exporter omits failure nodes for
expected failures and places skip reasons in diagnostic text. The source-fork
report producer now binds exact program/case inventories, preserves non-passes
and skip reasons, and retains database/inventory/report hashes. All thirteen
[native reporting checks](../../verification/original-test-reporting.json) pass,
including actual Kyua and ATF expected-failure/root-skip runs. Those fixtures
qualify translation, not the original parser/utility tests or source compilation.
Bind the producer/runtime, inventory, raw results and reports to the actual
locked source-unit lifecycle before using them as evidence.

Independent acceptance must observe the newly built utility's actual file
effects, including size and content preservation. Exit/stdout/stderr checks alone
cannot establish those properties. Establish a verifier-owned filesystem oracle
or an equivalent separately admitted verifier through the existing lifecycle;
do not relabel original tests or a zero-exit invocation as independent file-effect
acceptance. This candidate is preparation for the same canonical composition
proof above, not an admitted source unit or a qualified replacement for libutil.

## Execution order and current state

The source fork now declares the exact 24 original case bindings for the existing
Kyua report producer and eleven typed independent utility filesystem cases. The
verifier expectations remain outside build inputs and bind the current three
locks. Actual newly built ATF listings, original test execution and independent
acceptance are still pending. The framework's reviewed build-output command-path
selection passes the full local regression, allowing original-style test commands
to select built exports by name. The current framework wheel is installed in an
isolated development CLI on the HP; native execution qualification is not claimed by the
[current checkpoint](../../verification/original-source-authority.json).

The source fork now contains three actual canonical contracts for the shared
libutil header, parser slice and truncate utility, each with a current `freebsd`
target lock. Its reviewed in-place adoption preserves original source authority
and hierarchy. The [metadata checkpoint](../../verification/original-source-authority.json)
binds the source revision, exact locks and initial authority evidence. These
locks now select explicit FreeBSD and pinned native-pkg Flavors. They still
qualify no compiler/runtime or executable Standard profile. Registered/locked units are
three; admitted units and qualified per-unit packages remain zero. This does
not establish complete source or ports coverage or native source compilation.

The owned source integration branch is `daemonarchy`, separate from the
upstream-tracking `main`; its source-development PR remains a draft. The
operator's `/usr/src` checkout now uses source revision
`978fed917ba2b391c3eace661c21a7a65549cb23`; isolated `litai-dev` validates
its current Standard binding and three locks. The receipt is missing because no
retained native lifecycle has run. The stable 1.1.1 framework remains unchanged.
The next executable step is the actual Standard/native profile, complete
selected input ownership and compiler/test-runtime admission, followed by
original compilation, original suites, independent acceptance and pkg products.

SRC-001 has supplied a pinned native build controller. The first GENERIC build
completed after a retained set-phase failure and exact-plan resume. Byte and
MANIFEST audits pass; an archive-fidelity defect was found and fixed in an
isolated source-archive build. All 21 current controller checks pass on FreeBSD;
macOS skips the native archive check. These results do not establish native
Component execution or boot acceptance. The current eight Daemonarchy
contracts still describe product integration, not full source/ports membership.
No complete base/ports Component catalog, current per-unit native receipt or
full-tree coverage pass is claimed.

The framework ownership foundation at `3badbdb7` binds exact canonical Component
authoring identities to complete retained file/directory coverage and revalidates
the actual catalog during planning. Its full local Python gate passes 1,684 tests
with 36 skips. It preserves public execution refusal; the configured framework
lifecycle receipt remains stale. No full native catalog is registered by this
foundation. Framework revision `545c4ae6` additionally preserves explicit internal
POSIX source symlinks. Its actual source corpus validates all 114,644 files and
138 link targets; the full local framework suite passes 1,696 tests with 37 skips.
[Input-custody evidence](../../verification/native-source-input-custody.json)
keeps complete source snapshots, native execution and per-unit packages unqualified.


Next action: establish complete pinned-tree coverage and reviewed build-unit
boundaries, then connect a real multi-component native fixture to the canonical
catalog, variant locks and retained lifecycle. Grow that path to complete tree
registration and the exact release closure without weakening ADOPT-002 or
RELEASE-001. Framework catalog/lifecycle gaps are tracked in [issue #74](https://github.com/jordanhubbard/literate-ai/issues/74), building on retained lifecycle issue #22.
