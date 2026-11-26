# 1.6 release recovery, November 25

The release remains in development. This checkpoint retains the interrupted
native work and separates recovered results from new release qualification.

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

## Remaining release gates

No new Pi image, 1.6 installed-system acceptance or signed release is claimed.
The [1.6 release plan](roadmap/release-1.6.0.md) retains matched amd64/aarch64
source, modules, packages and media; desktop and application behavior;
installation, update and rollback; canonical ownership/provenance/lifecycle;
the enrolled physical targets; and final freeze, signing and publication.
