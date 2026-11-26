# 1.6 release recovery, November 25

The release remains in development. This checkpoint retains the interrupted
native work and separates recovered results from new release qualification.
The current accepted bounded ARM development set is **125 packages**; counts
below record successive qualification checkpoints. Libthai's inherited header gaps
remain explicit.

## ARM source producer

The selected source is `759e93f1bbc79103eda36077e7c28d17317f15c8`, with retained
plan `6ff1e029b20b618659a2953d8114fef2cddf3943eba5067e7492e7ee9a35b45e`.
Its original four-job, filemon-traced producer completed all five phases:
world, kernel, packages, release objects and installer sets. The supported
resume finished on November 25 at 19:07 UTC. The original byte-and-trace
verifier passed for all 531 artifact records, and the complete source, plan
and selected worker postguards passed. The failed first world attempt and
the successful phase logs remain retained.

All eight installer sets, their MANIFEST and three producer records were
exported to separate local scratch storage. All 12 exported files match their
native recorded sizes and SHA-256 hashes. The base set is
`382265eec4ae4f1511f405783eeabb3de78b72da6936893c976b724ed23b50d9`;
the kernel set is
`ad432d7189ed4cf706fb3f78e719a65a1851a1347350d01d92523e477f101226`.
Independent semantic review subsequently passed for all 531 artifacts and all
six phase logs, retaining the failed first attempt. Both repository catalogs
match all 516 package manifests; their 1,063 dependency edges close, with no
unprovided shared libraries. The file index matches all 157,087 manifest paths.
Both source packages and the source set match all 115,712 selected Git entries,
including modes and links. An actual isolated package installation verified all
750 kernel/module nodes against the kernel set, including effective ownership
and aliases. Raw package and set numeric owners differ; their actual installed
payloads match.

The completed source-products archive contains 573 non-directory members,
including all original artifacts and the retained controls, inputs and logs.
Its SHA-256 is
`23236e2ac01a653f3be141c62c5ac15948d67a08b603d3eca6b9835414441244`.
All member bodies and links and the complete gzip stream were independently
verified on both evidence hosts; native capture also checked modes and owners.

A private UEFI QA image was assembled from the matched base and kernel sets
on the other scratch-backed native worker, preserving its complete installed
105-package SDK inventory. The existing 120 GiB start and 100 GiB completion
thresholds remained enforced. The image SHA-256 is
`b68d9bc68e6ae20a4558ef0500c0d510085091431499d287250cef33ee4303cb`;
compressed/raw identities and both GPT checksums passed before launch.

A fresh ARM VM then booted that image through the EFI loader to multiuser mode
and accepted authenticated SSH. Its kernel, loader, shell, libc and system-header
hashes match the image. The complete running kernel version also matches the
selected kernel's embedded bytes. UID 65534 shell/file/arithmetic/date controls
passed, followed by actual native C and C++ compile/link/run checks covering
threads, monotonic time, allocation, filesystem access and exceptions. These
are bounded base-system checks, not original compiler or base-system suites.
The private disk contains QA credentials and is not a publishable product image.
Matched SDK, desktop, product media, physical-target and release acceptance
remain open.

The completed independent-review/kernel-consumer evidence has a separate
793-member archive, SHA-256
`f57dea296d0dd7b361242f440e9b0478febd36c7b47a3a84769ea6ccb95067d4`.
The image-assembly guards, boot/runtime results, native compiler smoke and
retained observer failures have a 58-node proof archive, SHA-256
`f2132107b0858496a50d992abcf3b00f10f244622fd0faa7d14f2b829bf821cd`.
Both archives were independently verified on both evidence hosts. The boot
proof includes neither private SSH keys nor the private disk image.

The existing allocated ARM worker was recovered with fresh writable overlays
on a separate local scratch disk. The crash disks remain unchanged backing
files. The host root volume still has approximately 46.5 GiB free, below the
recorded 64 GiB build reserve; the separate scratch volume has approximately
188 GiB available after the recovered work, evidence copies and private boot
image. Guards for resumed
writes must measure that writable volume.
Guest free space alone does not reserve host backing capacity.
A later storage recheck still finds the host root below its 64 GiB reserve,
with approximately 46 GiB available, while local scratch has approximately
187 GiB and the package worker has 132 GiB. The shared NAS still reports a
degraded pool, one faulted member, another degraded member and two data errors.
The current recovery continues on the separate local scratch and allocated
worker storage.

The original producer requires at least 100 GiB free when filemon tracing is
enabled. Its guest had approximately 97.8 GiB free. A 16 GiB expansion of the
fresh overlay was completed without lowering that requirement. The crash-left
UFS filesystem passed an offline check covering 2,938,148 files before growth.
The mounted build filesystem had approximately 112 GiB available after growth.
Original worker base-file hashes match their retained values, and filemon was restored
for the unprivileged producer. The supported resume is under a host monitor
that measures the scratch-backed writable volume, retaining its 120 GiB start,
64 GiB stop and 8 GiB available-memory thresholds. The monitor and native
wrapper both completed successfully.
After the independent evidence copies passed, the source-builder VM was shut
down cleanly with no active builder processes. Its disks and original outputs
remain retained; the package worker and fresh boot tester remain available.

## Desktop dependency closure

The clean native ARM64 `xmlcharent` 0.3_3 to 0.3_4 upgrade passed before the
crash. Recovery checked the installed SDK against its saved post-upgrade
inventory. The final 538-node upgrade capsule was then independently verified
on both evidence hosts. Its compressed archive SHA-256 is
`6a3f2eed16e04ffbb24c9520e387dfb6a011636a5f1d3dce376ef63bafa912a5`.

The allocated desktop/package worker was then stopped cleanly and restarted
with fresh writable overlays on the separate scratch volume too. Its retained
104-package SDK was remounted and the installed Xmlcharent 0.3_4 registration
confirmed. Original disks remain backing files, without further build writes.

The normal upgrade had no hook diagnostics, preserved all four catalog files
and the other 103 package prefixes, and passed 136 entity commands covering
975 definitions plus 20 Simplified DocBook consumer commands. All 104 installed
development packages are accepted at that bounded integration checkpoint.
This is not complete original-upstream-suite or canonical lifecycle acceptance.

Continue ISO8879, SGML, the DocBook metaport and XSL closure,
then original-default D-Bus with MANPAGES/X11 and the full original GLib tests.
The shared catalog keyword fix has 21 known port consumers; selected-package
rebuild and upgrade-version coverage remains open.

