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

## How the loader writes the stick

On the MSI Raider (AMI Aptio E1824IMS.317), the dev2 image showed the
countdown, booted experiment 0001 and cycled after the kernel hung. The
stick came back byte-for-byte unchanged: `STATE.TXT` still read `next=1`,
and there were no `TRACES/` and no `DUMPS/`. The loader had not stopped
with "Writing STATE.TXT on the stick failed", so its read-back check
passed. The same stick contents work under QEMU/OVMF. The firmware's FAT
driver had acknowledged the writes and served the read-back from its cache,
and the data never reached the stick before the reset. That loader would
have repeated experiment 0001 forever. The earlier interim stick (a
remastered live ISO) did get its FAT-driver writes onto the stick on the
same machine; those writes created and extended files. The dedicated
image rewrites preallocated files in place on a different layout. Which
of those differences the AMI driver mishandles is unknown, so the loader
no longer depends on it. QEMU checks of this design are in the
[raw-block test record](testing-1.4-hwtrace-rawblock-20261027.md).

The loader now avoids the FAT driver for writes:

- **Block map.** `build-hwtrace-image.sh` preallocates `STATE.TXT` and the
  200 `TRACES/NNNN.TXT` slots. `stick.py write-map` then records each
  file's offset and size inside the DATRACE partition in `SLOTS.MAP`,
  together with the partition's start and length and an FNV-1a checksum.
  It refuses a file that is not contiguous.
- **Raw writes.** The loader accepts the map only after these checks:
  - the checksum is valid and every extent is sector aligned, inside the
    data area and not overlapping another
  - the partition's BlockIo length and its device-path start match the map
  - the sectors the map gives for `STATE.TXT` hold what the FAT driver
    returns for the file; it repeats this check for each slot before the
    slot's first write

  It then rewrites a file's sectors with `EFI_BLOCK_IO.WriteBlocks`, reading
  partial blocks first. It calls `FlushBlocks` on the partition and on the
  whole disk, and reads the sectors back through the disk's own BlockIo
  after checking the `MediaId`. A write that does not read back equal stops
  the loop with the reason.
- **Fallback.** A stick without a usable map, such as one from an older
  builder, is written through the FAT driver as before, and the screen
  says so.

The rescue root's `DUMPS/` are written by FreeBSD's msdosfs after init,
not by the loader, so the map does not cover them.

### Loader self-report and the loop counter

The loader keeps its own record in NVRAM. The 128-byte variable
`DBTLoader` holds the queue epoch, the cycle number and the last step
reached: found stick, read `STATE.TXT`, filed trace, chose experiment,
wrote and verified `STATE.TXT`, booting, or stopped. It also holds the
write method (raw or FAT), the write status, the read-back result, the
`STATE.TXT` values it wrote and read, and a repeat counter. The loader
saves it at each step, so the stick is never the only loop counter. Each
filed trace includes the previous cycle's record (`loader previous:`) and
the current method (`loader now:`).

At the start of a cycle, the loader compares the stick's `STATE.TXT` with
`DBTLoader`. If the previous cycle got as far as booting an experiment,
but the stick does not hold the `next`, `traces` and `pending` values that
cycle wrote, the stick's writes did not persist. The loader then shows:

```text
=========== HARDWARE TRACE: STOPPED ===========
STICK WRITES ARE NOT PERSISTING.
Cycle 1 wrote STATE.TXT next=2 traces=0 pending=0001 via ... (read-back ...),
but the stick still reads next=1 traces=0 pending=-.
```

It leaves the kernel trace in NVRAM and waits at the prompt; the trace can
be read with `boottrace show` or the Windows reader. The verdict sticks
across reboots until the stick is queued again, which starts a new epoch
(`epoch=` in `STATE.TXT`, written by `stick.py queue` and the builder), or
until `boottrace clear`. As a second guard, staging the same experiment a
third time in a row stops the loop (`boottrace_max_repeat`, default 2).
Sticks without an epoch use epoch 0. Do not queue them between cycles
while a loop is running.

### Testing the failure paths

`boottrace_test_drop` in `loader.conf` (built in with `build-hwtrace-image.sh -S -x
knobs.conf`) makes the loader acknowledge writes without making them:

