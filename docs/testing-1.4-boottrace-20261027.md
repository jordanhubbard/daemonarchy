# Hardware trace stick: QEMU/OVMF checks and first MSI run, October 27

These checks cover the [hardware trace stick](boottrace.md) loop: runs 1
to 5 under QEMU/OVMF, then the first physical run on the MSI Raider.

## Artifacts

- Source: daemonarchy-src `feat/boottrace` (PR #35) on `fd259a1787ab`.
  The shipped kernel is GENERIC from the 1.4.0-live3 release base
  `d63d77f4eb3c` with the same patch applied (run 1 used an earlier branch
  kernel). That keeps it identical to the
  failing MSI kernel apart from boottrace, and its modules match the ISO's
  `/boot/kernel`. The loader (`loader_lua.efi`) was built from the branch.
- Delivered MSI image: `daemonarchy-1.4.0-live3-hwtrace-amd64.img`, sha256
  `d7a02e888fed39319ed55b4bab32c73fe1ff60e964c45b36ac36607b13e32041`.
- Stick: the 1.4.0-live3 ISO with the `/boot/d` presets, remastered by
  `tools/boottrace/make-stick.sh`. The test images add a serial console
  (`boot_serial`) for the harness. The MSI image does not.
- Host: QEMU 8.2.2 (TCG), OVMF `OVMF_CODE_4M.fd` and a fresh
  `OVMF_VARS_4M.fd` copy per run. The stick is attached as a USB disk on
  xHCI.
- Harness: `tools/boottrace/qemu-stick-test.py`.
  - A boot that stays silent for 150 s is reset, as the MSI firmware does after a hang.
  - A boot that reaches `login:` is reset, like an operator rebooting.
  - A triple fault resets by itself.

## Run 1: hang, reset, tracing off, normal boot

Queue: `hang-configure` (`/boot/d/1` + `test_hang=configure_first`),
`reset-hpet0` (`test_hang=hpet0`, `test_reset=1`), `trace-off`
(`debug.boottrace=0`), `normal`.

| Boot | Behaviour | Filed trace |
| --- | --- | --- |
| 1 | spin with interrupts disabled at `configure_first`; reset after silence | `0001.TXT` INCOMPLETE, last step `#1680 sysinit: configure_first [sub 0x3800000 order 0x0]` |
| 2 | triple fault at the hinted `hpet0` probe; QEMU reset | `0002.TXT` INCOMPLETE, last step `#1718 probe: probe hpet0 on acpi0 drv hpet` |
| 3 | tracing off; reached login | `0003.TXT` "no trace": nothing was written |
| 4 | normal; reached login | `0004.TXT` complete, `#3942 boot complete: root mounted, executing init` |
| 5 | loader: **HARDWARE TRACE: STOPPED**, "Experiment 0004 reached init" | — |

`stick.py status` afterwards: `next experiment: 0005 of 4; traces filed: 4`.
`decode-boottrace.py --vars` found no live variable (each cycle clears it)
and 78 stale copies in the store.

The loader's on-screen summary for boot 1 showed the last step, the five
newest SYSINITs and the last eight message lines. The coarse normal boot
used its whole 175 KiB budget at step 3145 of 3942 (before the message tail was made to shrink more slowly). It then wrote the reserved
completion record, which was 58 writes in all. Free NVRAM fell from 239 KiB
to 179 KiB across the run because OVMF does not reclaim at runtime. The
loader therefore now compacts the store at boot-services time after a boot
that ran low (run 2).

## Run 2: fine-grained budget, compaction, panic

The first compaction filled the whole store with scratch writes. Boot-time
`QueryVariableInfo` ignores stale copies, so the store reclaimed early and
then refilled with scratch garbage: the next boot saw only 35 KiB and
traced nothing. The record now carries the NVRAM written so far
(`nv_used_kb`), and the loader writes just past the runtime free estimate.
A kernel that finds too little space still leaves one minimal record. The
rerun used the final artifacts.

Queue: `fine-budget-then-hang` (`debug.boottrace.from=1`,
`test_hang=kick_init`), `panic-at-hpet0` (`test_reset=2`),
`hang-configure`, `normal`.

| Boot | NVRAM free at start | Filed trace |
| --- | --- | --- |
| 1 | 239 KiB | `0001.TXT` INCOMPLETE; every step persisted until the budget ran out at step 1293 (169 KiB written, flags `budget-exhausted,fine-window`) |
| 2 | 212 KiB, after compaction (6 scratch writes) | `0002.TXT` **PANIC**, last step `#1719 panic: boottrace: TEST panic at hpet0`; the kernel rebooted itself after 15 s |
| 3 | 165 KiB | `0003.TXT` INCOMPLETE, last step `#1680 sysinit: configure_first` |
| 4 | 196 KiB, after compaction (12 scratch writes) | `0004.TXT` complete, `#3942` |
| 5 | — | STOPPED: "Experiment 0004 reached init" |

At the end the vars file held no live trace variable and no stale copies.

## Run 3: the delivered MSI image

The delivered image was copied and booted unchanged with its MSI queue.
Its first experiment (`legacy-off`, `/boot/d/1`) reached init under QEMU.
The coarse trace used 171 of 175 KiB, and the reserved write recorded
completion at step 3933. The next boot filed `TRACES/0001.TXT` (complete),
compacted NVRAM and stopped with "Experiment 0001 reached init".
`STATE.TXT` read `next=2`, and the other four queue entries stay for the
MSI.

## First physical run: MSI Raider 18 HX AI, AMI E1824IMS.317

This is the first real-hardware evidence. The interim stick
(`daemonarchy-1.4.0-live3-hwtrace-amd64.img`) ran all five queued
experiments unattended on the MSI, with USB first in the boot order:

- The kernel's NVRAM writes worked.
- The loader filed `TRACES/0001`..`0005` on `DATRACE` through the AMI
  firmware's FAT driver.
- The queue advanced and `STATE.TXT` ended at `next=6`.

Every trace was unusable for the same reason. The store reported only
**55 KiB free** at the start of every boot, below the then 64 KiB reserve.
Each boot therefore left one minimal record at step 1198
(`module_register_init`, `SI_SUB_DRIVERS`), long before the hang that
follows ISA probing (`sc0 failed to probe on isa1`, at the end of
`SI_SUB_CONFIGURE`).

That build only printed the compaction outcome on screen, so whether
compaction ran on the AMI firmware is unknown. The constant 55 KiB is
consistent with a store that is mostly valid data rather than garbage.

## Run 4: a crowded store (52 KiB free)

The fix gives every step a 64-byte breadcrumb (`DBTStep`). Full records are
kept for checkpoints, panic and completion. The reserve is now a quarter of
the maximum variable size (8 to 16 KiB), and fine tracing starts at
`SI_SUB_CONFIGURE`. To reproduce the MSI's situation, the OVMF store was
filled with 187 KiB of test-only variables, leaving 52 KiB free.

- **Hang injected at `initclocks` (`SI_SUB_CLOCKS`):** reported as the last
  step from breadcrumb #192, about 140 bytes per breadcrumb; with the 8 KiB
  reserve, 188 breadcrumbs and 31 KiB written.
- **Normal boot:** completed with 270 breadcrumbs. Per-device probes were
  dropped at 60% of the budget (flag `thinned`).
- **Compaction made things worse.** Loader compaction, sized from the
  record, left 27 KiB free for the next boot, against 52 KiB without it.
  It is now opt-in (`boottrace_compact`). Without it, OVMF reclaimed by
  itself: the following boot started with 56 KiB free.

## Run 5: the dedicated hardware trace image

The image was `daemonarchy-hwtrace-1.4.0-dev2-amd64.img`, built by
`build-hwtrace-image.sh` (391 MB) with `-S` for a serial console. It was
attached as SATA, because QEMU's USB storage emulation failed the rescue
root's writes, and the store was again filled to 52 KiB free.

- **Experiment 0001 (hang at `initclocks`):** filed INCOMPLETE with that
  last step.
- **Experiment 0002:** reached init. The rescue root saved `dmesg`,
  `sysctl -a`, `kenv`, `kldstat`, `pciconf`, `devinfo` and `acpidump`
  output to `DUMPS/0002/`.
- **Next boot:** the loader stopped with "Experiment 0002 reached init".
  `fsck.fat` found `DATRACE` clean.

An earlier run of the same image without in-place writes left `DATRACE`
with cross-linked clusters. OVMF's FAT driver had not written its FAT
updates before the kernel started, so the kernel's DUMPS/ writes reused
clusters the loader had just allocated. The loader now rewrites
preallocated files in place.

The delivered MSI image is the non-serial build of the same artifacts,
queued with `tools/boottrace/msi-queue-2.txt`: sha256
`35113148851413424810bbb1ea9618d79c184683c160511b3ef9f2a43c5f6def`.

## Not covered

A physical trace that reaches the MSI's real failure point; the AMI firmware's
reclaim behaviour and runtime write cost; the dedicated image on physical
USB; bhyve; Secure Boot; and the optional wired-console loop.
