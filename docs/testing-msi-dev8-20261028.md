# MSI capture candidate dev8: no legacy VGA probe on UEFI boots, October 28

On the MSI Raider 18 HX (Ultra 9 285HX, RTX 5080, BIOS E1824IMS.317), dev7
experiment 1 `vga-disabled` (`hint.vga.0.disabled=1`, `hw.atrtc.enabled=0`)
reached init. Before that, every dev5 experiment hung at `probe vga0@isa1`.
The MSI's FADT `IAPC_BOOT_ARCH` is only `{8042,NO_ASPM}`. It does not set
"VGA Not Present", so the FADT path of
[daemonarchy-src #42](https://github.com/jordanhubbard/daemonarchy-src/pull/42)
never applies there, and a stock boot still probes vga0.

dev8 carries a kernel that leaves legacy VGA out of every amd64 UEFI boot.
It is a hardware experiment image, not a qualified 1.4 release. The
experiment that matters is `stock-uefi`: no hint and no other knob.

The [bounded qualification record](../native/hwtrace/dev8/qualification.json)
binds the image, the sources, the queue and the retained VM evidence digests.

## Kernel change

daemonarchy-src `fix/isavga-skip-uefi`, commit `24261b7146d`
([PR #45](https://github.com/jordanhubbard/daemonarchy-src/pull/45)), changes
`isavga_skip()` in `sys/isa/vga_isa.c`:

- On amd64, when `efi_boot` is set, vga0 is not added at identify time and
  the boot trace records the event `isavga: UEFI boot, not probing legacy VGA`.
- `hw.vga.efi_probe=1` restores the probe, for example for `kern.vty=sc`.
- `hint.vga.0.disabled` is still checked first. The FADT check from #42
  still applies to BIOS boots and to i386.

A UEFI boot returns before the FADT is read, so dev8 traces no longer record
the FADT boot flags. The MSI's flags are already known from its ACPI dump.

## Exact inputs

- Kernel: GENERIC amd64, built on madmax's FreeBSD builder guest with the
  host toolchain (`config` and `make -j16 kernel`). The guest runs
  16.0-CURRENT `d63d77f4eb3c`. The source was a shallow fetch of commit
  `24261b7146d7f4091b2e48eefbef0debad606f01` from GitHub, tree
  `96a4223c9ea288e7776a123126fdaf85b9912fe6`. Its parent is `daemonarchy`
  `bac4c23caca`, which already includes src #42 and #44, so no local merge
  was needed. It built with no errors or warnings. Kernel SHA-256:
  `9a4f3f379b02bc180c0f7b174ba8ce95a9c78b5429dc8d4f8cde34f29667fa6f`.
- i386 check: `sys/isa/vga_isa.c` compiles as `vga_isa.o` in an i386
  GENERIC kernel directory (`-target i386-unknown-freebsd16.0`, `-Werror`)
  with no warnings. Only that object was built.
- Loader: `loader_lua.efi` built from the same tree (`make -C stand`), SHA-256
  `dc6d7f71d5fd42c1b3783b7e2c6413b2b4985f3652fdc72e2c675fd2718e48f5`.
- Lua: `stand/lua` from the same tree. `splash.lua`, `netdebug.lua` and
  `menu.lua` are byte-identical to dev7's. Boot Trace is on `i`.
- World pieces: the 1.4.0-live3 ISO, as in dev7, SHA-256
  `bd3c12932bb93ae00cf5db26836532eab1480d69dae412062ee810a2c08e70b0`.
  The image loads no modules beyond `msdosfs`, and GENERIC already includes it.
- Image builder: `build-hwtrace-image.sh` from product `main` `cc4e373`,
  without `-S` or `-x`. The builder and `tools/boottrace` are identical to
  the files dev7 used. The unqueued image SHA-256 was
  `faa04e40270d00dc47ed4fde41fc0ab8be6d2a9ccfd7ec138f4696c2ef295e0e`.
- Candidate: `daemonarchy-hwtrace-1.4.0-dev8-amd64.img`, 391153152 bytes,
  SHA-256 `5d4413fff991c6ccd1e22c823e6e9c6c3067539ab41b73c0125545c99022a3dc`
  after queueing. `stick.py check-map` passes with 201 files. The state is
  next 1, zero traces, empty pending, epoch 1810113917.

## Queued experiments

| Queue | Experiment | Settings |
|---|---|---|
| 0001 | `stock-uefi` | `kern.panic_reboot_wait_time=15` |
| 0002 | `stock-uefi-atrtc-off` | `hw.atrtc.enabled=0`, `kern.panic_reboot_wait_time=15` |
| 0003 | `vga-hint-atrtc-on` | `hint.vga.0.disabled=1`, `kern.panic_reboot_wait_time=15` |

The cycle stops at the first experiment that reaches init. If `stock-uefi`
reaches init on the MSI, the later experiments do not run, and that is the
result wanted. If it hangs, `stock-uefi-atrtc-off` tests whether `atrtc0` is
the next hang, and `vga-hint-atrtc-on` repeats the dev7 path with the RTC on.

## VM evidence

All runs used QEMU on the arm64 host: q35/smm, x86 TCG, Westmere, two
virtual CPUs and 2048 MiB of memory. Each run had a fresh `OVMF_VARS_4M`
copy, and the stick was attached as xHCI `usb-storage`. The harness was
`tools/boottrace/qemu-stick-test.py`. Each run used a separate copy of the
queued image, so the delivered image was not changed.

1. **Exact candidate copy** (`--silence 1200`). Boot 1 ran experiment 0001
   `stock-uefi`, reached init and saved `DUMPS/0001`, and the rescue root
   rebooted. Boot 2 filed `TRACES/0001.TXT` through raw blocks (read-back
   ok), with "Status: complete: the kernel reached init". The loader then
   stopped. The dmesg in `DUMPS/0001` shows `sc0` failing to probe and
   `attimer0` attaching on isa0, and no vga0 at all. The kenv carries no
   `hint.vga` or `hw.vga` setting. Afterwards the map still verifies and the
   state is next 2, one trace.
2. **ISA hang runs.** A finished boot keeps only the newest steps, so the
   `isavga:` event leaves the window. Another copy of the candidate was
   requeued with two experiments that set
   `debug.boottrace.test_hang=attimer0`. Each one hung right after ISA
   probing and filed an INCOMPLETE trace whose recent steps show the event:

   ```text
   # stock-uefi-hang-attimer0
   #3561 13.335s cpu1 event: isavga: UEFI boot, not probing legacy VGA
   #3562 13.900s cpu1 probe: probe sc0@isa0 sc
   #3563 13.921s cpu1 probe: probe attimer0@isa0 attimer

   # vga-hint-hang-attimer0 (hint.vga.0.disabled=1)
   #3561 13.316s cpu1 event: isavga: hint.vga.0.disabled, not probing
   #3562 13.876s cpu1 probe: probe sc0@isa0 sc
   #3563 13.899s cpu1 probe: probe attimer0@isa0 attimer
   ```

   The NVRAM breadcrumb ring holds the same steps.

QEMU's usb-storage reported retried `READ(10)`/`WRITE(10)` CAM errors in
every run, as in dev4 and dev7. The DUMPS and traces were still written.
In QEMU `atrtc0` attaches on acpi0, so these runs do not exercise the MSI's
RTC question.

## Readiness and limits

The candidate image and its `.sha256` are in the private image directory.
The kernel, loader, build logs, serial logs, vars files, traces and DUMPS
excerpts are retained privately. No USB device was written, and the image
is not signed.

The MSI result is still pending. If the reset was only the legacy VGA probe,
`stock-uefi` should reach init with no knobs. If it hangs, its trace should
show the `isavga: UEFI boot` event followed by the next hang.
This record is VM evidence only. It does not claim a native profile, a
lifecycle receipt or release qualification.