- `fat`: FAT-driver writes, as on the MSI
- `raw`: block writes, with no read-back
- `all`: both

With a valid map, `fat` changes nothing, because the raw path does not
touch the FAT driver. Without a map, `fat` reproduces the MSI: the next
boot stops with STICK WRITES ARE NOT PERSISTING. `stand/efi/loader/
boottrace_blk.c` is also checked on any host by
`tools/daemonarchy/tests/run-boottrace-blockmap.sh` in daemonarchy-src,
against a fake BlockIo whose writes reach only a cache.

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

The kernel writes these variables (same GUID):

- The breadcrumb ring `DBTStep00` .. `DBTStep15` (`debug.boottrace.ring`,
  1..64). One slot is written before every persisted step. Breadcrumb `N`
  overwrites slot `(N - 1) % ring`, so the newest steps before a hang are
  always on NVRAM, and the live footprint is bounded at about 2 KiB for 16
  slots, well inside the reserve. A breadcrumb is 64 bytes: sequence, step
  number, subsystem and order, kind, time and a 40-character name. It costs
  about 140 bytes of store on OVMF, and the kernel measures the real cost
  on the second write. About 250 to 300 fit in 40 KiB. Readers sort the
  slots by sequence. The kernel deletes every slot when tracing starts,
  and also the single `DBTStep` variable that kernels before the ring
  wrote; readers still accept that variable.
- `DaemonarchyBootTrace` is the full record: newest breadcrumbs plus the
  message-buffer tail. It is written at the first opportunity, when the
  fine-grained region starts, every 64 breadcrumbs while more than half the
  budget is left, and at panic, completion or the budget stop. Two full
  writes are always reserved.

Readers show whichever is newer, and list the ring under "NVRAM
breadcrumb ring".

A ring does not make the store larger. Each `SetVariable` still appends a
copy, and firmware that does not reclaim at runtime still caps a boot at
its free space. Two changes keep the end of the trace near a hang:

- **Runtime re-read.** Every 32 breadcrumbs, and when the budget looks
  spent, the kernel reads `QueryVariableInfo` again. It always accepts a
  lower figure. It accepts a higher one, from firmware that reclaimed at
  runtime, only when the measured breadcrumb cost showed that the query
  follows writes (flag `runtime-reclaim`).
- **Stride.** Once less than a quarter of the budget is left, breadcrumbs
  are persisted for every 2nd step. Each further halving doubles the
  stride, up to every 1024th step (flag `strided`; `debug.boottrace.stride=0`
  restores the hard stop). The last breadcrumb is then within a stride of
  the hang, not at the step where the budget ran out (the first MSI run
  stopped at `acpi_lid0`). Zoom in with `debug.boottrace.from`.

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
| `debug.boottrace.ring` | 16 | breadcrumb ring slots `DBTStep00`.. (1..64) |
| `debug.boottrace.stride` | 1 | 1: persist every 2nd, 4th, ... step when the budget runs low; 0: stop |
| `boottrace_max_repeat` | 2 | trace image loader: stop when one experiment would be staged this many extra times in a row |
| `boottrace_test_drop` | - | **test only**, trace image loader: `fat`, `raw` or `all` writes are acknowledged but not made |
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
  reads `DaemonarchyBootTrace`, the breadcrumb ring and `DBTLoader` and
  writes `DaemonarchyBootTrace-*.txt` and `.bin` to the desktop; `-Clear`
  deletes the trace variables afterwards.
- **Linux:** `tools/boottrace/decode-boottrace.py --efivarfs
  /sys/firmware/efi/efivars/DaemonarchyBootTrace-9262df38-e448-4c99-bdd0-e70eada0faa1`
  also reads the `DBTStep*` and `DBTLoader` files next to it; `--vars`
  decodes a QEMU OVMF vars file and counts stored copies.
- **Wired network loop (optional):** with `boottrace_loop="YES"` and the
  plain `netdebug.*` settings in `loader.conf`, the loader starts the wired
  console, waits `boottrace_controller_wait` seconds for
  `tools/boottrace/boottrace-loop.py`, which reads the trace with
  `boottrace report` and sends the next experiment; otherwise it boots the
  `boottrace_conf` preset. The stick loop (`boottrace_autocycle`) takes
  precedence when both are set. This network path has not been exercised
  yet; the MSI stick image does not enable it.

