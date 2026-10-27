# Hardware trace stick: QEMU/OVMF checks, October 27

These checks cover the [hardware trace stick](boottrace.md) loop under
virtualization only. No MSI or other physical firmware result exists yet.

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

## Not covered

Physical firmware (AMI NVRAM behaviour, runtime write cost, FAT driver
binding of the `DATRACE` partition), bhyve, Secure Boot, and the optional
wired-console loop.
