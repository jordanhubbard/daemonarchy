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

The existing allocated ARM worker was recovered with fresh writable overlays
on a separate local scratch disk. The crash disks remain unchanged backing
files. The host root volume still has approximately 46.5 GiB free, below the
recorded 64 GiB build reserve; the separate scratch volume has approximately
188 GiB available after the recovered work, evidence copies and private boot
image. Guards for resumed
writes must measure that writable volume.
Guest free space alone does not reserve host backing capacity.

The original producer requires at least 100 GiB free when filemon tracing is
enabled. Its guest had approximately 97.8 GiB free. A 16 GiB expansion of the
fresh overlay was completed without lowering that requirement. The crash-left
UFS filesystem passed an offline check covering 2,938,148 files before growth.
The mounted build filesystem had approximately 112 GiB available after growth.
Original
worker base-file hashes match their retained values, and filemon was restored
for the unprivileged producer. The supported resume is under a host monitor
that measures the scratch-backed writable volume, retaining its 120 GiB start,
64 GiB stop and 8 GiB available-memory thresholds. The monitor and native
wrapper both completed successfully.

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

Continue Simplified DocBook, ISO8879, SGML, the DocBook metaport and XSL closure,
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
15 sealed payload checks, 20 DTD consumer commands and 18 actual generated-hook
commands. Its normal local-only installation passed with empty stderr, clean
hooks, both master catalogs and all 104 inherited prefixes preserved. The two
catalog indexes changed exactly as predicted; all 20 default-global consumer
commands matched the sealed run. There are now 105 accepted development
packages. The source/private/failure/observer archive has 625 nodes, and the
normal-installation archive has 80; both were independently verified on both
evidence hosts. Original upstream self-suite, canonical and release acceptance
remain separate.

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
no repair is qualified yet. OpenSP has not been installed, and the accepted
SDK remains at 105 packages. The full SDK inventory was preserved by the build
and test runs.

An isolated production-code repair prototype passes 20 of the same 23 original
cases, including `catalog-2`, `af-10` and `af-11`; no test bodies, expected
outputs or suite membership changed. The remaining three failures include
expected-output issues and an unresolved content-mapping semantic discrepancy.
The prototype is not installed or accepted as a qualified parser repair.

ISO8879 1986_4 also passed all eight original construction targets from the same
selected ports tree. Its package SHA-256 is
`b5287bac8795a9eede78ee8c9fe6257841a67918c86394aaab7fd4d03506a73e`.
The installed prefix, logical registry and selected source/base guards passed.
It remains uninstalled; independent SGML/catalog consumers and generated-hook
checks are pending. Its original port exposes no selected upstream test bridge.

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

## Remaining release gates

No new Pi image, 1.6 installed-system acceptance or signed release is claimed.
The [1.6 release plan](roadmap/release-1.6.0.md) retains matched amd64/aarch64
source, modules, packages and media; desktop and application behavior;
installation, update and rollback; canonical ownership/provenance/lifecycle;
the enrolled physical targets; and final freeze, signing and publication.