## Network debugger hand-over

A boot that reaches init can hand the machine over to an ssh session, so the
hardware can be probed in far more detail than the saved diagnostics. The
trace loop is unchanged; the hand-over is an addition at the end of the boot.
It needs a wired network (DHCP) and a public key on the stick; **Secure Boot
stays off** for this image, as before.

What the image does when a boot reaches init (`tools/hwtrace/rc`,
`tools/hwtrace/net.sh`):

1. Saves the diagnostics to `DUMPS/<id>/`, as before.
2. If the stick carries `KEYS/authorized_keys` (and `hwtrace.net=NO` is not set):
   loads the USB-Ethernet drivers, asks every wired interface for an address
   at once (bounded: `hwtrace.dhcp`, default 40 s; the T2's internal USB link,
   Wi-Fi and virtual interfaces are skipped), and starts `sshd` on **port 2222**
   for that key only (root, public-key login, no passwords, no forwarding).
   The host name is `daemonarchy-hwtrace`, so the DHCP server's client list
   shows it.
3. Records the address: `ADDRESS.TXT` on the stick, `DUMPS/<id>/network.txt`
   (interfaces, routes, DHCP and sshd logs) and `DUMPS/<id>/rc.log`.
4. **Holds the boot** for `hwtrace.hold` seconds (default 1800). Over ssh,
   `hwtrace-hold SECONDS` changes the total and `hwtrace-continue` ends the
   hold now. When the hold ends the machine reboots, the loader files the
   complete trace and stops the loop, exactly as without a hand-over. The hold
   is finite, so an unattended stick cannot wedge.
5. If there is no key, no address or sshd does not start, nothing is held: the
   boot reboots as before and `network.txt` says why.

The message on the screen is best effort: in QEMU the userland console output did
not reach the serial line, so read `ADDRESS.TXT` from the stick afterwards, or
find `daemonarchy-hwtrace` in the router's client list.

### Keys and the host key

- The published image carries **no keys**, so it starts no network service.
  Add yours to a stick: `tools/boottrace/stick.py keys STICK-OR-IMAGE
  ~/.ssh/id_ed25519.pub` (`--replace` to replace, otherwise it adds). Only
  public keys are accepted. `build-hwtrace-image.sh -K FILE` does the same at
  build time for a private image.
- The **host key** is made by the first boot that hands over and is kept on the
  stick in `KEYS/ssh_host_ed25519_key`, so its fingerprint is the same on every
  later boot; the fingerprint is printed, and written to `ADDRESS.TXT` and
  `network.txt` (`stick.py network STICK` shows it). `-H` generates it at build
  time instead and writes the fingerprint to `OUT.img.hostkey`, so the
  operator can pin it before the first boot. The key is on the stick
  (private) and is never shared between sticks unless you copy it.
  Tradeoff: anyone who holds the stick holds the host key, so keep the stick
  private and do not publish an image built with `-H`.
- Connect: `ssh -p 2222 -o UserKnownHostsFile=... root@ADDRESS` and compare the
  fingerprint to the one on the stick or from the build.

What is on the image for the session: `/rescue` tools (ls, cat, dmesg, sysctl,
kldstat, kldload, ifconfig, route, ping, dd, gpart, camcontrol, ...) on the
PATH, `pciconf`, `devinfo`, `acpidump`, `usbconfig`, `netstat`, `scp` and
`sftp-server`. Not on it: a package manager, a compiler, DTrace tooling beyond
what the kernel provides, Wi-Fi drivers or firmware (wired only).

### Testing it

`tools/boottrace/qemu-trace-mvp-test.py` drives an image built with `-S` and a
test key (`-K`) through four scenarios under QEMU/OVMF (user networking with a
forwarded port): `handover`, `hang` (the first experiment hangs, the second
hands over), `bounded` (the hold ends on its own) and `nokey` (an image with no
key never opens a port). `tests/hwtrace-net.sh` runs the shell logic against
shimmed commands in CI.

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
