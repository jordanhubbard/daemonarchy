# 1.4.0: network debugging and an incremental release graph

- **Status:** active
- **Release scope:** 1.4.0; no 1.4 build or release qualification is claimed.
- **Priority:** P0 network debugging from boot blocks and loader through `mountroot>`, early kernel and panic. Distributed/incremental build work supports this release.
- **Completion / archival evidence:** pending exact native VM operation/fault matrix and physical hardware capture, cross-repository locks and receipts, artifact reuse, exact diagnostic image/feed qualification and published release verification.
- **Tracking:** [network debugging issue #33](https://github.com/jordanhubbard/daemonarchy/issues/33), [source issue #21](https://github.com/jordanhubbard/daemonarchy-src/issues/21), [build issue #39](https://github.com/jordanhubbard/daemonarchy/issues/39), [aarch64 issue #62](https://github.com/jordanhubbard/daemonarchy/issues/62), [1.4.0 milestone](https://github.com/jordanhubbard/daemonarchy/milestone/3).
- **Owning queue item:** [DEBUG-003](active-work.md#debug-003-deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14).
- **Headline feature:** a live, measured install screen ([UI-001](active-work.md#ui-001-deliver-measured-retro-installer-visualizers), P1 by operator direction on 2026-10-26).
- **Supporting queue item:** [PERF-002](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140) owns the build and release path.
- **Architectures:** amd64 and aarch64; [ARCH-001](active-work.md#arch-001-add-aarch64-as-a-second-supported-architecture-for-140) owns aarch64. Virtual machines are the aarch64 test bed for now.
- **Acceptance coverage:** [row-by-row owner, dependency and evidence ledger](1.4-coverage-ledger.md) tracks every 1.4 requirement and its exact proof.
- **Existing foundations:** [retained native execution](active-work.md#adopt-002-qualify-retained-native-execution-and-release-enforcement), [complete source and ports ownership](freebsd-components.md), [native workspace](native-workspace.md), and [build-performance work](build-performance.md).
- **Release boundary:** 1.3.1 is published and immutable. The [former 1.3.2 network plan](release-1.3.2.md) is historical; its requirements are carried forward here with the additional mountroot and panic acceptance. The operator-confirmed MacBook pre-production result and narrow final-ISO rerun waiver retain their original 1.3.1 scope.

## P0: network debugging across the boot boundary

Deliver a real bidirectional console/debugger session in explicitly enabled
plain mode. Do not add a key, pairing step or SSH dependency. Keep the local
console and Stop/recovery path available. Support ordinary loader commands,
variable get/set/unset, disk and downloaded kernel/module selection, direct UDP
and TFTP transfer, and downloaded Lua executed by the real loader interpreter.
Cover the boot blocks and loader, including the transition into the kernel;
state the earliest stage actually instrumented and any earlier gap. Firmware
SNP is usable only before `ExitBootServices`.

Before ordinary NIC attachment, provide a kernel-owned, bounded polled path
for output **and remote input** at a deliberately forced `mountroot>` prompt.
Continue through early startup, a deliberate pre-driver panic and a later
panic/debugger entry. Record boot and phase identity, the last successfully
received stage, dropped bytes and transport loss on the controller. A hard
reset must preserve already-received output without fabricating a panic.
Quiesce the early path before one native driver takes ownership of RX/TX rings,
DMA buffers and callbacks. Test normal boot, failed attach, link loss, malformed
traffic, timeout, controller restart and repeated enable/Stop cycles.

Choose NIC backends from retained PCI/firmware reports and native driver
evidence, never from the laptop model. Implement and qualify VM backends now;
physical MSI built-in-Ethernet acceptance follows once its exact report and
access are available. A loader-only packet capture or later-driver NetGDB
session does not qualify mountroot, panic or the MSI reset boundary. The
earlier [network design](release-1.3.2.md) remains a detailed implementation
reference, with this 1.4 scope and acceptance taking precedence.

The native VM matrix must force `mountroot>` and prove remote interaction,
deliberately panic before normal NIC attachment, panic later, hard-reset after
a known stage, boot normally through driver takeover, and inject transport
faults. Retain both passing and failed logs against exact source, kernel,
loader, controller, NIC and image identities. Build a separate exact 1.4
diagnostic artifact; do not modify the public 1.3.1 ISO or feed.

## Preserve and reuse the 1.3.1 build inventory

Before any substantial 1.4 build, record worker health and inventory every
retained package archive, installed package, signed repository/catalogue,
Poudriere jail/tree, object tree and shared cache in place. Verify artifact
bytes, provenance, ABI, options, flavors and dependency identities. Reuse or
requalify compatible outputs before queuing a genuinely necessary rebuild;
record the reason for every rebuild. No clean, distclean, prune, blanket
rebuild, replacement of old outputs or deletion of retained evidence is
allowed. Place new debugger builds, package candidates and diagnostic images
in isolated output roots, and keep existing mounts, active processes and
path-dependent environments intact. New linked worktrees belong under
`~/.worktrees/<repository>/<name>`.

Use owned finite supervisors for native jobs, with logs and exit records kept
outside older output roots. Final 1.4 QA must still obtain public binaries and
packages; local verified caches accelerate iterative tests only.

## Intended operating model

Literate AI owns one exact, cross-repository release plan and schedules its
dependency-ready actions on parallel native workers. Keep source authority in
each owned fork and preserve the FreeBSD package, installer and signing
contracts. Select the
executor by measured correctness and elapsed time: Bazel, remote build caches,
remote execution, other incremental tools, `make` and Poudriere are candidates.
`make` and Poudriere are not required architecture. Every action's inputs,
outputs, variants, dependencies and side effects must be visible to the LitAI
plan. Calling a full legacy build or release script as one opaque action is a
migration bridge; it cannot provide per-unit invalidation or worker scheduling.

The selected release workspace includes `daemonarchy`, `daemonarchy-src`,
`daemonarchy-ports`, `daemonarchy-desktop`, and `omarchy-freebsd`. Admit the owned
`omarchy` fork and any later release input only when the exact release selection
uses it. Record each commit, upstream ancestry, tree identity and integration
contract without collapsing independently maintained repositories into one
checkout. Preserve reviewable upstream refreshes and pin one selection for each
qualification run.

Both FreeBSD source and ports are now owned forks. The 1.4.0 implementation
may change any part of those forks needed to make source units, ports,
packages, base ABI contracts and release inputs accurately incremental and
distributable. Put dependency declarations, package metadata, build hooks and
cache integration in the fork that owns them where that yields an authoritative
graph. Preserve FreeBSD's functional ABI, package format and installation
contracts, native qualification and reviewable FreeBSD CURRENT refreshes; the
existing make/Poudriere execution model is not a constraint. Land the resulting
source and ports changes through their own reviewed main branches before the
1.4 release selection is locked.

## Cross-release artifact reuse and distributed execution

Before scheduling any release build, produce an exhaustive package inventory
against the last published release. Include every old and selected package,
including added and removed origins, build dependencies and package-only
changes. For each row, record exact source and port-tree identities, package
version, options, flavors, generated inputs, toolchain and base ABI, build and
runtime dependency identities, old artifact digest, selected artifact digest
when present, and the proposed reuse or rebuild reason. Fail the release plan
if any package lacks a decision or if an unchanged artifact is rebuilt without
a recorded invalidation or failed native qualification. Publish aggregate
counts, cache bytes and time saved, plus the per-package decision ledger with
the release evidence. The [1.1.1-to-1.3.1 application-feed inventory](../evidence/release-1.3.1-package-reuse-inventory.md)
is the baseline: it covers 510 old packages, including 320 with unchanged port
and dependency metadata and 162 requiring runtime ABI review. Its LibreOffice
row changed version and port inputs, so that package required a new build.

Always reuse a verified build output, binary, package or release input across
versions when its complete action identity is unchanged. A release number or
an unrelated repository commit must not force recompilation. Cache keys must
cover the exact source subdirectory and transitive shared inputs; port
Makefiles, distinfo, patches, plist, options, flavors and metadata; generated
inputs; compiler, toolchain and sysroot; the relevant FreeBSD base ABI;
build-time dependency contents and generated interfaces; runtime dependency
ABI contracts and version constraints; command, environment and output format.
Record the exact base OSVERSION and dependency versions as provenance. Recheck
retained bytes, provenance and signatures where applicable before a cache hit.
Re-sign or repackage only a changed envelope when the underlying payload
remains valid.

If the graph lacks an input or dependency edge needed for a sound key, repair
that graph gap before allowing reuse. Until it is repaired, rebuild the
affected unit and retain the reason. The 1.1.1 and 1.3.1 Chromium and CEF port
subtrees are identical, while their selected base OSVERSION and seven package
dependency versions differ. This is a regression case for separating actual
build inputs from runtime-only dependencies, rather than either rebuilding on
every version change or admitting a cache hit based on port-tree equality alone.
For a changed base or runtime package, allow reuse of a userland payload only
after proving the selected base and dependency ABI contracts, package version
constraints, installation scripts, native execution and relevant application
behavior still hold. Record the new qualification against the retained payload
digest and repackage metadata if required. Rebuild kernel modules, changed
headers or generated interfaces, static links, incompatible ABIs, and any
case without sufficient evidence. A changed OSVERSION by itself must trigger
requalification, not automatically a full userland rebuild.

The release pipeline must decide reuse before scheduling compilation, fetch
retained payloads from the shared cache, and record either the native
requalification receipt or a specific failed condition. A compatible base or
runtime-library version change must not queue Chromium or CEF for compilation
solely because that version changed. If compatibility tests fail, rebuild and
retain the failure. Duplicate full builds on other machines do not count as a
distributed speedup.

Treat ports and packages as graph artifacts. Evaluate Bazel incremental builds,
shared remote cache servers and other proven incremental or remote-execution
systems against equivalent native output and end-to-end time. Dispatch ready
build, test and package actions across multiple physical machines using their
CPU, memory, disk, network and target capabilities. Share verified immutable
artifacts, coalesce duplicate work for one action key, and recover from worker
loss without racing package databases or protected signing state.

Use a cache on the release engineer's network for pre-release build and
installer iterations. The iterative bhyve harness and installer test
configuration should accept an explicit package and asset cache source, with
each entry bound to the selected signed catalogue, package name, version, ABI
and SHA-256 digest. Reject mismatches, fetch verified misses, and record hits,
misses, bytes saved and elapsed time. Exercise a corrupt cache entry in a
fail-closed test. Final release-candidate QA must disable the local cache
override and fetch the actual public binary, package and feed URLs, then
verify their signatures and payloads during a fresh install and installed
boot. Cache savings from earlier iterations cannot stand in for that public
distribution check.

## Build, test, package and release graph

1. **Admit inputs and dependencies.** Assign source build units, ports origins,
   desktop and compatibility outputs, shared Makefiles, public headers,
   generated inputs, bootstrap tools, compiler/sysroot, target/options/flavors,
   firmware and package catalogues to canonical owners. Resolve conditional
   source and package edges. Reject missing or ambiguous ownership, incomplete
   closures and changed inputs instead of treating them as cache hits.
2. **Dispatch native work.** Use LitAI's worker model to run ready actions across
   multiple isolated physical machines, with explicit CPU, memory, disk and network
   budgets. Keep a stable action identity over command, toolchain, environment,
   selected inputs and expected outputs. Parallelize independent compilation,
   tests, downloads, package preparation and image inputs. Use shared verified
   caches and avoid duplicate work for the same action key. Serialize shared
   package-database writes, protected signing operations and any other action
   whose side effects cannot safely overlap.
3. **Retain products and evidence.** Capture verified source/build/runtime pkg
   outputs, versioned repositories, source and dependency SBOMs, native test
   reports, independent acceptance, logs, resource use and failure/retry state.
   Package and feed metadata must retain ABI, origin, flavor, options, exact
   dependencies and archive identities. A successful command exit alone does
   not qualify the selected product or release.
4. **Assemble and qualify one release.** Derive the signed feeds, boot bundle,
   installer ISO, checksums, documentation and GitHub asset selection from the
   same locked plan. Bind native tests, fresh VM installation, upgrade/rollback
   and scoped physical hardware checks to those exact artifact bytes. Keep the
   existing signing keys and private worker details outside committed metadata.

## Second architecture: aarch64

Ship 1.4 for aarch64 as well as amd64, built from the same selected source,
ports, desktop and compatibility revisions. aarch64 is a typed variant in the
release input graph, not a copy of the amd64 plan: it has its own world,
kernel, packages, signed feeds, UEFI installer image, cache keys, timings and
evidence. An amd64 result never qualifies aarch64, and a cache hit never
crosses architectures.

Little suitable aarch64 hardware is available, so qualify on virtual machines
first. The initial aarch64 worker is a FreeBSD arm64 guest under VMware on an
Apple silicon Mac, installed from the operator-supplied official FreeBSD
arm64 `dvd1` ISO. Verify that ISO against FreeBSD's published checksum and
record its name and SHA-256 before installation. The guest is the native
aarch64 build host and the first test target; the release graph admits it
as a worker only after the usual capacity and identity checks. Run Daemonarchy
installer and boot tests in separate VMware guests rather than nested inside
the build worker, so a failed test cannot disturb build state. Record the Mac
model, macOS and VMware versions, guest firmware and virtual devices with
each result. Cover installation, boot, upgrade, rollback, the desktop and the
network-debugging path where the virtual NIC supports it. A virtual result
qualifies only virtual operation.

Once the virtualized matrix passes, enlist the available Apple M1, M2, M3 and
M4 laptops as test machines. Record each laptop's exact model, firmware and
execution mode. Hosted virtualization on macOS is the expected first mode.
Bare-metal FreeBSD on Apple silicon is not assumed; claim it only for a model
where it has actually been demonstrated. A result on one Apple silicon
generation does not qualify another.

## Live desktop from the installer media

The FreeBSD installer media can boot to a live system, and Daemonarchy should
not offer less. Add a boot option that starts a minimal Daemonarchy desktop
from the ISO and RAM without touching any disk. Its purpose is to show whether
the desktop boots on the target hardware and, if it does, to run the complete
installation graphically instead of on the TUI. It does not need the full
application set: a compositor, a terminal and a graphical installer front-end
are enough.

Make the read-only ISO root usable without unionfs. Copy `/etc`,
`/usr/local/etc`, `/root` and `/home` into tmpfs at boot, as FreeBSD's
`rc.initdiskless` does; `/var` and `/tmp` are already tmpfs. Add GPU payloads
only on tmpfs layers mounted with `-o union`, which can add files but never
replace ISO files. A unionfs probe over the ISO's `/etc` stopped a FreeBSD
16-CURRENT host during `pw`'s password database rename, so unionfs is not
used. Select GPU modules from the ISO's own package
repository so the live desktop needs no network. The graphical installer
writes the same installation configuration as the TUI and renders the
installer's `@@progress` stream, so both paths share one install engine. Keep
pool import, disk swap and all disk writes off the live path until the
operator confirms an installation, and fall back to the TUI installer if the
compositor cannot start. The TUI installer remains the default boot entry.
See [LIVE-001](active-work.md#live-001-offer-a-live-desktop-from-the-installer-media-without-touching-the-disk).

## Proactive installer network bring-up

The network step is the most fragile part of an installation: a machine often
has several adapters, only some get DHCP, and the DNS servers that DHCP supplies
can be broken. Before any disk change, the installer works through these steps
on its own:

1. Find every wired, USB-tethering and wireless adapter, including devices still
   waiting for a driver or firmware. Loopback, the live medium's
   pseudo-interfaces and tunnels are not shown.
2. Probe all wired ports for DHCP at the same time, with bounded timeouts. Keep
   each lease's address, gateway, DNS and NTP servers. Choose the primary
   connection by link, lease and a gateway that answers ARP, and let the user
   override the choice.
3. Prove DNS by sending a record lookup directly to the server, never by ICMP.
   The DHCP servers come first, then Cloudflare, Google and Quad9. If none
   answers, accept a server the user enters, but only if it answers the same
   lookup.
4. Make the clock usable: no earlier than the image build, and inside the
   signing certificate's validity. Try network time before the manual clock
   screen.
5. Fetch only the firmware that is missing from the media.
6. Load the Wi-Fi drivers and create wlan0.
7. Join Wi-Fi if needed, then check DNS and the clock again over Wi-Fi.

With no working cable, steps 6 and 7 come first, using the firmware already on
the media, and steps 3 to 5 then run over Wi-Fi. The text, graphical and
unattended installers share this one pipeline. Unattended installs honor
their `net_*` answers and stop with a clear message instead of prompting. When
public or user DNS replaced broken DHCP DNS, the installed system keeps it.
See [NET-001](active-work.md#net-001-make-the-installer-network-bring-up-proactive-and-robust).

## Headline: a live, measured install screen

A real MacBookPro16,1 installation of 1.3.1 showed almost no visible
progress: "installation is still running" and then nothing until it ended.
For 1.4 the operator made a dazzling, truthful install screen a headline
feature. It stays alive in every stage with real activity: disk throughput and
IOPS for the target, network rates, per-core CPU, memory, and ZFS writes and
GELI where cheap. It shows a timeline of the stages (partition, encrypt, ZFS
pool, base sets, boot loader, configure, download, packages, account, verify)
with each stage's elapsed time from the installer's own markers, a scrolling
ticker of the package names pkg reports with count and total, and a
Winamp-style spectrum and scope driven by measured I/O rates, in 256-color
gradients with the Daemonarchy logo. Nothing invents a completion percentage
or time remaining. The FreeBSD vt(4) console is the primary target: it gets
the 16 vt colors and never 24-bit color, which vt(4) misparses. Plain output,
reduced motion, small terminals, VT100/serial and SSH keep working.

Nothing may depend on function keys or a virtual console switch, which many
laptops (including the Touch Bar MacBookPro16,1) cannot use. The screen runs
as window 0 of a locked-down tmux session with tmux's default `Ctrl-b` keys:
splits and windows show the install log, diagnostics, console-approved remote
debugging or a shell, while the installation keeps running and window 0
cannot be closed. Remote debugging can stay up from the configurator through
the installation. The live desktop's graphical installer (LIVE-001) shows the
same stages and metrics from the same producer. See
[UI-001](active-work.md#ui-001-deliver-measured-retro-installer-visualizers) and
[installer progress](../installer-progress.md).

## Delivery sequence and acceptance

- [ ] Inventory all selected fork revisions, tools, workers, actions and outputs;
  record complete-tree source/ports ownership and the 1.3.1 clean-build timing
  baseline, including world, kernel, package fetch/build, signing and ISO stages.
- [ ] Before queueing builds, compare every package in the prior public feed and
  selected release closure, including additions and removals. Produce the
  per-package reuse/rebuild ledger and account for every build, cache hit,
  invalidation, failed qualification, package byte and elapsed time. Reject an
  unexplained rebuild of an unchanged package. Include the 1.3.1 Chromium,
  CEF, OBS and changed LibreOffice cases in the regression fixture.
- [ ] Qualify retained native profiles and full dependency closures for every
  selected repository. Demonstrate that changed implementation, header,
  generated input, port option/flavor, compiler, sysroot and upstream commit
  invalidate the correct dependent actions; unchanged cross-release actions
  reuse their verified binary, package and release-input outputs without
  recompilation. Missing graph edges refuse cache admission until repaired.
- [ ] Implement required build, ports, package and ABI metadata changes in the
  owned FreeBSD source and ports forks, with native tests and reviewed merges
  to each fork's main. Demonstrate that the graph is authoritative at its
  actual producers rather than inferred only by an outer release wrapper.
- [ ] Split build-time inputs from runtime-only ABI/version constraints. Prove
  unchanged userland payload reuse across compatible OSVERSION and runtime
  dependency changes using native installation, package scripts, executable
  and application tests, exact payload digests and fresh provenance. Rebuild
  for changed headers, static dependencies, incompatible ABIs or failed tests.
  Use the 1.1.1-to-1.3.1 Chromium/CEF case as a positive or negative regression
  test determined by evidence, not an assumed hit.
- [ ] Run independent ready actions concurrently on at least two physical
  machines with a shared verified cache, bounded resources, retained
  partial-failure evidence and reproducible retry. Coalesce duplicate keys
  and show that package database and signing actions cannot race.
- [ ] Demonstrate verified local-cache hits in pre-release installer and build
  iterations, measured time and network savings, verified miss fallback, and
  rejection of a corrupt entry. Run final ISO QA with the cache override off
  against the public signed feeds and public package assets.
- [ ] Build and test the same selected source/ports/desktop/compatibility
  products with native tools under LitAI custody, then produce versioned pkg
  feeds and an installer ISO whose contents and signatures pass native checks.
- [ ] Measure equivalent clean, unchanged, changed-input, package-only and
  ISO-only runs against the baseline. Include single-machine and distributed
  runs, remote cache hit rates, prevented rebuilds, and action-level invalidation
  reasons. Set numeric speed targets from that baseline before implementation
  and demonstrate material end-to-end savings without skipping required
  products, tests or acceptance.
- [ ] Demonstrate the 1.3.1 regression is eliminated: an unchanged release
  rerun compiles no packages; a compatible base/runtime dependency update
  requalifies and reuses the retained Chromium/CEF payloads without compiling
  either browser; a changed browser build input or incompatible ABI rebuilds
  only the affected closure. Report wall-clock time, cache bytes reused and
  every admission or rebuild reason. A 1.4 release fails this item if it still
  repeats the 1.3.1 browser rebuild for a compatible version-only change.
  Measure the full build/package/sign/ISO critical path with the same required
  gates and worker pool: the compatible-update run must finish at least four
  times faster than an equivalent clean rebuild, and the unchanged rerun at
  least ten times faster. Record 1.1.1 and 1.3.1 observed timings separately
  from these normalized comparisons so earlier retries or hardware waivers
  cannot inflate a claimed speedup.
- [ ] Install the exact image in a fresh VM, exercise upgrade and rollback,
  complete the release's physical hardware matrix, publish through the
  LitAI-controlled release plan and independently verify the tag and assets.
- [ ] Build, sign and publish the aarch64 products, feeds and installer image
  through the same graph, cache and custody rules as amd64. Pass the aarch64
  virtual-machine install, boot, upgrade, rollback, desktop and network-debug
  matrix on the exact aarch64 bytes, then record scoped results for each
  enlisted Apple silicon laptop and execution mode.
- [ ] Boot the exact 1.4 image to the live desktop in a VM without writing to
  any disk, proven by before/after disk digests; complete a graphical
  installation from it; show the TUI fallback when the compositor cannot
  start; then record scoped physical live-desktop results, including the
  MacBookPro16,1.
- [ ] Run the installer's network check against the exact 1.4 image in VMs
  covering several NICs with only one offering DHCP, broken DHCP DNS,
  blocked public DNS with a user resolver, ICMP blocked, a wrong clock fixed
  by NTP and then by hand, and an unattended CIDATA install. Then complete
  the MacBookPro16,1 path with no cable: offline BCM4364 firmware, Wi-Fi
  first, then DNS and the clock over Wi-Fi.
- [ ] Install the exact 1.4 image on the physical vt(4) console and in a VM
  with a serial console while recording the install screen: every stage shows
  live measured activity and its elapsed time, the package ticker follows pkg,
  no element shows an invented percentage, and waits and failures are shown as
  such. On the MacBookPro16,1 with no function keys, open the log,
  diagnostics, a shell and remote-debug approval with tmux keys only, keep
  remote debugging up from the configurator to the end, and confirm the
  graphical installer shows the same stages and metrics.
- [ ] Bring release media and documentation into sync before calling 1.4.0
  published: update `release/current.json` from the verified published
  release with `scripts/release-current.py update`, covering every published
  image type (each architecture's installer and the separate hardware-trace
  bring-up image), then pass `tests/docs-release-sync.py` in CI and complete
  the HACKING.md release checklist for the README download section, release
  notes, checksums, image names, every current-state document and the image's
  own shipped documentation and data.

Completion requires working cross-release reuse, a distributed multi-repository
flow and retained receipts, not a renamed wrapper around the current serial
build. Keep `make` or Poudriere only where they meet the same native correctness
and elapsed-time targets as the selected incremental executor.