[Ports PR #117](https://github.com/jordanhubbard/daemonarchy-ports/pull/117)
now bumps the other 20 consumers' package revisions so existing installations
can receive the regenerated fixed hooks. The version-only source selection is
`74ee006accba1fd1b9da68ac6e0579cf88527b6d`. Native verification passed all
184,371 source entries. All 42 original-make queries and 21 package-version
comparisons passed: the other 20 consumers are strictly newer, and Xmlcharent
remains 0.3_4. Kernel, fstab and main installed package-database bytes were
unchanged by those metadata queries.

Fresh Simplified DocBook 1.1_3,2 passed all eight original construction targets,
15 sealed payload checks and 20 DTD consumer commands. Its normal local-only
installation passed with empty stderr, clean
hooks, both master catalogs and all 104 inherited prefixes preserved. The two
catalog indexes changed exactly as predicted; all 20 default-global consumer
commands matched the sealed run. The bounded development SDK then reached
105 packages. The source/private/failure/observer archive has 625 nodes, and the
normal-installation archive has 80; both were independently verified on both
evidence hosts. Original upstream self-suite, canonical and release acceptance
remain separate.

The earlier direct hook controls executed percent-encoded manifest text;
their claim to execute the exact pkg runtime bodies is withdrawn. The pinned
pkg implementation decodes manifest scripts before execution. Fresh controls
now apply that decoding: all 13 Xmlcharent, 18 Simplified DocBook and 17
ISO8879 commands pass. An independently read, byte-verified copy of the installed
package database confirms that all four Xmlcharent/Simplified DocBook script
bodies exactly match the decoded manifests. The actual normal installations
already passed through pkg's decoder and remain separate evidence.

The corrected controls, original encoded-text controls, ISO8879 source/private
checks, observer failures and original OpenSP build/suite evidence are retained
in a 5,370-node archive, SHA-256
`f142f4eafb4ec3eafede192015103dd5b1bffb6d6ea20be3ea238784f9a1868d`.
All bodies, types, modes, owners, flags, nanosecond timestamps and links were
verified on both evidence hosts. The installed 105-package SDK stayed unchanged
during these controls. The SGML parser accepted the unfinished-quote negative
fixture without error; its failed observer result is retained. The corrected
SGML hook error control uses a real catalog I/O failure. XML malformed-catalog
controls continue to pass.

The initial sealed/hook attempts stopped before installation because only the
SQLite shared-memory file's timestamp differed from the older inventory. Its
32 KiB body and every other node matched. A real read-only `pkg query` against
an isolated database copy reproduced only that timestamp change, preserving
all database bodies and the actual SDK. The failed attempts and both inventories
are retained. Fresh attempts used the complete observed inventory and passed
the same exact metadata guards; no timestamps were restored or fields ignored.

OpenSP 1.5.2_4 then passed all eight original construction targets with DOCS
and NLS enabled. Its package SHA-256 is
`1a53c59be13df5825eb9c6c004c813974864f5329578d4bab5f4ce8e8a0aad23`.
The complete original upstream suite ran all 23 selected cases: 17 passed;
`catalog-2` and `af-7` through `af-11` failed. No cases were removed or
reclassified. The failures and isolated repair experiments are retained;
no repair is qualified yet. OpenSP remains uninstalled. Its build and test
runs preserved the full 105-package SDK inventory.

An isolated production-code repair prototype passes 20 of the same 23 original
cases, including `catalog-2`, `af-10` and `af-11`; no test bodies, expected
outputs or suite membership changed. The remaining three failures include
expected-output issues and an unresolved content-mapping semantic discrepancy.
The prototype is not installed or accepted as a qualified parser repair.

ISO8879 1986_4 also passed all eight original construction targets from the same
selected ports tree. Its package SHA-256 is
`b5287bac8795a9eede78ee8c9fe6257841a67918c86394aaab7fd4d03506a73e`.
The installed prefix, logical registry and selected source/base guards passed.
All 24 sealed payloads and 228 private SGML/catalog commands pass, covering
978 definitions through 38 public identifiers in 19 resource files. These
include invalid-document and missing-catalog rejection, changed-resource
values and recovery. Its previous 1986_3 package was rebuilt from retained
source to supply actual old script bodies for the 17 decoded hook controls.
Its normal local-only installation then passed with clean hooks and empty
stderr. All 24 payloads match; only the predicted SGML catalog index changed,
and all 105 inherited package prefixes and the XML catalogs were preserved.
All 114 default-global resource commands matched the private results, bringing
the bounded development SDK to 106 packages. The 246-node normal-installation
archive was verified on both evidence hosts, SHA-256
`ab69a186df6a3910edbf7ff6827a622e8962e216f6e7422e6e18b262b56e5689`.

Its original port exposes no selected upstream test bridge. The SGML resource
checks use an uninstalled original OpenSP test tool with an explicitly bound
private library directory. Default-global catalog discovery uses no catalog
environment override. These checks do not qualify a normally installed parser
or close its six suite failures. The next original DocBook SGML producer retains
all nine selected DTD versions and the original dependencies.

## Catalog error propagation follow-up

The corrected runtime-script checks exposed another shared-keyword defect:
with the first SGML catalog unreadable, its add or remove failed, but the
following XML catalog operation succeeded and the whole generated script
returned success. The remove case also changed the later XML catalog despite
the earlier failure. Native reproductions and a six-command copied-body repair
experiment are retained in a 1,190-node archive, verified on both evidence
hosts, SHA-256
`50b6fa2c27a4e9dd9dad316433f3f8bd89a89b1411ff4ac3ab5619fe9d7a8ae4`.
These passing reproductions establish the defect, not product acceptance.

Ports candidate `1d0dc88cb0d7e2087bd7acaefb2f030e1036b3de` stops on the
first failed add or remove and increments all 21 keyword consumers. Native
verification checked all 184,371 source members. All 42 original make queries
and 21 native version comparisons confirm strictly newer consumer versions.
Xmlcharent 0.3_5 passed eight original construction targets, its actual custom
port test target with all 21 added regressions, 19 decoded generated-script
controls, and 136 isolated consumer commands covering all 975 independent
entity values. The new controls reproduce the installed 0.3_4 error masking
and verify that 0.3_5 returns failure while preserving the later XML catalog.
The added port regressions are separate from an original upstream self-suite.

The 1,482-node source, build, test and isolated-consumer archive was verified
on both evidence hosts, SHA-256
`ae1ac3805284821562ef6180725bfdbd827e85305f4c7c89072deb4643ef8fdd`.
The normal 0.3_4 to 0.3_5 local-only upgrade then passed with empty stderr
and no hook failures. All 25 payloads match, all four global catalog files
retain their bytes and timestamps, and the other 105 package prefixes are
preserved. All 136 default-global entity commands, 20 Simplified DocBook
commands and 21 added port regressions pass on the installed payload. The
bounded SDK remains at 106 packages. The remaining selected consumer rebuilds
require their own qualification; this count does not establish admission of
every revised consumer. The 542-node normal-upgrade archive was verified on
both evidence hosts, SHA-256
`324ecf3da5120b53df21d9e9cfe92b0b4de41ea24f2d691f582f0d6e4626e83d`.
An initial preflight observer used a retired result-field name and stopped
before package mutation; that failed result is retained alongside the passing
fresh attempt.

Simplified DocBook 1.1_4,2 was then rebuilt with the same keyword and its
normal Xmlcharent 0.3_5 dependency. All eight original construction targets,
15 isolated payloads, 20 DTD commands and 24 decoded generated-hook controls
pass. The normal 1.1_3,2 to 1.1_4,2 upgrade has empty stderr and no hook
failures; all four catalogs retain bytes and timestamps, and the other 105
prefixes remain unchanged. Fresh 20 default-global DTD commands and 136
Xmlcharent dependency commands pass. The SDK count stays at 106. The port
exposes no selected upstream self-suite bridge; these are independent consumer
and hook checks. The 649-node source/private and 454-node normal archives were
fully verified on both evidence hosts, with respective SHA-256 values
`bcba754b5c8ae4f430bef1ea93dea40d30d8606ce1c764af76670af0b462a4cd`
and `41abf49c1db80bb60f16040ecaab37f5e0000a7cc05a6b8eaf04416d97f43948`.

ISO8879 1986_5 also passed eight construction targets, 24 isolated payload
checks, 228 resource commands and 21 decoded generated-hook controls. Its
normal 1986_4 to 1986_5 upgrade passed with empty stderr and no hook errors.
All four catalog files retain bytes and timestamps, the other 105 package
prefixes are preserved, and all 114 fresh default-global resource commands
match the private results. The SDK count remains 106. The 1,869-node
source/private and 258-node normal archives were verified on both evidence
hosts, with respective SHA-256 values
`872980a11c880bbf9b85f92d3f2fc30c9c538664abcbaa359488680f9d7fe85a`
and `a4c41741ab028133d8e19178123947e3aa2c40f10828094e9f3c75af4eded2c6`.
A pre-install verifier-field error remains retained with the fresh passing
attempt. The external OpenSP test tool still uses its explicitly bound private
libraries, and its six original suite failures remain open.

Fresh DocBook SGML 4.5_3 and DocBook XML 5.0_5 packages then passed all eight
original construction targets with the updated normal dependencies. Their
package SHA-256 values are, respectively,
`974d769e8db5ffefe66e6b2e153ce1eeed880949639f799ea5dc4771ee707514`
and `1325b1bcdae273f3a226728e2ce88a7597b8384317c74184a489f050d716c2a5`.
SGML remains uninstalled; its isolated consumers, generated hooks and normal
integration still require qualification. XML qualification follows.

DocBook XML 5.0_5 subsequently passed all 195 isolated payload checks, 42
DTD/schema/catalog/conversion commands and 24 decoded generated-hook controls.
The controls parse and assert both script orders: XML precedes SGML. The old
5.0_3 script masks a first XML add/remove error when the later SGML operation
succeeds; the new script returns failure and preserves the SGML catalog. Two
observers that assumed another operation order remain failed and retained.
The old 5.0_3 bodies have no percent-decoding differences, so their seven
historical direct controls remain runtime-byte-exact.

Its normal 5.0_3 to 5.0_5 package transaction and all 42 consumer commands
succeeded, but the wrapper then raised an error while reading an optional
report flag absent from the older consumer. That original wrapper remains
failed. A separate read-only completion binds its result and transaction,
validates all 42 retained command outputs and the actual loader/catalog guards,
and runs the remaining 136 Xmlcharent dependency commands. No package
transaction or completed consumer commands were repeated. All 195 payloads,
four catalog bodies and timestamps, and the other 105 prefixes verify; the
complete SDK prefix and raw database stay unchanged through completion. The
bounded SDK remains at 106 packages. Four original aliases for two absent
schema targets remain explicitly unqualified.

The 1,938-node source/private and 515-node original-normal/completion archives
were fully verified on both evidence hosts, with respective SHA-256 values
`701deb251972d52be8f4605d8c2f850fa652fcd00997126b3f792d9160d395a2`
and `32cc97e62d6f38b900af533e017360db8c4700df18bfed675019b37228e1e2b1`.
These independent consumers and transaction checks do not close original
upstream self-suite, canonical lifecycle, desktop or release acceptance.

### Legacy SGML mode repair and the 107-package checkpoint

Actual SGML consumers exposed a further failure in DocBook 4.3 after the six
older DTD versions passed. The shared 4.3/4.4 modules contain XML-only
attributes and HTML table declarations that fail in SGML mode. Both original
providers now apply the same narrowly scoped module repair: SGML attribute
guards and tag-minimization declarations, with CDATA table rules only in SGML
mode. XML 4.3 retains its original rules enumeration and rejects an invalid
value. All original distributions, dependencies and options remain selected.

Ports revision `6defff971350efcf84889a03120ab5462ece1508` was independently
reconstructed and checked across all 184,377 native source members. Fresh
DocBook SGML 4.5_4 and XML 5.0_6 packages each passed eight original construction
targets. All six patched module bodies match the experimentally tested repair;
the original patch targets report no fuzz or offsets. The package SHA-256
values are, respectively,
`ef144a868c625279a2074bc2a4e033fa4b70018919f2864c9f66f08cac6be8e4`
and `e22952c7ae93156b3400ea5818ec5cd7b9ad9001ca7391e9bef252b0499c58ff`.

The actual sealed pair passed all 141 SGML and 195 XML payload checks,
63 SGML commands across all nine DTD versions and 42 XML commands across six
DTDs and three shipped schemas. A further 23 commands cover reversed catalog
order, HTML and CALS tables, XML attribute/rules rejection, original failures
and patched recovery. The decoded generated hooks are byte-identical to the
previously tested 17-control SGML and 24-control XML sets. Those hook controls
were bound by exact bytes and receipt digests; they were not replayed.

The normal XML 5.0_5 to 5.0_6 transaction passed with empty stderr and no hook
errors. All 195 payloads, four catalog bodies and timestamps, and the other
105 package prefixes verify. Fresh consumers passed 42 DTD/schema/catalog/
conversion commands, 136 Xmlcharent dependency commands and seven XML table
and strictness commands. The count stayed at 106.

The subsequent normal SGML 4.5_4 installation passed its original local-only
solver, dependencies and hooks with empty stderr. All 141 payloads verify.
Only the predicted SGML catalog index changed; the other three catalogs and
all 106 inherited prefixes outside that index are preserved. Fresh default
global consumers passed 36 commands across nine DTD versions and three HTML/
CALS table commands. The bounded development set is now **107 packages**.
The frozen SDK, base/kernel and mount guards passed throughout.

Both evidence hosts independently verified every node in four retained
capsules: 5,362 nodes for original failures and derived prototypes
(`d89598e0bc1d6078cc9995b666fed97f15d96c251518928811493dfd7dc42413`),
3,450 for the actual source and sealed pair
(`b3ce039396124736bc163d0469e02361ed0bd7cffa1c30361f312e99f66b6840`),
532 for normal XML integration
(`b2516cf1d4ec909645df99b9535b2dd8ee48530774f8c3b22ba384b5b294832d`),
and 96 for normal SGML integration
(`89f58f78da3fd46c036e116d7855af94c99adaddaa80b5471dbb61612a1ecbc3`).
Earlier fixture and observer errors remain preserved with the real failures;
derived prototypes are distinguished from actual package acceptance.

Positive consumers use no catalog environment override. XML uses the default
loader; SGML uses the uninstalled original OpenSP tool with explicitly bound
private libraries. Its six original suite failures remain open. The four XML
catalog aliases for two absent XInclude XSD files remain unqualified; ordinary
XSD files do not substitute for those schemas. No upstream self-suite,
canonical lifecycle, desktop or release acceptance follows from these checks.

The DocBook 1.5 metaport then passed all eight original construction targets,
all four license/SBOM payload checks and exact bindings to its three normally
qualified providers. Its initialized empty-registry negative control confirms
that the original solver rejects the first missing provider. Two earlier
harness failures remain retained. Isolated extraction explicitly skips
dependency delivery; the separate normal local-only transaction and original
installed payload/dependency checks pass with the real providers. All 107
inherited prefixes and four global catalog files remain unchanged. Frozen
SDK, base and mounts verify. The bounded development set is now **108 packages**.

The 486-node source/private capsule and 22-node normal capsule were fully
verified on both evidence hosts, with respective archive SHA-256 values
`82834030b5d934c2ff982ce0822c9180fdd68416e30d82b3fef768bac6f7e6b2`
and `68d6c944f7977d90593a7c70434ae17bcf084c45cf2200ed110fe964b128ad97`.
This metaport aggregates dependency metadata; it has no upstream distribution
or self-suite. Fresh DocBook XSL 1.79.1_3,1 construction also passes all eight
original targets with all 14 feature options and DOCS enabled. Its 20,690,058-byte
package has SHA-256
`0bae6553ac8373189fdb42bcd0d59337fc7af9238699c5e03ebe7db6c606db94`.
Its subsequent consumer, hook, custody and normal integration results are
recorded below. The initial observer's wrong epoch expectation is retained; no port
metadata or options were weakened. The TESTS module option is not an original
self-suite result. Continue XSL acceptance, D-Bus MANPAGES/X11 closure, full
original GLib suite and desktop qualification.

### Original XSL consumers and the 109-package checkpoint

The actual XSL package now passes all 3,085 isolated payload checks. Its
unchanged upstream smoke-test Makefile discovers and completes 45 transforms
using both original fixtures. A small argument adapter maps its XML-first
invocation to the native `xsltproc` CLI; every child exit and output is
journaled separately so shell loops cannot hide a failed transform. All 45
pass privately and again from the normal installed paths. These upstream
smokes check successful execution; independent output checks are separate.

Nineteen private commands check offline DTDs, HTML/XHTML/FO content and
structure, profiling, generated man pages, all four original catalog rewrite
rules and both advertised aliases. Empty, shadow and recovery controls bind
the results to the selected resources. Seventeen actual pkg-decoded hook
controls verify registration, idempotence, entry-type collisions, removal,
reinstallation and add/remove I/O failures. All 15 default options remain on.

The normal local-only package transaction, dependency and installed payload
checks pass with empty stderr. Only the predicted XML catalog index changes;
the other three catalog files and all 108 inherited prefixes outside that
index are preserved. Fresh installed consumers pass all 45 upstream smokes
and the first 17 semantic/API checks without positive loader/catalog overrides.

The next counterfactual exposes an incomplete observer: its private shadow
catalog overrides URI lookup only, while the now-installed global catalog also
supplies system lookup. The original semantic and outer wrappers remain
failed. A read-only completion binds those failures, independently revalidates
all 17 retained outputs, demonstrates the URI/system distinction with two
native API commands, then passes a dual-kind shadow and default-global
recovery. It also queries the actual 109-package registry. The successful
transaction, 45 smokes and 17 prior checks are not replayed.

The complete SDK prefix/raw database stays unchanged through that completion
following the explicitly recorded, known shared-memory timestamp transition
from the read-only query. All payload, inherited-prefix, catalog, frozen SDK,
base and mount guards pass. The bounded development set is now **109 packages**.

Source/build, private and normal/completion capsules contain 7,179, 6,764 and
297 nodes respectively, all independently verified on both evidence hosts.
Their archive SHA-256 values are
`53a52ca78380941cd6d54bdbb68bbdf20017a6e44b9b30006cf5ebf135840f08`,
`02cf0c65237809720c1bd03972ddd7299fa40cbc15852146dfc979e2b9ee095c`
and `82a46659c2e64c19a2cb98124727ff089d81a8585da399427435ef9df935e285`.
Original epoch, generated-driver quoting, declared HTML charset and deprecated
API observer failures remain retained. The final native API consumer uses
nondeprecated interfaces while preserving compiler warning checks.

Original default D-Bus 1.16.4_1,1 subsequently passed all eight construction
targets with EXAMPLES, MANPAGES and X11 enabled. Its original `make test`
target passed all six discovered programs. An independent audit binds every
native command to the generated Meson inventory and accounts for all 43 TAP
events: 30 pass and 13 original skips, with no failures. Skip reasons remain
retained. The original disabled modular-test variant is not qualified.

The first deep-directory build passed construction but its server test
exceeded the Unix socket name limit. A fresh build uses the original port's
`WRKDIR` setting beneath a short, separately owned parent; no source, test,
expected output or options changed. The initial short-directory extraction
and optional-stderr audit observer failures also remain retained. The fresh
303,628-byte package has SHA-256
`ee2bbb9870eeba634b2c75e63ee345f8a76e969d6c930971860beaf2916ff8c8`.
Its 3,887-node source/build/failure/test capsule is fully verified on the
native ARM worker and independent Intel tester, with archive SHA-256
`a8ebc27e06fdcba68dc6694da3a2e146d5e0a547c73534cf66274f6b511351d9`.
The original evidence destination refused this copy below the 64 GiB reserve;
the same verifier and reserve guard were kept for the alternate healthy
host. No software installation or aggregate build was needed on that tester.
D-Bus subsequently passed sealed payload, lifecycle, private/default runtime
and normal integration checks. The bounded development set is now **110 packages**.

The actual package contains 59 payloads and seven explicit directories.
Six real `pkg -c` transactions exercise fresh installation, force reinstall,
modified sample preservation, removal of unchanged samples, uninstall and
reinstallation with original shell/Lua hooks enabled. Real locked fixture
accounts acquire messagebus UID/GID 556, which original uninstall hooks retain.
The actual private ldconfig hook materializes its cache. Dependency delivery
uses verified SDK library copies and `-M`; missing dependency-record warnings
remain retained. The actual normal solver separately passes with declared
dependencies, original account/sample/loader hooks and empty stderr.

Both private and normally installed default-loader/configuration consumers
pass 12 independent C IPC checks, 13 service-activation checks, `dbus-send`,
child exit-status propagation, unprivileged helper execution denial, repeated
UUID generation and CRC/content checks for nine gzip manpages. Runtime actors
use UID/GID 65534. The normal per-user service fixture lives outside the SDK.
No manual library or D-Bus address override is used. All new payloads,
existing package prefixes, frozen SDK, base files, account records, loader
cache and mounts pass their applicable preservation checks.

The successful normal installation initially hit an observer that incorrectly
required unique soname keys. A real cache refresh includes existing named
bootstrap libraries after the preferred full GLib entries. Read-only completion
verifies ordered bindings and byte-identical preexisting bootstrap candidates;
the default `gdbus` loader still selects full GLib. A second observer failure
revealed that read-only package queries can unlink and recreate SQLite's empty
WAL/SHM pair. Per-command snapshots retain these explicit sidecar transitions
and directory mtimes, with the main database exactly preserved. Fresh consumer
guards then preserve the entire SDK, including the raw database and sidecars.
Both failed receipts remain retained; installation and hooks were not replayed.

The 403-node private and 90-node normal/failure/completion capsules are fully
verified on the native ARM worker and independent Intel tester. Their archive
SHA-256 values are
`e6b53d6a579114d807f59438d87973eaea1f7b28c75e34daae86cecf6fc37b76`
and `8a5bec2a3d76e701f02a02b48a271ac6fbe1f57f4f5f3a42df05cc9cbabde4b0`.
No extra archive was placed on the constrained Linux root or original second
host. The system bus was not started; broader D-Bus modular coverage remains
open.

All original GLib test tools are now installed. Its earlier configuration
listed 387 tests but found neither `dbus-1` nor `dbus-daemon`. A fresh original
default build has therefore started in a short, separately owned work directory,
with DOCS/MANPAGES/NLS/TEST preserved and the original test target selected.
Fresh configuration discovers 420 programs, including 33 additional D-Bus
programs and every previously discovered test. All eight construction targets
pass. The first original `make test` stops before upstream execution because
its original pre-test overwrites root-owned `/var/lib/dbus/machine-id`; the
unprivileged actor receives permission denied. All products and the failure
remain retained, with SDK, registry, base and mount guards passing.

The second build completed the original selected target: **407 passed, nine
skipped and two failed**, in pollability and authentication. The independent
audit accounts for all 418 commands and 6,987 numbered TAP events. The two
original upstream `failing` variants remain excluded and unqualified. Root
runs the required UUID pre-test; the exact original backend, environment and
target then execute as UID/GID 65534 through the supported identity hook.

[Ports review 118](https://github.com/jordanhubbard/daemonarchy-ports/pull/118)
backports pinned upstream test corrections. The pollability test checks the
running FreeBSD version and positively asserts the supported capability. The
authentication test accepts orderly EOF while preserving its other rejection
assertions. Both pass in the full rerun, which reports **404 passed, nine
skipped and five failed**. Independent base-C probes reproduce empty descriptor
paths at the worker's saturated namecache. A bounded A/B/A experiment yields
correct paths only with added capacity. A proposed null-device kqueue error
hypothesis was disproved; no library change was made.

The A/B/A observer failed because resizing back restored writable limits and
capacity but rebuilt the read-only hash geometry. That failure remains retained.
A separate read-only completion verifies the restored writable settings,
explicitly records the current hash geometry and passes fresh preservation
guards. Subsequent runs restore this recorded current geometry as well.

The complete 65,018-node original source/build/failure/probe/resource capsule is
fully verified on native ARM and the independent Intel tester. Its
285,816,034-byte archive has SHA-256
`281982442c0b4c2d6c1ea0fe8b950a35815c358db5b1e8c090293f8416856174`.
All original live trees remain retained. This capsule contains the first three
builds; later capacity reruns are separate evidence.

With measured namecache headroom, all eight original construction targets pass
and the full selected suite reports **408 passed, nine skipped and one failed**.
All five prior cache-related failures pass. The independent audit accounts for
6,988 numbered TAP events and isolates the remaining filename-completion order
assumption. The minimum observed cache headroom is 1,275,601 entries. All
original worker settings, capacity and current runtime hash geometry are
restored and independently checked by a process-exit watchdog. The uninstalled
11,263,642-byte package has SHA-256
`732c10ac4b45c6286d2210a6861311f5205534caa241d6f60be7191f751aa230`.

The review now adds the test portion of upstream commit
`70355ac696600d7cd99dcb7e1cf110b52bd158b9`, which documents unspecified completion
order. Sorting the compared arrays preserves expected membership, multiplicity,
directory-only behavior and suffix assertions. All three changes affect test
files only: no library source, options, dependencies, distinfo, added skips or
exclusions, or package revision change. Zero-fuzz patch checks match the pinned
upstream test bodies.

Fresh complete source `fadd8b8b2e4bdd2a4a9c1af6deb6472bec9e4231` has 184,381 Git
members. Every native source body and mode verifies. All eight original
construction targets now pass, and all three actual patched test bodies match
the pinned upstream bodies. The full original selected default target passes:
**409 passed, nine original skips, zero failures**. The independent audit matches
all 418 native commands to the 420-program discovery list and accounts for
6,989 numbered TAP events. The two original upstream failing variants and all
skipped/optional coverage remain unqualified.

Minimum measured namecache headroom is 1,640,459 entries. All original worker
settings, capacity and current runtime hash geometry are restored and verified
by the independent watchdog. The strict whole SDK110 prefix/raw database, frozen
SDK, base/kernel/shells, accounts/loader cache, mounts and selected-source guards
pass; known read-only package-query sidecar transitions remain explicit. This
qualifies the selected native ARM target under the recorded worker profile; it
does not qualify production kernel defaults or the complete release.

The new 11,262,812-byte package has SHA-256
`dc3256e613e4c6c957d0dbd404a66f45393edfa64cabb643fb9f40ae8b121925`.
All 41 private API/tool/typelib/documentation/manpage/translation commands pass.
All 8,130 payloads and two explicit directories verify. Six real isolated
`pkg -c` transactions execute the original ldconfig install/deinstall hooks;
cache bindings appear, disappear and return through forced reinstall, removal
and reinstallation. Locked fixture accounts, SDK110, frozen SDK, base, host
accounts/cache and selected sources verify. All temporary mounts are removed.
Separate private `pkg -r` extraction disables hooks; the actual chroot
transactions provide these hook observations.

The complete latest 68,906-node source/build/failure/private/lifecycle capsule
is independently verified on native ARM and Intel. Its 279,110,721-byte archive
has SHA-256
`a2912beb7bc836fca117a8faee2178e38c435703a533493a8ebb26f7dc075b07`.
It includes both the failed adequate-capacity run and complete passing corrected
run; the earlier 65,018-node capsule remains independently retained.

The actual new package now replaces the old same-version GLib with original
local-only dependency checks and hooks enabled. All 8,130 installed payloads,
two directories and other 109 package prefixes verify. All 110 registry rows
remain unchanged. The refreshed loader cache preserves every candidate and
per-soname priority, including the required named bootstraps. All 41 consumers
pass with the normal loader and no `LD_LIBRARY_PATH` override.

A separate read-only check binds that successful transaction and its complete
post-install SDK seal, records the explicit read-only package-query sidecar
transition, then preserves a fresh full SDK110 prefix/raw database through all
41 default consumers. Frozen SDK17, base, host accounts, actual normal loader
cache, mounts and all 263 selected source inputs also verify. The bounded
accepted development set remains **110 packages**. The final 233-node normal/completion
capsule is independently verified on native ARM and Intel. Its 22,704,634-byte
archive has SHA-256
`1144fa1ddd37cf13db5740f1eb1f4f082d9ace5881be492b0cb9fd961805b93e`.
A transient SSH banner timeout interrupted retention after metadata staging;
its failure is retained and the resumed copy verifies the original archive,
without replaying native installation or hooks. This is native ARM development
acceptance; matching source,
SDK and kernel, AMD64, canonical lifecycle and the complete release remain open.

Storage was rechecked at 00:56 UTC on November 26. The Linux root has about
48 GiB free, below its 64 GiB archive reserve; scratch has about 181 GiB and
the native build volume about 126 GiB, above its 100 GiB floor. The original
second evidence host has about 149 GiB free, clearing its 64 GiB reserve.
The Intel tester's pool is healthy with about 870 GiB free. The NAS remains
degraded with one faulted device, another degraded device and two reported data
errors; migration and cutover remain on hold.

## Original default PNG qualification

The original `graphics/png` port at source
`fadd8b8b2e4bdd2a4a9c1af6deb6472bec9e4231` preserves APNG and ARM SIMD.
Its original `make test` uses the CMake testing bridge despite an empty
`TEST_TARGET`. All **37 original CTest cases pass**, with zero failures/skips;
an independent audit matches every discovered name, command and working directory.
The 293,396-byte package has SHA-256
`58f084e06e8b41148dc63a49b3df507bfd90f994657b524a30de784efd05a3b3`.
Production library bytes and the package remain unchanged by test reconfiguration.

Private checks pass 31 actual codec and 15 tool commands. Shared/static clients
exercise classic/simplified APIs, all five filters, APNG frame timing/sequence/CRC,
error callbacks and recovery. Independent PNG parsing/unfiltering checks 32 RGBA
planes. Actual CLI corruption repair, aliases and three manpages pass. Six real
isolated package transactions execute original ldconfig hooks through installation,
forced reinstall, removal and reinstallation. All 31 payloads verify.

The original normal installation succeeds with dependency checks and hooks enabled;
31 default codec commands pass. Its wrapper then fails because an observer scans
unrelated packages' manpages. The retained failure is followed by a read-only
completion restricted to the three owned pages. It passes 30 metadata/tool commands
and builds three actual default-discovery CMake CONFIG/MODULE shared/static clients
with Ninja. Installation, hooks and the earlier codecs are not replayed. All 110
inherited package prefixes and a fresh whole SDK111 prefix/raw database verify;
frozen SDK, base, accounts, actual loader cache, mounts and selected inputs remain
preserved. The accepted bounded ARM development set is now **111 packages**.

Complete source/private and normal capsules contain 3,552 and 298 nodes,
respectively, independently verified on native ARM and physical Intel. Earlier
observer failures and original sources remain retained. This does not qualify the
open CMake BSD-make space-path case or all backends/upstream tests.

The physical Intel tester separately passes the same 31 native codec commands
against its existing PNG package. All 30 installed payloads, 1,195 registry rows,
selected kernel/loader/base/accounts/cache and mounts remain unchanged. This is an
existing 1.5.1 component baseline; it does not qualify a new AMD64 package, SDK,
1.6 deployment, upgrade or rendered desktop. CMake is absent on this tester.
Its complete 228-node evidence capsule verifies on Intel and Linux scratch,
including actual nonzero BSD flags stored in an explicit numeric PAX field.
Mismatched flags and missing format declarations are rejected. No restore is claimed.

A fresh original-default Graphviz metadata plan preserves SDK111 and all feature
options: 59 nodes remain unbuilt, with 32 ready missing dependencies. This plan
provides no construction or runtime acceptance. See the
[detailed PNG report](https://github.com/jordanhubbard/daemonarchy-ports/blob/work/native-python-bootstrap-20261124/docs/verification/png-original-default-20261126.json).

Storage was rechecked at 02:06 UTC on November 26: local root has about 46 GiB
free, below its 64 GiB archive reserve; scratch has 181 GiB and native ARM build
126 GiB, above its 100 GiB floor. The second evidence host has about 88 GiB
free. The Intel tester pool is healthy with about 870 GiB available. The NAS
still has one faulted device, another degraded device and two data errors;
migration and cutover remain on hold.

## Original default libdatrie qualification

The unchanged original `devel/libdatrie` port at source
`fadd8b8b2e4bdd2a4a9c1af6deb6472bec9e4231` passes all eight construction targets.
All **10 unfiltered upstream tests pass**, with zero failures/skips; actual
Automake TRS results and logs match the original `TESTS`. This is direct original
`make check`; the port has no declared test bridge. Source files, production
library and package bytes remain unchanged by testing. The 41,075-byte package
has SHA-256 `44a9cfe14d503368ec101be17bdcd0c78489913889e39c3e170b58c45a109330`.

Independent private and normal checks each pass 33 actual commands. Shared/static
clients compare 8,192 mutations per writer with an independent 1,024-key model,
using disjoint ASCII/Thai alphabets and three seeds. Six cross-library persistence
pairs, serialization/file equality, embedded stream offsets, enumeration/iteration,
state clone/copy/walk/rewind and invalid alphabet rejection pass. Real CLI checks
cover aliases, UTF-8/Latin-1 conversion, add/query/delete, listing and export/import;
both owned manpages verify. Original version/help switches return exit 1; an
initial observer expecting 0 is retained and corrected from actual upstream source.

Six real isolated package transactions execute original ldconfig hooks, using
sealed qualified dependency libraries and read-only base mounts. All mounts are
removed. Normal installation then succeeds with original offline dependency/shlib
checks and hooks enabled. All 17 payloads, 111 inherited package prefixes, the
exact 112-row registry and ordered loader candidates verify. Real package integrity
and dependency checks pass. All 33 default consumers preserve a fresh whole SDK112
prefix/raw database, frozen SDK, base, accounts, actual loader cache, mounts and
248 selected source inputs. The accepted bounded development set is **112 packages**.

Complete source/private and normal capsules contain 1,406
and 113 nodes, respectively, independently verified on native ARM
and physical Intel. This advances the text dependency closure; matching AMD64,
source/SDK/kernel, complete desktop/apps and all broader release gates remain open.
The previous Graphviz plan predates this integration and needs refreshing. See the
[detailed libdatrie report](https://github.com/jordanhubbard/daemonarchy-ports/blob/work/native-python-bootstrap-20261124/docs/verification/libdatrie-original-default-20261126.json).

## Initial libthai installed-header assessment

The unchanged original `devel/libthai` 0.1.30 candidate passes all eight
construction targets and all **nine original default tests**, including both
dictionary-dependent cases. An independent audit matches actual `TESTS` to native
TRS/log outcomes and original test inputs to the verified distfile. Original
static-disabled and documentation configuration choices remain preserved.
The 187,178-byte package has SHA-256
`652654b56c066669ba92a4c9b5c6448740a96679a703d9703a64dff0a68f72c8`.

Private checks cover all 26 payloads and seven actual native client commands:
215 conversions checked with Python's TIS-620 codec, normalization, cells,
65,536 input pairs, 49 collation/transform pairs, controlled dictionary boundaries
at positions 4 and 7, and the actual packaged dictionary. Six real isolated
package transactions execute original ldconfig hooks; temporary mounts are removed.
Whole SDK112/raw database, frozen SDK, base, accounts, actual loader cache, mounts
and all 247 selected source inputs verify.

The first client fails to link the wide-collation functions declared by installed
`thwcoll.h`. A full installed-header audit finds **12 declarations without
implementations or exports**, across `thwcoll.h`, `thwinp.h` and `thwrend.h`.
All 17 headers match original distfile bytes, and every original versioned export
definition is present in the library. Sixteen headers compile individually;
`thwrend.h` fails because it uses an incomplete `struct thcell` in array parameters.
The later positive client covers implemented interfaces and retains this gap.
Complete API acceptance remains unresolved.

The initial assessment held the candidate and left the accepted development set
at **112 packages**; subsequent gperf and libthai admission records are below. Full source/build/test/failure/private/lifecycle/header
records (1,550 nodes) are independently verified on native ARM and Intel.
The later original-ABI/consumer review below scopes normal admission; full
installed-header API acceptance remains unqualified. See the [detailed libthai report](https://github.com/jordanhubbard/daemonarchy-ports/blob/work/native-python-bootstrap-20261124/docs/verification/libthai-original-default-20261126.json).

## Original default gperf qualification

The original `devel/gperf` 3.3 port preserves source, options, dependencies and
serial construction. All eight construction targets and original `make test`
pass. An independent audit verifies nine default groups, 24 expected-output
comparisons and three native SMTP generated-code runs; all original test inputs
match the verified distfile. The optional `extracheck` language-syntax matrix
remains unqualified. An initial source-list parser failure is retained; its
read-only correction does not replay the completed original tests.

The 88,319-byte package has SHA-256
`5e5fa3933fe097cf3cf70ed235997dc012aa6bd3d4d5f70c0e4c31fc4248aae6`.
Private and actual normal contexts each pass 21 commands and **31,992 native
queries** against independent Python keyword, payload and nonmember oracles.
Six generated ANSI C/C++ matrices cover readonly/global/enum/switch tables,
string/length comparison, Unicode, embedded NUL and ASCII case folding. Actual
version/help/error recovery, manpage, Info and HTML checks pass.

Six real isolated package transactions execute original Info-index hooks with
sealed qualified `indexinfo` bindings; the gperf menu appears, disappears and
returns through reinstall/removal/readdition. Before normal installation,
actual `indexinfo` rebuilds a private copy of the complete normal Info tree.
The first rebuild matches the original global menu, adding the exact candidate
adds only the expected gperf entry, and removal restores the original bytes.
The actual normal hook then produces precisely the predicted 5,486-byte menu.

Normal installation preserves all eight payloads and the other 112 package
prefixes except this predicted index and shared parent directory mtimes. The
registry is exactly the old 112 plus gperf. Package integrity/dependency checks
pass. Actual loader cache bytes/metadata and ordered candidates remain unchanged.
All default consumers preserve a fresh full SDK113 prefix/raw database; frozen
SDK, base/C++ runtime, accounts, cache, mounts and 247 source inputs verify.
At this checkpoint the accepted bounded development set reached **113 packages**;
libthai's subsequent admission is recorded below.

Complete source/private and normal/prediction capsules contain
1,518 and 152
nodes, independently verified on native ARM and Intel. Matching AMD64,
source/SDK/kernel, canonical lifecycle and complete desktop/physical/release gates
remain open. See the [detailed gperf report](https://github.com/jordanhubbard/daemonarchy-ports/blob/work/native-python-bootstrap-20261124/docs/verification/gperf-original-default-20261126.json).

Storage was rechecked at 02:38 UTC on November 26: local root has about 49 GiB
free, below its 64 GiB archive reserve; scratch has 180 GiB, native ARM build
126 GiB and the second evidence host 82 GiB. Intel's pool is healthy with about
870 GiB available. The NAS still reports one faulted device, another degraded
device and two data errors; migration and cutover remain held.

## Libthai admission against the original exported ABI

The release contract retains original implementation authority and scoped
acceptance. The exact selected Pango 1.58.2 distfile is verified against the
original port's hash and size. Its Thai implementation calls `th_brk`,
`th_brk_find_breaks`, `th_brk_new` and `th_uni2tis`; all exist in the actual
candidate's original exported ABI. It uses none of the 12 unimplemented header
functions. This source inspection establishes consumer requirements; actual Pango
compilation, layout and runtime qualification remain pending.

The earlier hold is reassessed against that original exported ABI and required
consumer surface. All declarations and original source remain preserved. The
12 absent implementations and `thwrend.h` compilation failure stay explicitly
unsupported/unqualified; no new implementation or full-header API pass is claimed.

Actual normal installation now passes with original offline dependency/shlib
checks and ldconfig hooks enabled. All 26 payloads, the other 113 package prefixes,
the exact 114-row registry, new libthai loader candidate and all previous
per-soname priorities verify. Real package integrity/dependency checks pass.
Seven native default-path commands exercise the implemented APIs and actual
installed default dictionary with no loader/dictionary override. A fresh complete
SDK114 prefix/raw database, frozen SDK, base, accounts, actual loader cache,
mounts and all 247 selected source inputs remain preserved.

The first normal observer accidentally referenced libdatrie's lifecycle result.
Its actual transaction and consumer results are retained. A separate read-only
completion binds producer/private/correct libthai lifecycle/normal package
identities and verifies that correct lifecycle result's body inside the already
verified 1,550-node source/private capsule. Installation, hooks and the seven
consumer commands are not replayed. The complete new normal/contract/binding
capsule (71 nodes) verifies independently on native ARM and Intel.
At this checkpoint the accepted bounded ARM development set reached **114 packages**. Full Pango,
installed-header API, canonical, matching AMD64/source/SDK/kernel, desktop,
physical, installer/update/rollback/media and signing/publication gates remain open.

## Brotli original default qualification

Original Brotli 1.2.1_1,1 advanced the accepted bounded ARM development set
to **115 packages**. All eight original construction targets and the original
28-program CTest suite pass with zero failures or skips. A separate audit matches
discovery, commands, working directories and actual completions; the original
LastTest log was retained before discovery. The original STATIC-off option stays
unchanged.

Eighty-eight private and 88 normal native commands exercise shared C one-shot and
streaming codecs, CLI behavior, pkg-config/loader bindings, malformed and truncated
input, error recovery, output boundaries, overwrite controls and shipped manuals.
Six corpora across 18 quality/mode cases produce 54 one-shot/streaming/CLI streams.
Existing Linux AArch64 Brotli 1.2.1 libraries decode all 54 byte-exact; this is
cross-binary/OS evidence on the same ISA, using the same upstream algorithm.
Native clients also consume controller-encoded vectors.

Six real lifecycle transactions verify original ldconfig hooks and all three
provider cache transitions. Normal installation enables original offline solver,
dependency/shlib checks and hooks. All 27 payloads, 114 inherited prefixes, exact
115-row registry, previous loader candidates and priorities, package integrity,
and fresh whole-SDK115/raw-database guards pass. Producer/private/lifecycle/normal
package identities are explicitly bound. All 54 normal streams match the already
controller-decoded private outputs. Frozen SDK, base, accounts, actual cache,
mounts and all 248 selected source inputs remain preserved.

The physical Intel tester's existing Brotli 1.2.1,1 decoder also decodes all 54 ARM
streams byte-exact: actual FreeBSD ARM-to-amd64 interoperability. Its existing
26 payloads, 1,195-row logical registry and selected system guards stay unchanged.
This existing Daemonarchy 1.5.1 baseline supplies no new AMD64 package build,
source provenance, installation, upgrade or 1.6 deployment acceptance.

Complete source/private evidence (1,719 nodes) and normal installation evidence
(266 nodes) verify independently on native ARM and Intel. The physical Intel
baseline capsule (178 nodes) verifies on Intel and Linux scratch, preserving
actual numeric BSD flags; mismatched-flag and missing-format controls reject.
Originals remain retained. Custom dictionary, comment, concatenated and
large-window extension surfaces remain unqualified by this standard-stream
matrix. Matching source/SDK/kernel, canonical lifecycle, desktop, physical,
installer/update/rollback, signing and full release gates remain open.

## FreeType original default qualification

Original FreeType 2.14.3 advances the accepted bounded ARM development set to
**116 packages**. All eight original construction targets pass, preserving
BROTLI, DOCS, LONG_PCF_NAMES and PNG and the original HarfBuzz-disabled bootstrap.
The final observer initially rejected CMake's enabled `true` spelling because it
required `ON`. That failure is retained; a read-only completion verifies the
actual enabled values, package identity and full preservation guards without
rebuilding.

Thirty-three private and 33 normal native commands exercise ten font inputs and
13 faces: TrueType, CFF OpenType, a four-face collection, WOFF1, BDF, PCF, gzip PCF,
bzip2 PCF and an immutable upstream WOFF2 fixture. Each matrix performs 372 glyph
render operations through both file and memory loading. Metadata, metrics and
bitmap outputs match byte-for-byte between those paths and between private and
normal installations. A known 8-by-8 glyph matches its independent bitmap oracle;
lossless WOFF1 matches its original TrueType, and both compressed PCFs match the
original PCF. WOFF2 actually decodes and renders through the accepted Brotli
provider. Truncated/malformed input and unsupported compressed-SFNT rejection,
followed by valid recovery, pass.

The original issue-1063 program and font are checked against the verified source
distfile and original download declaration. Its unchanged 112-character loop
completes with empty stdout/stderr; compilation supplies the standard `getenv`
declaration through `-include stdlib.h`. This is a direct original regression
program run. The original CMake port declares no test target, and no complete
Meson suite pass is claimed. Earlier private failures from an omitted base
pkg-config directory and an incorrect generic compressed-TrueType expectation
are preserved with their corrections; the original PCF driver defines the
compressed-font behavior. Product source, options and package bytes stay unchanged.

Six real isolated package transactions verify the original ldconfig hooks and
provider appearance, removal and restoration. Normal installation enables the
original offline solver, dependency/shlib checks and hooks. All 184 payloads,
115 inherited prefixes, exact 116-row registry, previous loader candidates/order,
package integrity and fresh complete SDK116/raw-database guards pass, with no
private loader or pkg-config override. Frozen SDK, base, accounts, cache, mounts
and all 248 selected FreeType source inputs remain preserved.

Complete source/private/failure/lifecycle evidence (2,956 nodes)
and normal evidence (102 nodes) verify independently on native ARM
and Intel, including all bodies, metadata, link topology and gzip CRC. Font
fixtures copied from existing controller packages qualify runtime inputs only.
Fontconfig, HarfBuzz, Pango, complete desktop applications and all matching
source/SDK/kernel, AMD64, canonical, physical and release gates remain open.

## Intel MacBook tester

The operator restored access to the physical MacBookPro16,1 tester. SSH and
passwordless administrative access are verified. It runs Daemonarchy 1.5.1 on
FreeBSD 16-CURRENT amd64, kernel revision `cb38d6498a24`, with an Intel i9-9880H
and 16 GiB of RAM. The ZFS pool reports healthy, with approximately 871 GiB
available to the root dataset.

The read-only baseline records all 1,195 installed packages and the kernel and
EFI loader hashes. The initial boot-environment inventory contained only
`default`. A recovery environment, `pre-1.6-20261125`, was then created;
`default` remains active now and on the next boot. No package or boot-setting
change was made. The separate home dataset is outside this root recovery copy.
Its creation does not establish boot or rollback acceptance.

SDDM, seatd and Hyprland processes are running; the AMD graphics module is
loaded and Broadcom Wi-Fi is associated. These observations do not qualify
rendered desktop interaction, wireless traffic, a 1.6 deployment or update and
rollback. The machine is a physical tester, not an allocated aggregate builder.

## Physical Pi 4 diagnostic reconnection

The operator brought the Pi 4 back online on November 25. Authenticated SSH
uses the retained operator key, and the host key matches the retained f4
Pi 4/Pi 400 diagnostic image. Its kernel and EFI loader bytes match that
image exactly: source `f4eb2cff7f8b5c511c448f0158f071105d19aaf5`, kernel
SHA-256 `a8c493095a72afff329f1b51a67a2ff125c9d289dc6c8193d2b28643350991d6`
and loader SHA-256
`a5f23fb00bdd7931c2e38d8948ccc9a19a39183b4dbc608ae212ed9e21077061`.
This is the older diagnostic cohort; it does not qualify the newly recovered
source/SDK cohort described above.

Firmware identifies a Raspberry Pi 4 Model B, revision D03115, with 8 GiB
installed and the diagnostic 3 GiB memory cap. The ACPI GENET interface has
DHCP and a 1 Gbit/s full-duplex link. The authenticated transfer of the
19,948,928-byte kernel and 1,389,068-byte loader verifies their bytes over
that wired path; it is not a network performance qualification.

The native BRCME88C SD controller enumerates the existing 64 GB card at
50 MHz/4 bits. Six bounded read commands cover three 1 MiB ranges, each read
twice with identical SHA-256 results and no reported read errors. Existing
FAT/Linux partitions remain untouched. No SD writes, filesystem mount, boot
acceptance, partition repair or disposable-media assumption is made for that
card. Keyboard and mouse devices enumerate, and the kernel reports a
1920-by-1080 EFI framebuffer; rendered desktop/input acceptance remains open.

The diagnostic root stays read-only. The bounded network hold was extended
to 86,400 seconds from its start to preserve debugger access. The target RTC
is stale, so the controller supplies observation timestamps. Original boot,
device and network evidence remains private, alongside the retained media.
The original DATRACE was copied through a read-only mount and unmounted; its
184,320-byte private archive has SHA-256
`2c2e1daf5851dfa957c9328b73f652bc0fd5abfe152338c14f98a05bf0095e69`.
No reboot, root remount, firmware change or full physical-release acceptance
is claimed.

A further read-only reconnection at 02:51 UTC on November 26 confirms the
same diagnostic kernel, read-only root, 86,400-second hold and active 1 Gbit/s
Ethernet link. The running kernel advertises only the DDB backend and EFI console.
A remote kernel debugger attachment remains pending. The probe enumerated debugger
control names without invoking entry, panic or control handlers.

The embedded configuration, read back separately at 03:33 UTC, confirms that
GDB, DDB, DEBUGNET and NETDUMP are compiled in, while NETGDB is not selected.
An unknown `kern.features.gdb` OID does not establish that GDB was omitted.
Only DDB is currently available as a backend. Exact running-source and selected
release-source inspection finds no debugnet registration or callbacks in either
GENET driver. The original NetGDB implementation requires a proxy and an active
interface with debugnet support; ordinary SSH over GENET does not meet that
requirement. The original debugnet connection code rejects unsupported interfaces.

A matched NetGDB build and qualified GENET polled transport, or an independently
working serial debugger path, are still needed before entering the debugger with
a confirmed remote return path. Both source views and bounded configuration
observations are retained. No debugger entry, module load, root remount, SD write
or reboot was performed; this remains diagnostic evidence, not physical release
acceptance.

## Remaining release gates

No new Pi image, 1.6 installed-system acceptance or signed release is claimed.
The [1.6 release plan](roadmap/release-1.6.0.md) retains matched amd64/aarch64
source, modules, packages and media; desktop and application behavior;
installation, update and rollback; canonical ownership/provenance/lifecycle;
the enrolled physical targets; and final freeze, signing and publication.


## LibYAML and Fontconfig test prerequisites

Original LibYAML 0.2.5 advances the accepted bounded ARM development set to
**117 packages**. All eight construction targets and the original `check`
target pass. Both discovered upstream programs complete with PASS and no skips
or errors. Independent shared and static clients preserve composed node, tag,
scalar and alias identity through six UTF-8/UTF-16 plain/canonical round-trip
matrices, each with two documents. Five malformed inputs exercise reader,
scanner, parser and composer errors, followed by valid-input recovery.

Six real package lifecycle transactions verify the original ldconfig hooks,
locked fixture accounts, read-only base mounts and complete unmount. Normal
offline installation preserves all 116 inherited package prefixes and loader
priorities, adds ten exact payloads and one shared provider, and yields exactly
117 registry rows. Shared and static consumers produce the same outputs as the
private clients through default pkgconf and loader paths. Whole SDK117/raw
database, frozen SDK, source, base, accounts, cache and mount guards pass.
Source/private/lifecycle (1,237 nodes) and normal (44 nodes) evidence archives
verify independently on native ARM and physical Intel; originals remain retained.

Fontconfig TEST exposed an ignored Meson option helper and an undeclared TAP
plugin. The helper correction runs all 16 original programs: 15 C programs pass,
while Python exits 4 for missing `--tap` support. The full failure remains
retained in [the draft fix and TAP source ports](https://github.com/jordanhubbard/daemonarchy-ports/pull/119).
The complete 184,387-member source composition and build/test dependency graph
verify. More-itertools completes all 929 original discovered cases and 245
independent checks; its normal/lifecycle/custody acceptance remains pending.
PyYAML builds with its original LibYAML option, but its original pytest target
fails during collection because the compiled extension is unavailable on the
test import path; the staged package contains that extension. This failure
remains retained. Adding staged site-packages to the test import path makes
the original selection report 2,608 passed; the resulting port fix is in draft
review. Corrected-source qualification and the per-case audit remain pending.
Neither the TAP tools
nor Fontconfig have normal acceptance yet; all broader release gates remain open.


## Python prerequisites for complete Fontconfig testing

More-itertools 11.2.1 and PyYAML 6.0.3_1 advance the accepted bounded ARM
development set to **119 packages**. More-itertools passes all 929 original
case identities and ordered completions, plus 245 independent seeded iterator,
streaming and differential checks. The retained initial audit parser mistook a
method doctest for its parent class; the corrected audit preserves every case.

PyYAML retains EXAMPLES/LIBYAML and all original upstream implementation,
assertions and test data. Its original collection failure is traced to the
compiled extension missing from the test import path. The port fix explicitly
preserves `${MAKE_ENV}` and adds staged site-packages; the earlier `TEST_ENV+=`
attempt suppresses the framework default and is retained as a failed metadata
observation with zero construction targets run. Fresh corrected-source native
construction and the original suite pass: 2,608 independently discovered cases
match 2,608 unique JUnit ID/file/line signatures and ordered passes, with zero
skips/errors/failures. All 598 original test/data files match the verified sdist.

Sixty-two independent pure/compiled YAML checks cover UTF-8/UTF-16 byte/file/text
inputs, scalar types, aliases, cycles, streams, custom types, token/event
semantics, malformed inputs, safe-constructor rejection and recovery. The
original warning about an ineffective assertion remains retained; normal
`yaml.load` without its required Loader independently raises TypeError and
subsequent valid `safe_load` succeeds.

Each package passes six real isolated package transactions. Neither declares
scripts/Lua/shared providers; none are suppressed or invented. Actual normal
offline dependency resolution, package integrity, default Python module/metadata
and compiled LibYAML binding checks pass. All 21/68 new payloads, 117/118 inherited
prefixes, exact 118/119 registries, previous loader cache bytes/metadata/priorities
and fresh whole SDK/raw database, frozen SDK, source and system guards verify.
Private and normal independent outputs match without private LD/PYTHONPATH
overrides. Source/failure/private/lifecycle capsules (1,062/3,283 nodes) and
normal capsules (30/34 nodes) verify on native ARM and physical Intel.

The two new TAP ports and complete Fontconfig TEST/default-runtime qualification
remain pending in [draft PR119](https://github.com/jordanhubbard/daemonarchy-ports/pull/119).
The source composition includes staged pytest-tap entry-point visibility for its
original pytester child processes; older qualified artifacts retain their actual
source revisions. Matching source/SDK/kernel and AMD64, canonical ownership,
provenance/lifecycle/SDK/TCB, complete desktop/apps/physical/installer/update/
rollback/media/freeze/signing/publication remain open.

The physical Pi4 remains reachable on its original read-only diagnostic root,
with only DDB available. Both exact running and selected source revisions also
refuse non-panic NetGDB. GENET polled callbacks and NETGDB configuration alone
do not establish live resumable attach: preserve that restriction pending
qualified buffer/transport/return lifecycle or an independently supported serial
path. This source/readiness audit enters no debugger and changes no target state.


## Tappy parser and package acceptance

The accepted bounded ARM development set is now **120 packages** after Tappy
3.2.1. Sealed tests reproduced six false passes across `tap` and `tappy`: the
original parser accepted `1xx2` as a plan and `okay` as a test result. The port
patch requires literal plan dots and word boundaries after `ok` and `not ok`.
All 116 unchanged original tests pass, with 16 test/data files byte equal to the
verified source archive. The first patched wheel accidentally included the
patch backup; that 63-file candidate remains rejected and preserved. The final
port retains the exact backup outside the wheel project and restores the
original 62 payload names.

Fresh native construction, the original suite, 90 independent checks with YAML
available and 87 with optional dependencies actually absent, and 48 real CLI
file/stdin/help/error checks pass. A separate producer oracle checks exact TAP
records; malformed input, missing results, failures and bailouts propagate.
Six real isolated package transactions pass without inventing scripts or shared
providers. Actual normal offline dependency resolution and integrity checks,
90 default library checks and the same 48 CLI checks pass without private import
or loader overrides. The original checker shadows its payload map with an exit
code after these consumers pass; that failed result and successful whole-SDK
final guard remain retained. A fresh read-only completion independently verifies
the missing payload/inherited-prefix checks without reinstalling or rerunning
the consumers. All 62 new payloads, 119 inherited package prefixes, loader
cache bytes/metadata/priorities and whole SDK/raw database/system guards verify.
Source/failure/private/lifecycle and normal archives verify on native ARM and
physical Intel. Detailed evidence and both rejected candidates are recorded in
[draft PR119](https://github.com/jordanhubbard/daemonarchy-ports/pull/119).

Pytest-tap, complete Fontconfig TEST/default-runtime acceptance and all wider
1.6 release gates remain open. NAS migration remains held by the degraded pool,
faulted/degraded disks and two data errors; Madmax remains 99% full. Qualification
uses the allocated ARM worker and healthy Intel tester. The Pi4 remains on its
read-only diagnostic root with DDB only; resumable live attach is unqualified.


The next pytest-tap 3.6 source candidate passes all eight original construction
targets and all 17 unchanged upstream cases, with independent discovery/JUnit
identity and ordered completion checks. All five test/conftest files match the
verified source archive, and captured nested pytest output is retained. Three
xdist cases exercise mock hook contracts; actual distributed transport remains
unqualified. The candidate is not normally installed: sealed plugin/CLI/nested
TAP oracles, lifecycle and both-host custody remain required before Fontconfig.


## Pytest-tap normal acceptance

Pytest-tap 3.6 advances the bounded ARM development set to **121 packages**.
All 17 original cases pass; the five test/conftest and seven total Python source
bodies match the verified archive. The sealed package passes 172 independent
checks across 25 commands, 22 TAP reports and 48 test points. Actual distribution
entry-point loading and its disabled-autoload negative control, stream/alias,
file/combined/outdir, help, logging, ordinary failures, call/setup errors, skips,
TODO, strict/non-strict XPASS and unittest outcomes are checked with an independent
stdlib TAP oracle. The three original xdist cases cover mock hook contracts only.

A teardown error can follow a passing call-phase TAP point. The complete result
must retain pytest's nonzero exit status: the actual Meson consumer independently
returns OK for success, FAIL for an ordinary failure and ERROR for this teardown
case. Reading only the TAP stream is insufficient.

All six isolated package transactions pass. Actual normal offline resolution,
integrity and the same 172 default-path checks pass without private import or
loader overrides; typed TAP semantics and Meson statuses match the private run.
All 16 new payloads, 120 inherited prefixes, loader cache bytes/metadata/priorities
and whole SDK121/raw database/system/source guards verify. Source/private/lifecycle
and normal capsules contain 1,531 and 291 nodes, fully verified on ARM and Intel.
Fontconfig's fresh original TEST build follows this prerequisite; full case/TAP
and default-runtime/Lua/sample/trigger acceptance remain open with the wider 1.6
gates.


The next Fontconfig TEST variant completes all 16 original Meson programs with
exit 0. Its independently matched TAP plan has 49 unique ordered cases: 21 pass
and 28 skip; two network-marked cases are deselected by the original selector.
All original test/data bodies bind to the archive except declared shebang
rewrites. The requested JUnit observer file is absent because ambient variables
are cleared by the ports environment boundary; the failed observer result is
retained and the actual TAP/discovery audit completes read-only.

Eighteen skips expose a missing json-c test executable. The TEST build dependency
is now declared before configuration. Other retained skips require an actual
older-version baseline (3), original disabled network access (2), or unavailable
Linux bwrap (5); these are not recorded as passes. Json-c 0.19_1 initially builds
and packages, but its original suite has 27 passes and one CLI failure with
`xxd: not found`. Its xxd test dependency is now declared without changing the
regression input, assertions or golden output. No Fontconfig/json-c normal
admission is claimed. Full source `82752667` verifies all 184,388 Git members,
11 changed/added paths and zero removals with SDK121/system and retained-source
guards. Prior qualified artifacts keep their original source pins.

## xxd prerequisite acceptance

Standalone xxd 9.2.1302 advances the bounded ARM development set to 122 packages.
The original source port imports its version/checksum from the twelve selected
editors/vim inputs and extracts only xxd plus the license/manual. All 257 selected
Git inputs and the official 20 MB source checksum verify. Its original port bridge
registers no source tests; this is not recorded as a full Vim suite pass.

The sealed and normal executable each pass 211 independent checks across 69 CLI
commands: byte-exact plain/reverse/formatted hex, widths/case, file seek/limit,
non-truncating patching, C include output plus actual C compilation/execution,
error statuses/recovery and the exact json-c 0xe2 fixture operation. The ELF binds
only base libc, with no private loader override. Six real package transactions,
all 6 payloads, 121 inherited prefixes, 122 exact registry entries, unchanged cache
bytes/metadata/priorities and whole SDK/system/source guards verify. An early
observer used the old SDK120 snapshot filename and ran no CLI cases; its failure
and the corrected SDK121 proof remain retained. Source/failure/private/lifecycle
and normal capsules contain 1,159 and 246 nodes, verified on ARM and Intel. The
installed compressed manual also decompresses to the original source bytes.

## json-c original suite after xxd

The fresh default json-c 0.19_1 package uses source `82752667` with the declared
xxd test prerequisite. All eight construction targets and all 28 original CTest
cases pass. The original CMake testing bridge changes BUILD_TESTING from OFF to
ON after packaging; production library, app and package bytes remain unchanged.
All 79 original test C files, scripts, fixtures and golden bodies match the
verified source archive, including the unchanged invalid UTF-8 regression input.

The producer queried CTest discovery before saving LastTest.log, truncating that
runtime trace to 121 bytes. The first healthy run's stdout and complete build/test
outputs are preserved. One full original make-test replay captures all 28 native
commands, working directories, outputs and PASS completions, matched to original
discovery. All compiled production and test binaries remain byte-identical.
SDK122/raw database, frozen SDK, base, accounts, cache, mounts and source guards
pass. Independent C API/shared/static/pkgconf/CMake consumers, actual loader-cache
lifecycle, both-host custody and normal json-c installation remain pending.

Fontconfig still needs its fresh full TEST coverage and separate default runtime,
font/cache/XML/CLI/shared/static and Lua/sample/trigger acceptance. All broader
1.6 release requirements remain open.


## json-c independent and normal acceptance

Json-c advances the bounded ARM development set to **123 packages**. The exact
original package identifies as 0.19_1, while pinned upstream commit `81092b3`
consistently identifies as 0.19.99 in its headers, runtime, CMake and pkgconf.
Four independent native consumers use shared and static libraries through
pkgconf and the installed CMake exports. Each passes 88 checks across the same
16-command run, with actual candidate/base loader bindings verified. Checks cover
JSON types, Unicode/NUL bytes, integers, copying, ownership, iteration, arrays,
pointers, patches, incremental/invalid UTF-8 parsing, limits, recovery and exact
file bytes. This is selected public-consumer coverage; complete API/ABI, OOM,
concurrency and fuzzing acceptance are not claimed.

Six original package lifecycle transactions exercise the real ldconfig hooks.
Actual normal offline dependency/integrity checks and the same four consumers
pass without private loader/import overrides. All 28 payloads, 122 inherited
prefixes and 123 registry entries verify. The new json-c loader provider preserves
every prior path and candidate priority. Source/failure/private/lifecycle and
normal capsules contain 2,897 and 106 nodes, fully verified on ARM and Intel.
The initial normal capture expected an absent convenience field; the corrected
capture checks the actual recorded package/source identities and result hashes,
without repeating installation or consumers. Both observations remain retained.
Whole SDK123/raw database, frozen SDK, base, accounts, cache, mounts and all 248
selected source inputs pass their guards. Fresh Fontconfig TEST coverage follows;
its default runtime/hooks and all wider 1.6 release gates remain open.


## Fontconfig configuration cases restored

The fresh TEST variant from source `82752667` passes all eight construction
targets and all 16 original Meson programs after normal json-c acceptance.
All 18 previously missing JSON configuration cases now execute and pass. All 49
selected nested case identities, order and outcomes agree across independent
discovery, the actual TAP stream and JUnit: **39 pass and 10 skip**. Two original
network-marked cases remain deselected. The JUnit observer now preserves the
original TEST_ENV and explicitly forwards only its reporting addition through
the ports environment boundary. All 71 original test/data bodies bind to the
source archive, allowing only three declared Python shebang substitutions.

The ten retained skips require an actual older-version cache baseline (3),
originally disabled network access (2), or Linux bwrap (5). No same-version build
is substituted for the older baseline. Complete cross-version/platform TEST
acceptance remains open. SDK123/raw database, frozen SDK, base, accounts, loader
cache, mounts and all 250 selected source inputs remain preserved. A fresh default
artifact and independent font/cache/XML/CLI/shared/static, Lua/sample/cache-trigger,
custody and normal acceptance remain required; the TEST package is separate.


The separate fresh default Fontconfig artifact now passes all eight construction
targets and its original zero-case test bridge. Default options, effective
arguments and dependencies match the retained original metadata. Its 344 payloads
and declared `/var/db/fontconfig` directory (root:wheel, 0755) require independent
runtime and actual Lua/sample/trigger/ldconfig lifecycle qualification before
normal delivery. The first preconstruction observer queried a field absent from
the narrower option probe; it ran no construction commands and remains retained.
The corrected guard binds that probe's fields and the original producer's
EXTRACT_DEPENDS/USES independently. The successful build preserves the complete
SDK123/raw database, frozen SDK, base, accounts, cache, mounts and selected source.


The full framework checks remain open: `litai project validate` reports a stale
human documentation-authority review. `litai verify` confirms all eight committed
locks are current, but its authority and receipt gates fail on that stale review;
source intelligence and HTML observability are skipped by the selected project
configuration. The review attestation is unchanged. Native package checks and
hosted security checks do not establish full framework or release acceptance.


## Fontconfig runtime and descendant font trigger

The revision-0 default Fontconfig package passes 54 private native commands with
ten exact font files and 13 faces. Shared and static consumers each pass 180
positive assertions and 46 malformed-XML/recovery assertions. Listing, matching,
querying, scanning, validation, user caches and expected font formats work through
the unchanged packaged sample configuration under explicit private paths. All
344 payloads and the outside-prefix cache directory verify; the normal host font
cache stays absent. Dependency metadata keeps its installed paths while only a
private copy of the candidate PC prefix is relocated.

The original lifecycle run then exposes a real delivery gap. Fontconfig's own
configuration files run its trigger, but a valid package placing fonts below
`share/fonts/daemonarchy-trigger` installs successfully without running fc-cache.
pkg's exact path matching receives the immediate touched directory, which does
not match the trigger's root-only path. The isolated cache has no font records.
All SDK/host/source guards and mount cleanup pass; the failure remains retained.

A copied isolated root changes only installed trigger path matching. Reinstalling
the exact same font fixture now runs the original fc-cache script and populates
both font records. The existing configuration-directory trigger and real XML
alias substitution still work. This is a causal control, not rebuilt-package
qualification. The source fix adds descendant matching for the configured
canonical and legacy system-font locations, aligns the configuration path with
LOCALBASE, and increments PORTREVISION to 1. Its complete source verification,
fresh original TEST/default builds, runtime, real lifecycle/custody and normal
acceptance remain pending. The accepted development set stays at 123 packages.


## Repaired Fontconfig normal acceptance

The repaired Fontconfig **2.18.3_1,1** package advances the bounded ARM development
set to **124 packages**. Source `d76dd1dd` verifies all 184,388 Git members, with
12 changed/added paths relative to the retained baseline and zero removals.
Fresh original TEST construction and all 16 programs pass again. Independent
discovery, TAP and JUnit agree on all 49 cases: 39 pass and 10 retain their
original skips, with all 18 JSON configuration cases passing. The fresh default
artifact passes its eight construction targets and zero-case bridge; this empty
bridge is not reported as an upstream suite pass.

The same 54 private/default commands pass with ten fonts and 13 faces; shared
and static consumers each pass 180 positive and 46 XML-negative/recovery
assertions. Actual default operation uses the original installed configuration,
real HOME user fonts and no private loader/configuration/pkgconf overrides.
All 344 payloads, the Lua-generated default fonts.conf, the root:wheel 0755
outside-prefix cache directory, 123 inherited prefixes and 124 registry entries
verify. The new loader provider preserves every prior candidate path and priority.
Whole SDK124/raw database, frozen SDK, base, accounts, mounts, selected source and
actual outside-prefix cache remain guarded through the consumers.

The lifecycle covers six accepted Fontconfig transactions and six authored
font/config fixture transactions. Deep canonical and legacy font-directory
add/delete events run the original cache script; cache records are read before
any discovery command. Configuration add/delete triggers apply and remove the
actual XML alias. Modified configuration contents, UID/GID, mode 0600, flags and
nanosecond mtime survive force reinstall/delete/readd; the unmodified sample is
removed and freshly restored as intended. Original ldconfig hooks and full
isolated mount cleanup pass.

Two authored checker errors remain explicit. The alias fixture initially used
weak binding, allowing documented language fallback; its intended exact match
now requests strong binding. The no-font check initially expected default
fc-match to fail, while upstream returns success with empty output. The corrected
check verifies that result and the --sort no-font diagnostic/failure. The retained
R2 fresh add and six passed trigger events are audited and bound to a copy of its
post-delete root; only the five remaining Fontconfig transactions execute in R3.
No passed trigger events or original upstream cases are replayed for that repair.
Original failed roots and all historical source/artifact identities remain intact.

History, corrected source/private/lifecycle and normal archives contain 18,019,
5,723 and 165 nodes respectively, fully verified on ARM and Intel. Complete
public API/ABI, a real older-version cache baseline, original optional skip scope,
product fonts/desktop rendering and all wider 1.6 release requirements remain open.

### Genuine older Fontconfig cache baseline, November 26

The three original cross-version cache cases now execute on ARM against a private
Fontconfig 2.17.1 build. Its 1,326,312-byte archive matches the original ports
`b70a2116` SHA-256; all 956 source bodies and 987 modes verify. Both actual runtime
versions and private library bindings verify. The original assertions, marker
filter and 600-second deadline remain unchanged.

Binary-format forward compatibility and forward discovery pass. Backward
discovery retains the original upstream XFAIL for baseline `.cache-9` versus
current `.cache-12`; full cache compatibility is not established. Source function
order, TAP and JUnit independently agree on two passes and one XFAIL. This is a
separate three-case supplemental run; the retained original 49-case suite remains
39 PASS and 10 SKIP with two original network marker deselections.

The complete older source, build, tests, preparation failures and helpers contain
3,338 nodes in a 17,523,916-byte archive, fully verified on ARM and Intel. Whole
SDK124, raw registry, frozen SDK, base, accounts, loader/system caches, mounts,
all 1,339 original current TEST nodes and 250 selected source inputs remain exact.
The installed development count stays 124. Wider release, original optional
network/Linux-bwrap, product font and desktop-rendering gates remain open. See
`docs/verification/fontconfig-older-cache-baseline-20261126.json` in the ports
review branch for the bounded report.

### Pixman original tests pass; runtime and package delivery remain held

Fresh native Pixman 0.46.4 TEST and default constructions pass all eight original
targets from source `d76dd1dd`. All 35 original native programs pass with the
port's existing 600-second deadlines and OPENMP serialization. OPENMP, ARM A64
NEON and the original shared-library choice remain enabled. The default variant
has zero test programs; its successful bridge is not suite acceptance. All 207
distfile source bodies match after the exact two existing port patch effects,
and all 249 selected recipe/framework/template inputs verify.

Four separate private C/C++ runs pass 24,826 checks each with normal dispatch or
NEON disabled, covering 8,192 independently computed OVER pixels plus matching
SRC/CLEAR vectors, masks, RGB565, explicit clipping, negative stride, transforms,
regions and reference lifetime. All ten package/framework payloads verify.

Three findings prevent normal admission. Without an explicit clip, the original
fill writes beyond the logical image; a padded allocation confirms the behavior
without an allocation overrun. The forced-general fill returns success without
painting, retaining two failed C/C++ controls. Fresh package add/integrity pass,
but a new executable with no RPATH or loader override cannot locate Pixman; the
original package declares no ldconfig hook. The positive clipped controls do not
resolve those original findings. Contract/source repair and fresh qualification
remain required.

All failed preparation checks, actual failures, original source, objects,
packages and probes remain retained: 4,411 nodes in a 39,615,838-byte archive,
fully verified on ARM and Intel. SDK124, its raw database, frozen SDK, base,
accounts, loader/system font caches and source inputs remain preserved; temporary
mounts are removed. Pixman remains normally uninstalled, so the accepted
development count stays 124. The ports ledger records details in
`docs/verification/pixman-native-findings-20261126.json`. All wider release gates
remain open.

### Repaired Pixman qualifies at bounded development count 125

Pixman 0.46.4_1 repairs the three retained original findings. Fast fills now
respect destination bounds, unavailable raw fills use the existing composite
fallback, and actual shared ldconfig hooks register/remove the library. The same
copied failing client passes after only the original shared ldconfig action; the
original failed root remains unchanged.

Fresh complete source `6032dbfb` verifies 184,389 Git members, fourteen changed or
added bodies and no removals. All 251 selected recipe/framework/template/keyword
inputs match review code `30770cfb`. Both original Meson port patches and all 35
original program names, arguments, environment, protocols and 600-second native
deadlines remain preserved; all 35 pass. Two added normal/general regression
runs also pass across ARGB32/RGB565/A8, both fill APIs, SRC/opaque OVER/CLEAR and
three clip configurations with guarded backing storage.

The fresh default package preserves its original OPENMP/A64 NEON/shared choices
and dependency arguments. Its zero-case test bridge remains a zero-case bridge.
The original unclipped C client passes in both C and C++, with normal, no-NEON
and forced-general dispatch: six runs of 24,824 checks each. Its three padded
controls now all paint exactly two logical pixels and no outside pixels. An
observer initially predicted the wrong check counter; a read-only completion
retains the successful original commands without replay. All original failures
and the lifecycle preflight field mismatch remain in custody.

All six actual package lifecycle transactions pass, including fresh executables
without RPATH or loader overrides after each add/reinstall and expected failure
after deletion. Normal offline dependency/integrity/hooks and the same six
consumers pass, plus a fresh no-RPATH client. All ten payloads, 124 inherited
prefixes, exact 125 registry entries and all prior loader priorities verify.
Whole SDK125/raw database, frozen SDK, base, accounts, loader/system font caches,
mounts and source guards pass. The accepted development count is now 125.

Original/repaired/normal archives contain 4,411/2,496/39 nodes and are fully
verified on ARM and Intel. The ports report
`docs/verification/pixman-fill-qualified-20261126.json` records exact artifact
identities and bounded scope. Complete API/ABI, desktop/apps/hardware, canonical
Component/provenance/lifecycle/SDK/TCB, matched source/kernel/AMD64 and all wider
1.6 release gates remain open.

### Signed-range fill follow-ups pass private qualification; normal upgrade held

Additional Box32 probes found two gaps beyond revision1's bounded acceptance.
A box spanning INT32_MIN to INT32_MAX reports success without painting when
raw fills are unavailable. Revision2 repairs that path and passes its original
suite, consumers and package lifecycle, but ADD still reports success without
painting through the separate general-composite path. All failed probes and the
complete intermediate revision2 remain retained; revision2 was never normally
installed.

Revision3 (`0b9e1861`, review code `91d12cb5`) keeps the bounded raw-fill region
alive and clips each original general box before signed coordinate subtraction.
It preserves repeated compositing of overlapping non-SRC boxes. All 184,389 Git
members and 251 selected review/native inputs verify. The same 35 original
programs and two extended regression runs pass with unchanged original options,
arguments, deadlines and OpenMP scheduling. The added regression covers ADD and
exact overlapping-box pixel values; its negative control detects the actual
revision2 failure in both normal and forced-general dispatch.

The fresh default package preserves all twelve selected dependency/option
metadata fields and its original OPENMP/A64 NEON/shared choices. The default
zero-case test bridge remains separate from the 37-case TEST result. Six
independent C/C++ consumers pass 24,824 checks each. All nine original small,
SRC signed-range and ADD signed-range probes paint exactly their expected
logical pixels with no outside changes. All six real ldconfig package lifecycle
transactions and fresh no-RPATH clients pass; temporary mounts are restored.
SDK125, its raw database, frozen SDK, base, accounts, loader/system font caches
and selected source remain preserved.

Complete intermediate/current archives contain 2,430/2,414 nodes in
25,100,320/25,096,883 bytes, with every body, type, mode, numeric owner, zero flag,
nanosecond timestamp, literal/hard link and gzip CRC verified on ARM. The
independent tester stopped accepting SSH during the intermediate archive copy.
The partial destination remains retained, independent custody is incomplete,
and neither revision2 nor revision3 has been normally installed. The accepted
normal count remains 125 on revision1 source `6032dbfb`; independent custody and
the actual revision1-to-revision3 upgrade are still required. The ports report
retains the exact identities and scoped results. The NAS remains degraded with
two data errors; no originals are reclaimed or new release publication claimed.

### Signed-range Pixman normal upgrade completes at count 125

Pixman 0.46.4_3 now passes actual normal admission at source `0b9e1861`.
The package transaction runs once; all ten new payloads and registry file entries,
124 other providers, loader priorities and the exact 125 registry count verify.
The six original C/C++ consumers pass 24,824 checks each, as does the fresh client
without RPATH or loader overrides. All nine small and signed-range SRC/ADD padded probes
pass. Twenty successful consumer commands remain retained without replay; the
final observer runs only the eight remaining wide-probe commands. Three old,
unregistered license files remain exactly preserved. Initial license-deletion,
missing-import and diagnostic-JSON observer failures remain with the successful
raw transaction and consumer observations.

The complete normal archive contains 84 nodes in 20,496,410 bytes, independently
verified on ARM and Intel with exact bodies, metadata, links and gzip CRC. It
includes the original raw before-database/prefix state, all observer failures,
retained successful consumers, final remaining probes and the new SDK125 seal.
All wider canonical, desktop, matching AMD64, physical and 1.6 release gates remain
open.

### LZO2 original checks pass; pkg-config header repair starts

The refreshed default graph has 52 missing nodes and 29 ready prerequisites.
LZO2's original DOCS/EXAMPLES shared/static construction, post-build `check test`
and package checks pass without disabling checks. All 306 source files match
both original patches, framework configure fixups and original staged doc edits.
Its declared ports test bridge is empty and remains separate from those actual
upstream self-tests.

A real private-prefix compiler control exposes the packaged flags: only
`-I${includedir}/lzo` is supplied, while public headers include qualified
`lzo/...` paths. The unchanged client fails with the original flags and compiles
when only the parent include directory is added. The initial metadata observer
failure and complete original source/package/private/compiler evidence remain
preserved in 1,622 nodes, fully verified on ARM and Intel. This original-version observation predates the repaired qualification below.

Review code `e3b88d6b` and native candidate `0164aca0` add the parent flag while
preserving the legacy include directory and all original tests/options. Complete
184,390-member native source verification and fresh original build/self-tests now
pass. Four independent C/C++ shared/static consumers each pass 432 cases and
11,179 checks, with both header styles and actual header/library bindings
verified. Successful C runs remain retained through driver repairs without
replay. Six actual original package lifecycle transactions now pass with fresh
clients after additions/reinstalls and expected loader failures after deletion.
The ports finding report records exact original package and custody identities;
source verification alone grants no native or canonical release acceptance.


### LZO2 corrected package reaches normal SDK126

Ports PR #121 preserves the legacy include flag and adds the required parent
include directory. Repaired source `0164aca0` passes all 184,390 Git-member,
251 selected-input and 306 independently referenced source-body comparisons.
Original default construction and exhaustive `check test` pass unchanged. The
four private C/C++ shared/static modes each pass 432 cases and 11,179 checks;
six real original package lifecycle transactions pass.

The actual normal offline package admission, integrity and dependency checks
pass. All 40 new payloads and all 125 inherited providers remain exact. The
registry now contains 126 packages, with one new LZO2 loader provider and all
prior loader paths and priorities preserved. The same four fresh normal modes
pass all 22 commands with both header styles and actual candidate bindings,
without RPATH, loader or pkg-config overrides. Full SDK126/raw database, frozen
SDK17, base, accounts, loader, font-cache, mount and selected-source guards pass.

Original 1,622-node, repaired source/private 1,945-node and normal 84-node
capsules are fully verified on ARM and independently on Intel, including all
bodies, metadata, literal links, hardlinks and gzip CRC. The initial capture's
strict anchor comparison failed on the known SQLite query sidecars; the failure
is retained and a new capture checks only that established narrow transition.
No completed producer or consumer was replayed. No additional Linux-root archive,
NAS use, cleanup or reserve reduction was needed. All wider canonical, desktop,
matched AMD64, physical and full 1.6 release gates remain open.


### Full default GObject Introspection reaches normal SDK127

Full default GObject Introspection 1.86.0,1 is now integrated separately from the
required named bootstrap. Source `0164aca0` verifies all 184,390 Git members,
249 selected native inputs and 2,634 independently referenced original source
bodies. All eight construction targets and 64 selected original Meson programs
pass with zero failures/skips. Original TEST-off, Cairo and documentation-tool
selection remains unchanged. The project-name observer mismatch is retained;
read-only completion binds the original inventory without replaying tests.

Private and normal contexts each pass 27 real scanner, typelib compiler,
inspection, generation and native reflection/invocation commands, including
changed library values and typed error/recovery controls. Six actual original
loader-hook lifecycle transactions pass with fresh processes and no RPATH.

The first normal preflight stops before any package or consumer command because
the named bootstrap already supplies the same SONAME. Its complete failure and
corrected helper have independent custody. The corrected admission requires the
new default library first according to the existing loader search order, keeps
the original bootstrap candidate second, and preserves all other provider paths
and priorities. All 239 new payloads, 126 inherited providers and exact 127-package
registry verify. Normal consumers use no loader or pkg-config override; the fresh
client has no RPATH. Full SDK127/database/frozen/base/accounts/cache/mount/source
guards pass. Source/private, preflight and normal capsules are fully verified on
ARM and independently on Intel. The original Cairo-test variant, full API/ABI,
canonical, matching AMD64, desktop/physical and full 1.6 release gates remain open.
