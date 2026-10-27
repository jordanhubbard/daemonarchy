# Hardware trace stick: reset-surviving boot trace

When a machine hangs or resets during kernel startup with nothing on screen
that explains why (the MSI Raider 18 HX AI A2XWIG in
[hardware quirks](hardware-quirks.md#msi-raider-18-hx-ai-a2xwig-early-installer-reset)),
the boottrace kernel records each startup step in UEFI NVRAM before the step
runs. The **hardware bring-up trace image**
(`daemonarchy-hwtrace-<version>-amd64.img`, built by `build-hwtrace-image.sh`)
then runs an unattended loop. Each boot files the previous trace on the
stick and boots the next queued experiment. The image is a separate product
image type, not a mode of the install ISO. The install ISO's loader keeps at
most the interactive single traced boot and never cycles. HACKING.md
("Hardware bring-up trace image") gives the build and operator procedure;
this page describes the mechanism.

## One-time setup at the machine

1. In the firmware setup (MSI: **Boot** tab), put the USB stick first in the
   boot order. Secure Boot stays off. Save and exit.
2. Plug in the stick and power on.

That is all. Every boot, and every firmware reset after a hang, comes back
to the stick. The loader prints `Hardware trace: running the next queued
experiment in 5 s`, files the previous boot's trace as `TRACES/NNNN.TXT` on
the stick, clears the NVRAM variable and boots the next `QUEUE/NNNN.CNF`
with `boot -v`, `debug.boottrace=1` and panic settings (trace on panic, no
debugger, reset after 15 s). When a boot reaches init, or the queue is
empty, the loader shows **HARDWARE TRACE: STOPPED** with the reason and
waits at the `OK` prompt. Pressing a key during the 5 s countdown gives the
normal menu instead; its **Hardware trace** entry (`W`) runs one cycle by
hand.

When a boot reaches init, the image's rescue root saves bring-up
diagnostics before it reboots. It writes `dmesg -a`, `sysctl -a`, `kenv`,
`kldstat`, `pciconf -lvbc`, `devinfo -vr` and `acpidump -dt` to
`DUMPS/<experiment>/`, and the next boot stops the loop.

Then unplug the stick and bring it to the controller host. Remove it only
when the loader is at the STOPPED prompt or the machine is off.

## On the controller host

The stick has a FAT32 partition labelled `DATRACE`. Linux mounts it
directly (for example `/media/$USER/DATRACE`); `stick.py` also works on an
unmounted device or image through mtools.

```sh
tools/boottrace/stick.py status  /media/$USER/DATRACE
tools/boottrace/stick.py traces  /media/$USER/DATRACE --out traces-$(date +%F)
tools/boottrace/stick.py queue   /media/$USER/DATRACE next.txt
```

`queue` replaces `QUEUE/`, resets the queue pointer and keeps the filed
traces (numbering continues; `--reset-traces` deletes them). An experiments
file is a list of blocks:

```ini
[legacy-off]
read-conf /boot/d/1

[legacy-off-no-hpet]
read-conf /boot/d/1
hint.hpet.0.disabled=1

[zoom-after-step-1200]
read-conf /boot/d/1
debug.boottrace.from=1200
```

Lines are `name=value`, `unset name` or `read-conf /path` (a preset on the
ISO, such as `/boot/d/1`..`/boot/d/4`), applied in order after the defaults
above, so they may override them.

Each trace file names its experiment and settings, then the record:
status (`INCOMPLETE` = never reached init, `complete`, `PANIC`), the last
step, the newest breadcrumbs and the tail of the kernel message buffer.

## What is recorded

| Step kind | When |
| --- | --- |
| `sysinit` | before every SYSINIT; function name as `VERBOSE_SYSINIT` resolves it, subsystem and order |
| `probe` | before `DEVICE_PROBE` (driver, device, parent; location for hinted devices) |
| `attach` | before every `DEVICE_ATTACH` (device, parent, driver, bus location) |
| `hook` | before each interrupt-driven configuration hook |
| `event` | `vfs_mountroot`; completion just before init is executed |
| `panic` | the panic message, written from `panic()` |

Every step is kept in a RAM ring. EFI runtime services (efirt) start at
`SI_SUB_DRIVERS`/`SI_ORDER_SECOND` on amd64, before `SI_SUB_CONFIGURE`, so
device probing is always covered; the RAM breadcrumbs from earlier steps
are flushed in the first write. Writes are synchronous `SetVariable` calls
made before the step runs, so a hang with interrupts disabled still leaves
the step on NVRAM.

### NVRAM budget and zooming in

UEFI variable stores append a copy on every write, and most firmware cannot
reclaim space until a later boot. A laptop store can be nearly full: the
MSI Raider (AMI E1824IMS.317) reports only 55 KiB free. Each boot therefore
spends the free space `QueryVariableInfo` reports, less a reserve. The
reserve is a quarter of the maximum variable size, kept between 8 and
16 KiB.

The kernel writes two variables (same GUID):

- `DBTStep` is written before every persisted step. It is a 64-byte
  breadcrumb holding the sequence, step number, subsystem and order, kind,
  time and a 40-character name. It costs about 140 bytes of store on OVMF,
  and the kernel measures the real cost on the second write. About 250 to
  300 fit in 40 KiB.
- `DaemonarchyBootTrace` is the full record: newest breadcrumbs plus the
  message-buffer tail. It is written at the first opportunity, when the
  fine-grained region starts, every 64 breadcrumbs while more than half the
  budget is left, and at panic, completion or the budget stop. Two full
  writes are always reserved.

Readers show whichever of the two is newer.

Before `debug.boottrace.from_sub` (default `0x3800000`, `SI_SUB_CONFIGURE`)
only the first SYSINIT of each subsystem is persisted. From there, every
SYSINIT, attach, config hook and each device's first probe is persisted.
Hinted (fixed-class) probes are always persisted. Per-device probes stop
once 60% of the budget is spent (flag `thinned`).

To zoom in, move `from_sub` later or set `debug.boottrace.from=N` to persist
every step from step N. If the budget runs out, the trace says so and names
the step.

Each trace file also records the boot-time store figures. Compare the
"NVRAM free at start" of successive traces to see whether the firmware
reclaims on its own. `boottrace_compact="YES"` makes the loader try to
force a reclaim by rewriting a scratch variable. It is off by default:
under OVMF, with a crowded store, it left less space (27 KiB instead of
52 KiB).

### Tunables

| Tunable | Default | Meaning |
| --- | --- | --- |
| `debug.boottrace` | 0 | enable tracing |
| `debug.boottrace.from_sub` | `0x3800000` | persist every step once this SYSINIT subsystem starts |
| `debug.boottrace.from` | - | persist every step from step N |
| `debug.boottrace.probes` | 1 | 0 none; 1 hinted probes plus each device's first; 2 every driver attempt |
| `debug.boottrace.reserve_kb` | auto | NVRAM left untouched (auto: max variable / 4, 8..16 KiB) |
| `debug.boottrace.full_every` | 64 | full-record checkpoint interval in breadcrumbs (0 off) |
| `debug.boottrace.msgbuf` | 1024 | message-buffer bytes per full record (max 3072; 512 in a cramped store) |
| `debug.boottrace.crumbs` | 6 | breadcrumbs per full record (max 16; 4 in a cramped store) |
| `debug.boottrace.max_writes` | 0 | cap the budget at N breadcrumbs (0: space only) |
| `debug.boottrace.test_hang` | - | **test only**: SYSINIT function, device or hook name to stop at |
| `debug.boottrace.test_reset` | 0 | **test only**: 1 triple-fault, 2 panic, instead of spinning with interrupts off |
| `hwtrace.shell` | - | trace image: `YES` gives a shell after the diagnostics instead of a reboot |

## Other ways to read a trace

- **Loader prompt:** `boottrace show` (paged), `summary`, `save` (to
  `DAEMDBG/TRACExxxx.TXT` on a boot medium carrying `DAEMDBG/PROBE.TAG`),
  `clear`. Without the stick loop, the loader prints a one-screen summary
  at startup whenever the stored trace is incomplete.
- **Windows** (the MSI resets into Windows when the stick is not first):
  from an elevated PowerShell,
  `powershell -ExecutionPolicy Bypass -File tools\windows\read-boottrace.ps1`
  reads `DaemonarchyBootTrace` and `DBTStep` and writes
  `DaemonarchyBootTrace-*.txt` and `.bin` to the desktop; `-Clear` deletes
  both variables afterwards.
- **Linux:** `tools/boottrace/decode-boottrace.py --efivarfs
  /sys/firmware/efi/efivars/DaemonarchyBootTrace-9262df38-e448-4c99-bdd0-e70eada0faa1`;
  `--vars` decodes a QEMU OVMF vars file and counts stored copies.
- **Wired network loop (optional):** with `boottrace_loop="YES"` and the
  plain `netdebug.*` settings in `loader.conf`, the loader starts the wired
  console, waits `boottrace_controller_wait` seconds for
  `tools/boottrace/boottrace-loop.py`, which reads the trace with
  `boottrace report` and sends the next experiment; otherwise it boots the
  `boottrace_conf` preset. The stick loop (`boottrace_autocycle`) takes
  precedence when both are set. This network path has not been exercised
  yet; the MSI stick image does not enable it.

## Building the image

`build-hwtrace-image.sh` builds the image on the FreeBSD builder from a
boottrace kernel, the boottrace loader and Lua, and the release ISO the
kernel matches; see HACKING.md. `tools/boottrace/make-stick.sh` is the
earlier interim remaster of a live ISO. It was used for the first MSI
iterations and adds the same stick settings (`boottrace_stick`,
`boottrace_autocycle`) to a copy of the ISO.
`tools/boottrace/qemu-stick-test.py` drives an image through several boots
under QEMU/OVMF with a persistent vars file, resetting silent boots the way
the MSI firmware does. `--bus ahci` attaches the stick as SATA, because
QEMU's USB storage emulation rejected the rescue root's writes.
