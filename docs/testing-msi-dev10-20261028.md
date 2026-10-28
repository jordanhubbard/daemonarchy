# MSI capture candidate dev10: AT RTC left alone on a UEFI port conflict, October 28

On the MSI Raider 18 HX (Ultra 9 285HX, RTX 5080, BIOS E1824IMS.317), the
dev8 kernel fixed the legacy VGA hang, and the AT RTC driver is now the
next hang. dev10 carries a kernel that records a boot-trace event before
every RTC hardware access. On a UEFI boot it also leaves the RTC alone when
the RTC's I/O ports cannot be allocated. It is a hardware experiment image,
not a qualified 1.4 release. dev9 is reserved for live6.

The [bounded qualification record](../native/hwtrace/dev10/qualification.json)
binds the image, the sources, the queue, the dev8 hardware results and the
retained VM evidence digests.

## dev8 hardware results

dev8 ([record](https://github.com/jordanhubbard/daemonarchy/pull/114)) ran
its queue on the MSI. Its kernel was daemonarchy-src `fix/isavga-skip-uefi`
`24261b7146d`
([#45](https://github.com/jordanhubbard/daemonarchy-src/pull/45)), which
skips the legacy VGA probe on UEFI boots.

| Queue | Experiment | Settings | Result |
|---|---|---|---|
| 0001 | `stock-uefi` | `kern.panic_reboot_wait_time=15` | hung; last step `#1981 2.860s cpu8 attach: attach atrtc0@acpi0 atrtc handle=\_SB_.` |
| 0002 | `stock-uefi-atrtc-off` | `hw.atrtc.enabled=0`, `kern.panic_reboot_wait_time=15` | reached init; `DUMPS/0002` saved |

Experiment 0003 did not run, because the cycle stops at the first boot that
reaches init.

- **VGA.** Experiment 0002 reached init with no VGA hint, so #45 works on the
  hardware. Earlier, every dev5 experiment hung at `probe vga0@isa1`.
- **RTC.** Experiment 0001 hung inside the attach of `atrtc0` on `acpi0`.
  Its trace ends there. The device attached just before it was `hpet0`.
- **The port 0x70 conflict.** In the `DUMPS/0002` devinfo, `acpi0`, through
  its system resources, owns I/O port `0x70` as a single byte. atrtc asks
  for `0x70-0x71`. `acpi_alloc_resource()` cannot satisfy that from its
  parent, because `0x70` already belongs to `acpi0`. It cannot suballocate it
  from the one-byte system-resource region either. The October video showed
  `atrtc0: Warning: Couldn't map I/O.` just before the reset, which matches.
  The stock driver prints that warning and then programs the RTC anyway.
- **The ISA instance.** In the same dmesg the hinted ISA instance fails too:
  `atrtc0 failed to probe at port 0x70 irq 8 on isa1`. With
  `hw.atrtc.enabled=0` its probe is rejected.
- **The clock.** `efirtc0` registers as a time-of-day clock and reports
  `efirtc0: providing initial system time`.

The trace files and the `DUMPS/0002` files were copied off the stick and are
retained privately. The stick itself was not written.

## Kernel change

daemonarchy-src `fix/atrtc-uefi-conflict`, commit `0400aa21dc6`
([PR #46](https://github.com/jordanhubbard/daemonarchy-src/pull/46)), is based on
`fix/isavga-skip-uefi` `24261b7146d` (#45) and changes only
`sys/x86/isa/atrtc.c`.

- **Fix.** On amd64, when `efi_boot` is set and the `0x70-0x71` allocation
  fails, the attach records `atrtc: UEFI port conflict, declining`, prints
  why, and returns `ENXIO` before any port access. This applies to both
  the ACPI and the ISA attach. No ACPI `SystemCMOS` handler is installed,
  and the driver never registers as a clock. `rtcin()`, `writertc()` and
  `atrtc_restore()` then leave the hardware alone, which covers their
  other callers (`nvram(4)`, `fdc(4)`, `acpi_ibm(4)`, legacy `vga`). amd64
  has no early RTC read outside the driver, and efirtc keeps the time.
- **Override.** `hw.atrtc.force_on_conflict=1` restores the stock behaviour:
  it prints the old warning and carries on. Non-UEFI boots and i386 are
  unchanged.
- **Events.** A boot-trace event is recorded before each hardware step:
  - the port allocation and its result;
  - each CMOS index select (`in 0x84, out 0x70`) and data write
    (`out 0x71, in 0x84`) in `atrtc_start()`;
  - `clock_register`, the IRQ 8 allocation, `bus_setup_intr`,
    `bus_bind_intr` and `et_register`;
  - the installation of the ACPI CMOS address-space handler and its result;
  - one event each in gettime and settime.
- **Event delivery.** The register writes in `atrtc_start()` drop the spin
  lock around each event, because a step is persisted only when the thread
  can block. Each event text fits the 39-character breadcrumb.

## Exact inputs

- **Kernel.** GENERIC amd64, built on madmax's FreeBSD builder guest with
  the host toolchain (`config` and `make -j16 kernel`). The guest runs
  16.0-CURRENT `d63d77f4eb3c`.
  - The source was a shallow fetch of commit
    `0400aa21dc6e7e82de292282beac455d4561f1bb` from GitHub, tree
    `ed689179deb51adab28d2e93dd4f1436b4c5ecb8`.
  - The first `make` stopped with a missing generated header,
    `vdso_offsets.h`, in `elf_machdep.c`, which is a parallel-build
    ordering race. Running the same `make` again in the same directory
    finished. Neither log has a warning. `atrtc.o` was compiled in the
    first pass with `-Werror`.
  - Kernel SHA-256:
    `41dc22228ec59dfe7c0449d6ef13b606ac5cddf554087e3e4bae571235866e03`.
- **i386 check.** `sys/x86/isa/atrtc.c` compiles as `atrtc.o` in an i386
  GENERIC kernel directory (`-target i386-unknown-freebsd16.0`, `-Werror`)
  with no warnings. Only that object was built.
- **Loader.** `loader_lua.efi` was built from the same tree
  (`make -C stand`) with no warnings. SHA-256:
  `335cf3cef067ab960a7fcd43cd9deba0158462b3902cc38f177d07ef77a32fb1`.
  The `stand` sources are the same as dev8's.
- **Lua.** `stand/lua` from the same tree, byte-identical to dev8's. Boot
  Trace is on `i`.
- **World pieces.** The 1.4.0-live3 ISO, as in dev7 and dev8, SHA-256
  `bd3c12932bb93ae00cf5db26836532eab1480d69dae412062ee810a2c08e70b0`.
- **Image builder.** `build-hwtrace-image.sh` from product `main`
  `cc4e373`, without `-S` or `-x`. The builder and `tools/` are
  byte-identical to dev8's. The unqueued image SHA-256 was
  `d8f3776d64ff8df687038d645fff7c21bceb4eb2b044d17a56d17458cded88a6`.
- **Candidate.** `daemonarchy-hwtrace-1.4.0-dev10-amd64.img`, 391153152
  bytes, SHA-256
  `0cc3ab9358a975dc5b2209dc4995092a699308bf8eb0782af2c540f47cafedc5` after
  queueing. `stick.py check-map` passes with 201 files. The state is next 1,
  zero traces, empty pending, epoch 396552766.

## Queued experiments

The queue file is
[`tools/boottrace/msi-dev10-queue.txt`](../tools/boottrace/msi-dev10-queue.txt).

| Queue | Experiment | Settings |
|---|---|---|
| 0001 | `atrtc-force` | `hw.atrtc.force_on_conflict=1`, `kern.panic_reboot_wait_time=15` |
| 0002 | `atrtc-force-noclock` | `hw.atrtc.force_on_conflict=1`, `hint.atrtc.0.clock=0`, `kern.panic_reboot_wait_time=15` |
| 0003 | `stock-fix` | `kern.panic_reboot_wait_time=15` |

A hang needs a manual power-off, so the diagnostic experiments come first.
The cycle stops at the first boot that reaches init.

1. **`atrtc-force`** reproduces the dev8 hang with the old behaviour, now with
   an event before every RTC access. Its last breadcrumb names the step that
   hung: a CMOS register access, the IRQ 8 setup or `et_register`.
2. **`atrtc-force-noclock`** also skips the IRQ 8 and event-timer setup. If it
   reaches init, the hang was in the interrupt path and not in the port
   accesses. The cycle then stops before `stock-fix`.
3. **`stock-fix`** is the candidate fix with no knobs. Its trace or dmesg
   should show `atrtc: UEFI port conflict, declining` and
   `efirtc0: providing initial system time`.

If `atrtc-force-noclock` reaches init, `stock-fix` needs its own boot. Queue
it again, or boot it from the loader. No `debug.boottrace.from_sub` setting is
queued. The default, `SI_SUB_CONFIGURE`, already persists every step after
device attach begins. In dev8 the `atrtc0` attach was breadcrumb 35 of a
budget of about 223, and the new events add about 15 more.

## VM evidence

All runs used QEMU on the arm64 host: q35/smm, x86 TCG, Westmere, two
virtual CPUs and 2048 MiB of memory. Each run had a fresh `OVMF_VARS_4M`
copy, and the stick was attached as xHCI `usb-storage`. The harness was
`tools/boottrace/qemu-stick-test.py` with `--silence 400`. Each run used a
separate copy of the image, so the delivered image was not changed. The
`test_hang` knob matches event texts as well as step names, so these runs
stop the boot at a chosen event.

### Reproducing the MSI port claim

In QEMU, atrtc's allocation normally succeeds: `atrtc0` attaches at
`port 0x70-0x77`. To reproduce the MSI's conflict,
[`tools/boottrace/qemu/rtc-0x70-conflict.asl`](../tools/boottrace/qemu/rtc-0x70-conflict.asl)
declares a `PNP0C02` system resource that claims I/O port `0x70` alone. It
was compiled with `iasl` from FreeBSD base, and the compiled `.aml` is next
to it, SHA-256
`5e77ea0a716a1237d0467f528095e0c518f3c3c89fd2a144a65ab1de2f4386da`.

The harness now takes repeatable `--qemu-arg` options for this:

```sh
tools/boottrace/qemu-stick-test.py IMAGE --vars VARS --log LOG --cpu Westmere \
    --qemu-arg=-acpitable --qemu-arg=file=tools/boottrace/qemu/rtc-0x70-conflict.aml
```

With the table loaded, devinfo shows `acpi0` owning I/O port `0x70`, a
single byte, through `acpi_sysresource1` at `\_SB_.RTCC`. This is the same
claim as on the MSI. The stock attach path then prints
`atrtc0: Warning: Couldn't map I/O.`.

### Runs

1. **Exact candidate copy, no conflict.** Boot 1 ran 0001 `atrtc-force`,
   reached init and saved `DUMPS/0001`. Boot 2 filed `TRACES/0001.TXT`
   ("Status: complete: the kernel reached init"), and the loader stopped.
   `atrtc0` attached at `port 0x70-0x77 irq 8 on acpi0`. The final state was
   next 2, one trace, and the map verified.
2. **Requeued copy, no conflict.**
   - `stock-fix` with `test_hang="atrtc: ACPI CMOS handler installed"` filed
     an INCOMPLETE trace. Its NVRAM breadcrumb ring shows the whole attach
     in order:

     ```text
     b27 #1838 attach: attach atrtc0@acpi0 atrtc handle=\_SB_.
     b28 #1839 event: atrtc: atrtc0 alloc ports 0x70-0x71
     b29 #1840 event: atrtc: ports 0x70-0x71 allocated
     b30 #1841 event: atrtc: sel 0x0a: in 0x84,out 0x70
     b31 #1842 event: atrtc: wr 0x0a=0x29: out 0x71,in 0x84
     b32 #1843 event: atrtc: sel 0x0b: in 0x84,out 0x70
     b33 #1844 event: atrtc: wr 0x0b=0x02: out 0x71,in 0x84
     b34 #1845 event: atrtc: start done
     b35 #1846 event: atrtc: clock_register
     b36 #1847 event: atrtc: alloc IRQ 8 (rid 0)
     b37 #1848 event: atrtc: bus_setup_intr IRQ 8
     b38 #1849 event: atrtc: bus_bind_intr IRQ 8 to cpu 0
     b39 #1850 event: atrtc: et_register RTC
     b40 #1851 event: atrtc: attach done
     b41 #1852 event: atrtc: install ACPI CMOS handler
     b42 #1853 event: atrtc: ACPI CMOS handler installed
     ```

   - `stock-fix` then reached init, with `atrtc0` attached normally, and
     the loader stopped.
3. **Requeued copy, with the conflict table.**
   - `stock-fix` with `test_hang="atrtc: UEFI port conflict, declining"`
     filed an INCOMPLETE trace ending
     `attach atrtc0@acpi0`, `atrtc0 alloc ports 0x70-0x71`,
     `ports 0x70-0x71 NOT allocated`, `UEFI port conflict, declining`.
   - `hw.atrtc.force_on_conflict=1` with `test_hang="atrtc: et_register RTC"`
     ended with
     `ports 0x70-0x71 NOT allocated`, `port conflict, forced on`, then the
     four CMOS accesses, `start done`, `clock_register`, the IRQ 8 steps
     and `et_register RTC`.
   - `stock-fix` reached init. Its dmesg shows both instances declining, and
     efirtc keeping the time:

     ```text
     atrtc0: <AT realtime clock> port 0x70-0x77 irq 8 on acpi0
     atrtc0: I/O ports 0x70-0x71 are claimed by another device; not touching the RTC on this UEFI boot (hw.atrtc.force_on_conflict=1 overrides)
     device_attach: atrtc0 attach returned 6
     atrtc0: <AT realtime clock> at port 0x70 irq 8 on isa0
     atrtc0: I/O ports 0x70-0x71 are claimed by another device; not touching the RTC on this UEFI boot (hw.atrtc.force_on_conflict=1 overrides)
     device_attach: atrtc0 attach returned 6
     efirtc0: providing initial system time
     ```

4. **Requeued copy, with the conflict table, `atrtc-force` only.** It reached
   init and printed `atrtc0: Warning: Couldn't map I/O.`, as the MSI did in
   October. QEMU emulates the RTC behind the unallocated ports, so the old
   path does not hang there. The conflict alone does not cause the MSI hang;
   something in the hardware access after it does.

QEMU's usb-storage reported retried `READ(10)`/`WRITE(10)` CAM errors in
every run, as in dev4, dev7 and dev8. The DUMPS and traces were still
written.

## dev10 hardware results

The operator ran the dev10 stick on the MSI on 2026-10-28. All three
experiments were filed through raw blocks (SLOTS.MAP), with read-back ok.

| Queue | Experiment | Result | Last step |
|---|---|---|---|
| 0001 | `atrtc-force` | hang | `#1986 0.822s cpu8 event: atrtc: sel 0x0a: in 0x84,out 0x70` |
| 0002 | `atrtc-force-noclock` | hang | `#1986 0.851s cpu8 event: atrtc: sel 0x0a: in 0x84,out 0x70` |
| 0003 | `stock-fix` | reached init | `#12841 12.316s cpu0 complete: boot complete: root mounted, executing init` |

Before the hang, both forced runs logged `alloc ports 0x70-0x71`,
`ports 0x70-0x71 NOT allocated` and `port conflict, forced on`. The last
event is recorded before the first CMOS register select in `atrtc_start`,
the delay read of port `0x84` and the index write to `0x70`. That access
hangs the machine, with or without the IRQ 8 event timer
(`hint.atrtc.0.clock=0`). So the legacy CMOS port access is the cause, not
the RTC interrupt.

`stock-fix` declined the RTC on the port conflict. `efirtc0` provided the
time, and the boot reached init with stock settings and no VGA or RTC hint.
Together with src#45, this is the first MSI boot of the Daemonarchy kernel
to init without hints. The trace SHA-256 values are:

- `0001.TXT` `020e6dd5465963ce604f74a685182d99804d9d17c2969f02fc313a39f888e391`
- `0002.TXT` `03d4e9a2fd88d90b249d2b1adaec6b10bc0ecc366e8bf03a10b649c5bd2918ac`
- `0003.TXT` `50a7c1945b4eb5a8586a5f5782ecd1e983cbab62db26ed2337c3f2e1471105cf`

## Readiness and limits

The queued, never-booted candidate and its `.sha256` are in the private image
directory, and the hash was re-verified there. The kernel, loader, build
logs, serial logs, vars files, traces and DUMPS are retained privately. No
USB device was written, and the image is not signed.

The MSI hardware results are above. They cover kernel startup to init on
the hwtrace image only, not the installer, the desktop, the NVIDIA driver or
an installed system. This record does not claim a native profile, a
lifecycle receipt or release qualification.
