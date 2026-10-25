# Historical 1.3.2 network bootloader and MSI plan

**Superseded October 25, 2026:** The operator moved this feature to 1.4 P0 and
expanded it to remote interaction at `mountroot>`, boot-block/loader coverage,
early startup and panic. The [current 1.4 plan](release-1.4.0.md) and
[DEBUG-003](active-work.md#debug-003-deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14)
own implementation and acceptance. The scope and evidence below are retained
as historical design work, not a 1.3.2 completion claim.

- **Status:** active
- **Implementation state:** planned; target acceptance incomplete.
- **Product tracking:** [#33](https://github.com/jordanhubbard/daemonarchy/issues/33),
  [1.3.2 milestone](https://github.com/jordanhubbard/daemonarchy/milestone/2).
- **Source tracking:** [#21](https://github.com/jordanhubbard/daemonarchy-src/issues/21),
  [source 1.3.2 milestone](https://github.com/jordanhubbard/daemonarchy-src/milestone/2).
- **Owning queue item:** [DEBUG-003](active-work.md#debug-003-deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14).
- **Completion / archival evidence:** pending implementation, exact native/VM
  operation and failure matrix, separate image and physical MSI capture.
- **Owners:** product diagnostics (operator flow, controller and acceptance),
  owned FreeBSD source (loader, protocol and kernel), release integration
  (exact artifacts, firmware closure and qualification).
- **Release decision:** the operator moves this complete feature to **1.3.2**.
  This supersedes its earlier 1.3.1 assignment. Preserve existing releases,
  published tags, image bytes and recorded test scope.

## Required operator experience

Provide the bootloader equivalent of `daemonarchy-debug`: boot the diagnostic
medium, select **Network debugging**, select the built-in wired NIC and network
addresses, then connect from the controller with one documented command.
No SSH daemon, password, shared key, pairing exchange, certificate or additional
session authentication is required in this explicitly enabled mode. Retain
local input, visible enabled/connected status and a local Stop operation.
Installed-system SSH approval and credentials remain a separate facility.

From the controller, the operator must be able to:

1. Read live loader output and run ordinary loader commands with completion
   status, get/set/unset variables, inspect disks, kernels and loaded modules.
2. Select a kernel on disk, preload matching modules (including the NIC driver)
   from disk or the controller, inspect the selection and boot it without
   modifying the installed kernel or its configuration.
3. Supply a kernel image directly from the controller over UDP, together with
   required modules and boot configuration. TCP is optional; UDP transfer and
   TFTP download are the required first transport implementations.
4. Download Lua from the controller or a configured TFTP server, execute it in
   the ordinary loader interpreter, and receive output, errors and completion.
   Lua has the same loader authority as a local script; no restricted imitation
   of the Lua API or separate security approval flow is required.
5. Continue receiving early kernel output and stage records over the built-in
   NIC before normal PCI/NIC attachment, including a diagnostic pre-driver panic.
   Retain everything already received if the target resets or disappears.
6. Bring the USB back for analysis of saved firmware inventory and any report
   explicitly saved before boot. The controller is the durable destination for
   early-kernel output; do not promise a USB write during a hard reset.

For the MSI Raider 18 HX AI A2XWIG/RTX 5080, ACPI-enabled boot resets early without
a visible panic. ACPI-disabled boot reports `APIC: Could not find any APICs`.
The previously tried ACPI/SMP/panic tunables did not resolve it; repeating those
comparisons is not the implementation or acceptance plan. Use the built-in
Ethernet port for bring-up. USB Ethernet, Wi-Fi and BIOS boot are outside the
initial supported target.

## Current baseline and gaps

| Area | Reusable work | Remaining work for 1.3.2 |
| --- | --- | --- |
| Loader console | SNP UDP console, output queues and normal command interpreter | Explicit mode without keys, integrated controller and physical NIC qualification |
| Local boot | FreeBSD kernel/module loading and variable commands | Guided remote selection, exact matching inputs and disk-preservation acceptance |
| File access | Existing TFTP/netboot and Lua interpreter | Direct controller transfers, bounded staging, network script execution and real boot coverage |
| Hardware preflight | PCI/MAC/UNDI inventory and verified USB reports | Actual MSI report and admission of its real loader and early-kernel backends |
| Early kernel | Phase-identity primitives and later-driver NetGDB/debugnet prerequisites | Actual producer, pre-driver networking, startup instrumentation and ownership transfer |
| Evidence | Native loader builds and inventory/USB VM results | Complete transfers, Lua, kernel boot, fault captures and physical MSI evidence |

Merged source PRs #20/#22 and product PR #28 are prerequisite history. Product
issue #27 was closed after that integration; neither its closure nor the old
1.3.1 image name establishes completion. Preserve the
[inventory record](../../verification/earlynet-131-inventory-development.json)
and [USB-save record](../../verification/earlynet-usb-report-development.json)
without relabeling their source revisions, release targets or results.

## Architecture and interfaces

### Loader networking and controller

Extend the owned EFI loader and Python standard-library controller rather than
introducing an SSH server or replacing the FreeBSD interpreter. Reuse firmware
SNP while boot services are available. If the MSI exposes no usable firmware
network interface, an explicitly supported loader NIC backend is required;
finding the PCI device alone is not enough.

Add a deliberately selected `plain` debug mode to `netdebug` and the controller.
The setup menu defaults to this mode for this diagnostic workflow and does not
ask for a key. Preserve the existing authenticated mode as an independent
compatibility option; the plain path must not depend on its key/entropy setup.
Both sides must display the actual mode. Ordinary unattended boot remains
unchanged until the operator enables debugging; Stop closes the receiver and
cancels pending transfers. Do not require fresh approval for every command,
file or Lua script once this mode is active.

Define a versioned UDP protocol for discovery/status, command requests/results,
output, file begin/chunks/acknowledgements/commit/abort, and boot-phase events.
Reuse reviewed framing and queue code where its assumptions remain valid.
Use boot ID, command/transfer IDs, sequence numbers and duplicate suppression
for correlation and retry correctness; these are not authentication. Track a
controller endpoint for routing and reject stale-boot, malformed, out-of-window
and oversized operations. Make no claim that this unauthenticated mode refuses
an attacker capable of supplying otherwise valid messages.

Keep input and bulk file traffic separate from the console output queue so
loss/retry cannot starve local input, status or Stop. Specify byte order, lengths,
message limits, errors, retransmission intervals, overall deadlines and maximum
retry counts in the source protocol document before implementing both peers.
Negotiate the UDP payload limit and use a conservative initial payload below
the Ethernet MTU; do not rely on IP fragmentation. Exercise timeouts with actual
packet loss, reordering, duplicates and peer restart.

Proposed operator entry points (design targets, not working commands today):

```text
loader: netdebug setup                   # choose built-in NIC and plain mode
host:   daemonarchy-boot-debug TARGET
host:   vars get/set/unset; command; disks; kernels; modules
host:   select-kernel DISK-PATH
host:   send kernel LOCAL-FILE; send module LOCAL-FILE
host:   run-lua LOCAL-FILE               # transfer, commit, execute, collect result
host:   run-lua-url TFTP-PATH
host:   boot; status; stop
```

The wrapper may invoke the retained `loader-console.py`; finalize one canonical
installed command and `--help` interface in the first implementation milestone.
Document static IPv4 as the deterministic direct-cable path; optional DHCP must
have a bounded wait and a static fallback. Multiple firmware NICs require
explicit selection by location/MAC; bulk transfer must not silently change NIC
or reuse another interface's cached configuration.

### Kernel, module and script transfer

Implement a bounded, memory-backed staging filesystem visible to the ordinary
loader file API. Receive directly from the controller over UDP; also support
TFTP pulls through the existing network filesystem. A transfer manifest records
file kind, name, byte length and content digest. Digest verification detects
corruption and binds evidence; it is not a trust/authentication requirement.

Before allocation, check the advertised length, aggregate memory budget and
available loader memory with reserved headroom for the selected kernel, modules,
loader and firmware transition. Publish enforced limits in `status` and reject
oversized inputs. Check every offset/range and arithmetic overflow. Free aborted
or superseded staging objects. Partial files are never visible as complete,
loadable or executable. No transfer overwrites an internal-disk file.

Commit a file only after all expected bytes and its digest match. Keep file
transport separate from execution: the controller's explicit `run-lua` operation
commits then executes; an unsolicited/partial file does not run. Route scripts
through the real Lua interpreter and standard loader file operations. Return
syntax/runtime errors with a script ID and completion state; retain local
recovery after an error. Run interpreter work in its normal command context,
never from a NIC receive callback. Preserve ordinary Lua behavior; if a script
never yields, report that completion is unobserved and document local reboot as
recovery rather than claiming it was forcibly cancelled.

Use the existing ELF kernel/module loader and its dependency/relocation checks.
Record selected kernel and module digests, ABI/build identity where available,
load order and resulting boot variables. Refuse demonstrably mismatched modules;
unknown identity must be explicit. Do not silently mix a downloaded kernel with
ambient disk modules. Module dependencies must come from the selected compatible
set or fail with a specific missing-dependency result. Preserve an explicit
unload/reselect path and test both disk and staged-kernel boot.

A NIC `.ko` is preloaded data until the kernel initializes it. It supplies neither
a loader driver nor a guarantee of operation before the failing MSI stage.
The early transport below is an independent required implementation.

### Firmware exit and early-kernel transport

Use the actual MSI USB report to identify PCI vendor/device/revision, firmware
path/MAC, BIOS version and firmware runtime-network capability. Do not guess the
NIC family from the laptop model. Compare supported native drivers and required
firmware with the exact selected FreeBSD tree.

Choose the backend with recorded evidence:

- A runtime UNDI backend is eligible only if real descriptor, runtime memory,
  entry point, mapping, callback and DMA requirements are satisfied and packets
  work after firmware exit. Never call SNP after `ExitBootServices`.
- Otherwise implement a kernel-owned polling backend for the exact MSI built-in
  NIC. Specify BAR access, bus mastering, descriptor ownership, DMA addressability,
  cache/coherency, ring bounds, link setup and reset/timeout behavior. If loader
  networking also lacks firmware support, share reviewed hardware primitives
  with a loader backend while keeping lifecycle ownership explicit.

Before writing the backend, map the earliest usable kernel entry and the MSI
failure boundary. Reserve buffers and handoff metadata before firmware exit;
provide a versioned, length-checked loader-to-kernel record with boot ID, selected
NIC/endpoint, exact kernel identity and reserved ranges. Do not use inspectable
variables as a substitute for an implemented transport. Initialize only the
minimum mapping and hardware required for polling; avoid interrupt, scheduler,
ordinary allocator and full bus-attachment dependencies on the early path.

Emit a loader handoff record, a fresh kernel-phase event and bounded stage/output
records from the earliest instrumented entry through ACPI/APIC, SMP, device probes
and normal NIC attachment. Report the earliest actually covered stage; execution
before that point remains unobserved. Use bounded polling in panic contexts,
explicit dropped-byte counts and retained controller timestamps. Silence means
last observed stage plus transport loss, not proof of the reset's cause.

At native-driver attachment, quiesce the early path and establish exactly one
owner for RX/TX rings, callbacks and DMA buffers. Restore allocator/buffer class
and driver batching invariants addressed by existing debugnet prerequisites.
Test orderly takeover, failed attach, link loss and repeated debug enable/stop.
Choose and document whether the session then moves to normal kernel debugnet or
ends with an explicit handoff event. No success claim may hide a transport gap
at the MSI failure boundary. Free/zero reserved state only after its last owner
has released it; debug-off boot must not claim or alter the NIC.

## Source implementation map

Work in the owned FreeBSD integration branch through reviewable source PRs.
Retain upstream source locations and native build procedures. Initial change
locations, verified against the prerequisite source tree, are:

| Responsibility | Existing source to extend or preserve |
| --- | --- |
| EFI console activation, commands and framing | `stand/efi/loader/netconsole.c`, `netconsole_proto.c`, `netconsole_proto.h` |
| Firmware NIC ownership and console/netboot coexistence | `stand/efi/libefi/efinet.c` |
| Menu and normal Lua/boot execution | `stand/lua/netdebug.lua`, `cli.lua`, `core.lua` |
| Disk/module loading and environment commands | `stand/common/module.c`, `commands.c` |
| Network file pulls and new staging filesystem registration | `stand/libsa/tftp.c`, `stand/efi/loader/conf.c`, corresponding native Makefiles |
| Firmware preflight and USB report preservation | `stand/efi/loader/netconsole_hardware.c`, `netconsole_undi.c`, `netconsole_report.c` |
| Controller protocol, transfers and durable output | `tools/daemonarchy/loader-console.py`, new installed wrapper and protocol documentation |
| Later kernel transport and ownership invariants | `sys/net/debugnet.c`, `debugnet_inet.c`, driver-specific paths after MSI identification |
| Native builds, controls and separate image assembly | `tools/daemonarchy/tests/`, owned source CI and product release scripts |

Choose new early-entry/handoff and NIC-specific source files only after mapping
that kernel's initialization path and actual hardware. Record this selection in
the backend review. Preserve unit/ownership tests already guarding debugnet and
iflib while adding behavioral tests at the real network and boot boundaries.
The [FreeBSD loader manual](https://man.freebsd.org/cgi/man.cgi?query=loader&sektion=8&format=html)
and [EFI loader manual](https://man.freebsd.org/cgi/man.cgi?query=loader.efi&sektion=8&format=html)
provide upstream operator context; the pinned owned source and exact products
remain implementation authority for this work.

## Implementation sequence and completion gates

Each step produces a reviewable source change and its own exact test record.
Steps 2–5 may proceed before physical backend selection; do not wait for the MSI
to finish loader/controller work that is independently testable.

| Step | Deliverable and owner | Dependencies | Exit evidence |
| --- | --- | --- | --- |
| 1 | Diagnostics: protocol/CLI specification, plain-mode boundary and capability/status schema | This plan | Reviewed wire/state/error specification; no key needed to activate intended mode |
| 2 | Source + controller: plain UDP console and menu integration | 1 | Native EFI VM runs commands, variables, Stop and reconnect; local input remains usable |
| 3 | Source + controller: bounded staging, direct UDP transfer and TFTP pulls | 1–2 | Byte-exact kernel/module/script transfers, retry controls, abort and memory reclamation |
| 4 | Source: standard disk/staged kernel and module selection | 3 | Both kernels actually boot with matching modules; missing/mismatch paths fail clearly; disks unchanged |
| 5 | Source + controller: network Lua execution | 3 | Real downloaded Lua changes a variable, calls loader APIs and returns output; syntax/runtime errors recover |
| 6 | Source: MSI hardware report, backend decision and failure-boundary map | MSI report; reusable preflight | Exact NIC/firmware identities and supported loader/early-kernel backend decision; no assumed UNDI support |
| 7 | Source: handoff ABI, polling backend and early-stage producer | 6; exact selected kernel | Independent capture proves packets after firmware exit and before ordinary NIC attachment |
| 8 | Source: panic path, native-driver takeover and recovery | 7; debugnet ownership prerequisites | Pre-driver panic capture, controlled hard-reset last-stage record and successful normal boot/takeover |
| 9 | Release + diagnostics: standalone 1.3.2 diagnostic image and controller package | 2–5, 8 | Exact-image full VM matrix, firmware/trust closure, artifact hashes and documented operator runbook |
| 10 | Diagnostics + operator: MSI physical bring-up and release decision | 9 | Actual built-in-NIC capture across failing boot, retained logs and explicit interpretation/limitations |

The hardware-specific backend is the largest uncertainty. If the MSI lacks
usable firmware/runtime support, scope includes the required native backend;
record the dependency and effort rather than declaring loader-only work done.
No calendar estimate is committed before the NIC and early-entry constraints
are known. Mark per-step progress without closing the entire feature early.

## Acceptance matrix

All runtime rows require native-produced binaries and actual VM/hardware
execution. Packet fixtures and controller mocks supplement these results.

| Scenario | Required observation |
| --- | --- |
| Plain activation | Menu/prompt activation with no key, SSH, pairing or certificate; advertised plain mode matches controller |
| Remote shell | Output, command result and get/set/unset agree with local loader state; duplicate request does not execute twice |
| Disk selection | Explicit disk/kernel/module identity, successful boot, original disk bytes/configuration preserved |
| Direct network image | Controller UDP kernel and module transfer completes; resulting downloaded kernel really boots |
| TFTP | Kernel and Lua fetched through real network file API on selected NIC; no cross-NIC state confusion |
| Lua execution | Transfer and run a real script using loader APIs; output/result observed; malformed and missing scripts leave loader usable |
| Transfer faults | Drop, duplicate, reorder, truncate, corrupt, exceed budget and cancel; no partial execution or unbounded allocation; retry completes or times out |
| Peer/NIC faults | Missing NIC/peer, link loss, controller restart, repeated start/stop; bounded waits and usable local console |
| Handoff | Independent wire capture and stage IDs prove kernel packets after firmware exit before normal driver attach |
| Panic | Deliberate panic before normal NIC attach reaches controller through the production early path |
| Hard reset | Deliberate reset after a known early stage preserves already-received output and marks connection loss without inventing a panic |
| Normal boot | Kernel completes startup and native driver owns NIC correctly; repeated cycles and debug-off regressions pass |
| USB retention | Inventory save, second-boot preservation, full/read-only failure and no other-disk fallback; no promise of reset-time kernel USB writes |
| MSI | Exact release-candidate image and built-in NIC produce real early output during ACPI-enabled failing boot; record uncovered entry interval |

Controller capture starts before boot and remains readable on disconnect. Record
boot IDs, exact source/kernel/module/controller/firmware/image digests, NIC and
worker identities, command/protocol versions, timestamps, stage/loss counters,
independent packet captures and test outcomes. Keep raw machine logs private;
commit sanitized summaries and identities. Content digests establish evidence
and transfer integrity without adding session authentication requirements.

## Release boundary and definition of done

- [ ] All required operator operations and all acceptance rows pass for the
  selected products; unsupported cases and any unobserved startup interval are
  explicit. An image/receipt from a different source selection cannot substitute.
- [ ] Source prerequisite issues are resolved or their remaining limitations are
  explicitly included in the release decision; merge status alone is insufficient.
- [ ] The actual MSI capture is retained and analyzed far enough to identify the
  last observed stage and transport state. A transport implementation is not
  automatically a fix for the underlying ACPI/APIC/reset problem; track that fix
  separately if the capture identifies additional kernel work.
- [ ] Package the canonical controller command, `--help`, setup examples, disk and
  network boot recipes, Lua example, Stop/recovery and USB return instructions.
- [ ] Native loader/kernel build, input/toolchain admission, exact-image boot and
  applicable framework lifecycle/receipt gates are completed or reported as
  failing. Existing missing receipts are not waived by this planning document.
- [ ] Integrate through reviewed owned-source/product changes and exact-commit CI;
  create a new 1.3.2 candidate and preserve all existing releases/artifacts.
  Signing/trust selection follows the normal release workflow; plain debugging
  does not require weakening ordinary boot verification.
- [ ] Close product #33 and source #21 only with links to the exact qualifying
  artifacts and MSI evidence. Historical #27 stays historical.

This document scopes work; it does not implement a protocol, ship an image,
qualify the MSI, authorize a release publication or claim a passing receipt.
