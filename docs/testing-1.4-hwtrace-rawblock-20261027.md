# Hardware trace stick: raw-block writes, self-report and ring, October 27

These QEMU/OVMF checks cover the changes made after the dev2 image failed
on the MSI Raider. The machine cycled, but the stick came back
byte-identical (see [How the loader writes the stick](boottrace.md#how-the-loader-writes-the-stick)).
They are VM evidence only. Whether the AMI firmware's `EFI_BLOCK_IO` path
persists where its FAT driver did not still has to be shown on the MSI
with the dev4 image.

## Artifacts

- Source: daemonarchy-src `feat/boottrace-rawblock`, based on `daemonarchy`
  `f4d86dc786e`. The loader (`loader_lua.efi`) and Lua were built from the
  branch. The kernel is GENERIC from the 1.4.0-live3 release base
  `d63d77f4eb3c` with the boottrace files from the branch applied, as for
  dev2, so its modules match the live3 ISO. Both were built on the FreeBSD
  builder.
- Test images: `build-hwtrace-image.sh -S`, plus `-x` with
  `boottrace_test_drop="fat"` or `"all"` for the failure runs.
- Delivered image: `daemonarchy-hwtrace-1.4.0-dev4-amd64.img`, queued with
  the four MSI experiments (`no-isa-hints`, `no-isa-bus`,
  `no-isa-hints-one-cpu`, `rtc-vga-only`). Its sha256 is in the `.sha256`
  file next to it. It was not booted under QEMU, because it has no serial
  console; the test images carry the same kernel and loader.
- Host: arm64 Linux, `qemu-system-x86_64 -machine q35,smm=on -accel
  tcg,thread=multi -cpu Westmere`, `OVMF_CODE_4M.fd` with a fresh
  `OVMF_VARS_4M.fd` copy per run, and the stick as `usb-storage` on
  `qemu-xhci`. The harness was `tools/boottrace/qemu-stick-test.py --cpu
  Westmere --silence 150`.

## Run A: normal path, raw writes

Queue: `hang-hpet0` (`test_hang=hpet0`), `reset-atrtc0` (triple fault),
`normal`. Every cycle printed:

```text
Hardware trace: cycle N; stick writes via raw blocks (SLOTS.MAP) (201 mapped files, read-back via the whole disk)
Hardware trace: saved \TRACES\000N.TXT via raw blocks (SLOTS.MAP) (read-back ok)
Hardware trace: running experiment 000N (...); STATE.TXT via raw blocks (SLOTS.MAP), read-back ok
```

The run took four boots. It filed `TRACES/0001` (last step `probe hpet0`),
`0002` (`probe atrtc0`) and `0003` (complete, step 3942). The rescue root
wrote `DUMPS/0003/`, and the loader stopped with "Experiment 0003 reached
init". On the host, `stick.py check-map` still passed and `stick.py
traces` read all three traces through mtools. Each trace carries the
16-entry breadcrumb ring and the `loader previous`/`loader now` lines.

## Run B: FAT-driver writes dropped, block map present

The image was built with `boottrace_test_drop="fat"`. The loop behaved
exactly as in run A (`hang-hpet0`, then `normal` to init and `DUMPS/0002`).
Every write went through the block map, so losing the FAT driver's writes
changed nothing.

## Run C: the MSI failure on an old-style stick

The run B image with `SLOTS.MAP` deleted falls back to the FAT driver,
with its writes dropped. The first boot "wrote" `STATE.TXT` (`read-back
skipped (test drop)`) and ran experiment 0001, which hung at `hpet0`. The
second boot stopped:

```text
=========== HARDWARE TRACE: STOPPED ===========
STICK WRITES ARE NOT PERSISTING.
Cycle 1 wrote STATE.TXT next=2 traces=0 pending=0001 via firmware FAT driver (read-back skipped (test drop)),
but the stick still reads next=1 traces=0 pending=-.
The kernel trace of experiment 0001 stays in NVRAM ...
```

The loader did not loop on experiment 0001, as the dev2 loader would have.

## Run D: every write dropped, block map present

The image was built with `boottrace_test_drop="all"`. The second boot
stopped with the same message, naming the raw path. The stick was
unchanged (`next=1`, no traces). `decode-boottrace.py --vars` on the vars
file showed the kernel trace (last step `probe hpet0`, ring of 16) and the
`DBTLoader` record (`reached 'stopped'`, flags `NOT-PERSISTING,block-map`).
A third boot stopped again with the same reason; the verdict persists.

## Run E: crowded store, hang at mountroot

The vars file was filled to 52 KiB free (as in the earlier run 4), with
`test_hang=vfs_mountroot` and a budget of about 234 breadcrumbs. The first
build of this change reached a stride of 4 and then stopped at step 3757
(`vnet_register_sysinit`), because the two reserved full records used up
the stride levels. After the stride was measured above that floor, the
kernel printed:

```text
boottrace: NVRAM budget low at step 3610; persisting every 2nd step
boottrace: NVRAM budget low at step 3682; persisting every 4th step
boottrace: NVRAM budget low at step 3754; persisting every 8th step
boottrace: TEST hang with interrupts disabled at vfs_mountroot
```

The filed ring ends `b235 #3920 ... event: vfs_mountroot`: the trace ends
at the hang. With the old hard stop, it would have ended about 300 steps
earlier.

## Host checks

- `python3 tests/boottrace-tools.py` (18 tests) covers:
  - the block map on a real FAT32 GPT image: its offsets match what
    mtools reads, `queue` rewrites in place, a corrupt map is rejected and
    rewritten, and a fragmented file is refused
  - map parser rejections
  - ring decoding from a vars store and from efivarfs siblings
  - the old single `DBTStep`
  - the `DBTLoader` report
  - old and new trace summaries
  - the Windows reader's ring output under `pwsh`
- `sh tools/daemonarchy/tests/run-boottrace-blockmap.sh SRC OBJ` in
  daemonarchy-src runs under ASan and UBSan. It covers map parsing and
  rejection, partition checks, raw rewrites with 512- and 4096-byte
  blocks (read-modify-write), a partition whose writes reach only a cache
  (read-back MISMATCH), test drop and a media change.

## Not covered

- Real AMI firmware: the raw path, the `FlushBlocks` behaviour, and
  whether the USB stick's own cache survives a hard reset. If raw writes
  also fail to persist on the MSI, run D's stop is the expected outcome.
- Firmware that reclaims NVRAM at runtime (`runtime-reclaim`). OVMF does
  not.
- The Windows reader against real firmware variables. Only its formatter
  ran under `pwsh`.
