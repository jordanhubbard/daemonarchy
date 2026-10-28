# MSI capture candidate dev7: legacy VGA probe skip, October 28

All four dev5 experiments on the MSI Raider 18 HX (Ultra 9 285HX, RTX 5080,
BIOS E1824IMS.317) reset about 9 s after the boot trace step
`probe vga0@isa1`. That happened even with every ISA hint removed and with
`hint.isa.0.disabled=1`. `isavga_identify` adds vga0 to every ISA bus, and
its probe touches the legacy VGA ports and memory. A disabled hint is only
checked at attach, after the probe has run. Earlier runs also hung on
`atrtc0` (port 0x70) unless `hw.atrtc.enabled=0` was set.

dev7 carries a kernel that leaves vga0 out at identify time. It is a
hardware experiment image, not a qualified 1.4 release. dev6 was never
built; this is the next image after dev5.

The [bounded qualification record](../native/hwtrace/dev7/qualification.json)
binds the image, the sources, the queue and the retained VM evidence digests.

## Kernel change

daemonarchy-src `fix/isavga-legacy-skip`, commit `499dab77fe9`
([PR #42](https://github.com/jordanhubbard/daemonarchy-src/pull/42)),
changes `sys/isa/vga_isa.c`:

- vga0 is skipped when `hint.vga.0.disabled` is set.
- vga0 is skipped when the FADT IA-PC boot flags set `ACPI_FADT_NO_VGA`,
  unless `hw.vga.acpi_ignore_no_vga=1`.
- The boot trace records `isavga: hint.vga.0.disabled, not probing` or
  `isavga: FADT boot flags 0x....` as an event step.

## Exact inputs

- Kernel: GENERIC amd64, built on the FreeBSD builder with the host
  toolchain (`config` and `make -j3 kernel`, niced beside a running live5
  buildworld). The source was a local merge of `daemonarchy` `b582921ee92`
  (src #38 to #41) with `fix/isavga-legacy-skip` `499dab77fe9`. The merge
  was clean, and the merged tree is `2c55e25960907f8d519e69c8faf083421dc07270`.
  It built with no errors or warnings. Kernel SHA-256:
  `90543cb5310c7f50ecf0303569156bcc9e366cec58b4aff155ad2e458e1d1a50`.
- Loader: `loader_lua.efi` built from the same tree (raw-block stick writes).
  SHA-256 `048a1f092cc6f4909bd12a95b6dfc431defb25f796b21cfd8bb3af3c6e5ab678`.
- Lua: `stand/lua` from the same tree. `splash.lua`, `netdebug.lua` and
  `menu.lua` are byte-identical to dev5's repaired files. Boot Trace is on
  `i`.
- World pieces: the 1.4.0-live3 ISO, SHA-256
  `bd3c12932bb93ae00cf5db26836532eab1480d69dae412062ee810a2c08e70b0`.
  This kernel's base is newer than live3's `d63d77f4e`, but the kernel
  changes in between are only Daemonarchy additions (boot trace, earlynet,
  netconsole, nvme, vtnet, mbuf). The image loads no modules beyond
  `msdosfs`, and GENERIC already includes it.
- Image builder: `build-hwtrace-image.sh` from product `main` `2066e62`,
  without `-S` or `-x`. The unqueued image SHA-256 was
  `6b7f54c12ee1cca9e529c3dc103f37ef55e2cd1a6317e94d2857c1ce22a7e42e`.
- Candidate: `daemonarchy-hwtrace-1.4.0-dev7-amd64.img`, 391153152 bytes,
  SHA-256 `8a703f99ab4919bd1c3117ee1f6c8b68ee544175a29db8debcb271bbbd64cd6e`
  after queueing. `stick.py check-map` passes with 201 files. The state is
  next 1, zero traces, empty pending, epoch 1763775401. `/boot/d/1` is on
  HWTROOT: the build installs the presets, and the preset text is in the
  image.

## Queued experiments

| Queue | Experiment | Settings |
|---|---|---|
| 0001 | `vga-disabled` | `hint.vga.0.disabled=1`, `hw.atrtc.enabled=0`, `kern.panic_reboot_wait_time=15` |
| 0002 | `vga-disabled-legacy-off` | `read-conf /boot/d/1`; unset the `.at` hints of `sc`, `atkbdc`, `atkbd`, `psm`, `atrtc`, `attimer`, `uart.0`, `uart.1` and `ppc`; then the 0001 settings |
| 0003 | `fadt-only` | `hw.atrtc.enabled=0`, `kern.panic_reboot_wait_time=15` (no VGA hint) |
| 0004 | `vga-disabled-one-cpu` | as 0001 plus `kern.smp.disabled=1` |

`fadt-only` tests whether the MSI's FADT sets "VGA Not Present". Its trace
records the boot flags either way.

## VM evidence

All runs used QEMU on the arm64 host: q35/smm, x86 TCG, Westmere, two
virtual CPUs and 2048 MiB of memory. Each run had a fresh `OVMF_VARS_4M`
copy, and the stick was attached as xHCI `usb-storage`. The harness was
`tools/boottrace/qemu-stick-test.py`. Each run used a separate copy of an
image, so the delivered image was not changed.

1. **Exact candidate copy** (no serial console, `--silence 1200`). Boot 1
   ran experiment 0001 `vga-disabled`, reached init and saved `DUMPS/0001`,
   and the rescue root rebooted. Boot 2 filed `TRACES/0001.TXT` through raw
   blocks (read-back ok), with "Status: complete: the kernel reached init".
   The loader then stopped. The dmesg in `DUMPS/0001` shows `sc0`,
   `atrtc0` and `attimer0` on isa0 and no vga0 at all. The kenv carries
   `hint.vga.0.disabled="1"`. Afterwards the map still verifies and the
   state is next 2, one trace.
2. **Serial test image, same queue.** This copy was built with `-S` and the
   same kernel, loader and Lua. The result matched run 1. The kernel passed
   ISA probing and reached init, and vga0 was not probed.
3. **Serial test image, `fadt-only` first.** vga0 was probed and failed
   ("vga0 failed to probe on isa0"), and the boot reached init. QEMU's FADT
   `IAPC_BOOT_ARCH` is `{8042}`, so the probe is expected here.
4. **ISA hang runs.** A finished boot keeps only the newest steps, so the
   `isavga:` event leaves the window. Two serial test experiments therefore
   set `debug.boottrace.test_hang=attimer0`. Each one hung right after ISA
   probing and filed an INCOMPLETE trace whose recent steps show the new
   event:

   ```text
   # vga-disabled-hang-attimer0
   #3565 13.118s cpu0 event: isavga: hint.vga.0.disabled, not probing
   #3566 13.638s cpu0 probe: probe sc0@isa0 sc
   #3567 13.699s cpu0 probe: probe atrtc0@isa0 atrtc
   #3568 13.713s cpu0 probe: probe attimer0@isa0 attimer

   # fadt-only-hang-attimer0
   #3565 13.022s cpu0 event: isavga: FADT boot flags 0x0002
   #3566 13.539s cpu0 probe: probe sc0@isa0 sc
   #3567 13.602s cpu0 probe: probe vga0@isa0 vga
   #3568 13.615s cpu0 probe: probe atrtc0@isa0 atrtc
   #3569 13.627s cpu0 probe: probe attimer0@isa0 attimer
   ```

   The NVRAM breadcrumb ring holds the same steps. The ring's text field
   truncates the first event to `not probin`.

QEMU's usb-storage reported retried `READ(10)`/`WRITE(10)` CAM errors in
every run. The same errors appear in the dev4 raw-block VM logs, and the
DUMPS and traces were still written.

## Readiness and limits

The candidate image and its `.sha256` are in the private image directory.
The kernel, loader, serial logs, vars files, traces and DUMPS excerpts are
retained privately. No USB device was written, and the image is not signed.

The MSI result is still pending. If the reset follows the VGA probe, the
`vga-disabled` experiments should pass `vga0`. The next hang, if any, then
shows in their traces. `fadt-only` reports what the MSI firmware declares.
This record is VM evidence only. It does not claim a native profile, a
lifecycle receipt or release qualification.
