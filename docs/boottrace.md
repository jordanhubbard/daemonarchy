# Hardware trace stick: reset-surviving boot trace

When a machine hangs or resets during kernel startup with nothing on screen
that explains why (the MSI Raider 18 HX AI A2XWIG in
[hardware quirks](hardware-quirks.md#msi-raider-18-hx-ai-a2xwig-early-installer-reset)),
the boottrace kernel records each startup step in a UEFI NVRAM variable
before the step runs. A stick-based loop then files every boot's trace on
the stick and boots the next queued experiment, unattended.

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

UEFI variable stores append a copy on every write and most firmware cannot
reclaim space until the next boot, so each boot spends at most the free
space reported by `QueryVariableInfo` minus a 64 KiB reserve. By default
only **coarse** steps are persisted: the first SYSINIT of each subsystem,
every attach, hinted probes, hooks and events. The message-buffer tail in
each record shrinks as the budget drains, and two full-size writes stay
reserved for completion, panic or the budget stop. A coarse trace names the
subsystem or device where the boot stopped; the next experiment sets
`debug.boottrace.from=N` (N a little below the last step number shown) to
persist every step from there. If the budget runs out first, the trace says
so and gives the `from` value to use.

One variable, `DaemonarchyBootTrace`
`{9262df38-e448-4c99-bdd0-e70eada0faa1}` (NV+BS+RT), is overwritten in
place with a sequence number. Writing stops at completion. With
`debug.boottrace` unset the kernel neither reads nor writes it.

### Tunables

| Tunable | Default | Meaning |
| --- | --- | --- |
| `debug.boottrace` | 0 | enable tracing |
| `debug.boottrace.from` | coarse | persist every step from step N |
| `debug.boottrace.probes` | 1 | 0 none, 1 hinted probes, 2 every driver probe attempt (fine mode) |
| `debug.boottrace.msgbuf` | 1536 | message-buffer bytes per full record (max 3072) |
| `debug.boottrace.crumbs` | 8 | breadcrumbs per record (max 16) |
| `debug.boottrace.reserve_kb` | 64 | NVRAM left untouched |
| `debug.boottrace.max_writes` | 0 | cap on full-size writes (0: space only) |
| `debug.boottrace.test_hang` | - | **test only**: SYSINIT function, device or hook name to stop at |
| `debug.boottrace.test_reset` | 0 | **test only**: 1 triple-fault, 2 panic, instead of spinning with interrupts off |

## Other ways to read a trace

- **Loader prompt:** `boottrace show` (paged), `summary`, `save` (to
  `DAEMDBG/TRACExxxx.TXT` on a boot medium carrying `DAEMDBG/PROBE.TAG`),
  `clear`. Without the stick loop, the loader prints a one-screen summary
  at startup whenever the stored trace is incomplete.
- **Windows** (the MSI resets into Windows when the stick is not first):
  from an elevated PowerShell,
  `powershell -ExecutionPolicy Bypass -File tools\windows\read-boottrace.ps1`
  writes `DaemonarchyBootTrace-*.txt` and `.bin` to the desktop; `-Clear`
  deletes the variable afterwards.
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

## Building a stick

`tools/boottrace/make-stick.sh` remasters a live ISO: it adds the boottrace
kernel as `/boot/kernel.bt/kernel` (the default kernel; modules still load
from `/boot/kernel`), the boottrace loader on the ESP and as
`/boot/loader.efi`, the matching Lua, `loader.conf` settings, a 256 MiB
`DATRACE` partition and, with `-q`, an initial queue. El Torito is not kept:
write the image to a USB stick and boot it with UEFI.
`tools/boottrace/qemu-stick-test.py` drives an image through several boots
under QEMU/OVMF with a persistent vars file, resetting silent boots the way
the MSI firmware does.
