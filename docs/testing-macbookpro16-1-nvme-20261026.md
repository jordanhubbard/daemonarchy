# MacBookPro16,1 Apple T2 NVMe fatal status, October 26

This record covers the HW-002 storage fault that stopped every install on the
Intel MacBookPro16,1 test machine. The internal SSD is `nvme0: Apple ANS2 NVMe
Controller (T2)`, PCI `106b:2005`, with `nda0` "APPLE SSD AP1024N" (NVMe 1.1,
4096-byte sectors). The fault is now understood and fixed in the driver. The
fix is in [daemonarchy-src PR 34](https://github.com/jordanhubbard/daemonarchy-src/pull/34).
A fresh-image installation with a kernel that contains the fix is still needed
before HW-002 can close.

## Summary

- **Symptom:** under concurrent writes, the controller sets CSTS.CFS
  (controller fatal status). CSTS.RDY then never clears after `CC.EN` is
  dropped, so the driver logs `Resetting controller due to a timeout and fatal
  error status` and then `Waiting for reset to complete` forever. The root
  file system stops, and about a minute later the firmware resets the machine.
- **Not a 1.3.1 regression:** a GENERIC kernel built from the 1.1.1 source
  (`83f5b5c2`) fails in exactly the same way. The October 22 install on 1.1.1
  was recovered only by limiting the driver to four trackers (see the
  [installer record](testing-macbookpro16-1-installer-20261022.md)). That
  reduced how often the fault occurred but did not remove it.
- **Root cause:** the driver rang the completion queue head doorbell once per
  batch, after running every completion in the batch. Running a completion
  frees its command ID, which another CPU can resubmit before the controller has
  been told that the old completion entry was consumed. The ANS2 indexes its
  internal state by command ID, in one table shared by the admin and I/O
  queues, and faults when this happens. It also faults immediately if the
  doorbell is rewritten with the value it already holds.
- **Fix:** for this controller only, the driver acknowledges each completion
  through the doorbell before running it, and skips the batched write when
  that write would repeat the same value.

## Machine and kernels

The machine runs the incomplete Daemonarchy 1.3.1 installation: the base
system on `zroot` on `nda0`, with cached packages in `/var/cache/pkg`. Tests ran
over the console-approved remote-debug listener. Each test streamed the kernel
log, `iostat -x`, the controller registers and driver counters off the machine,
so the data survived each hang.

| Kernel | Source | Use |
| --- | --- | --- |
| `/boot/kernel` | daemonarchy-src `d63d77f4` (1.3.1) GENERIC | original; kept as the fallback |
| `k111` (removed) | daemonarchy-src `83f5b5c2` (1.1.1) GENERIC | regression baseline |
| `t2exp` (removed) | `d63d77f4` + runtime experiment flags | isolating the trigger |
| `kernel.t2-cq-ack` | `d63d77f4` + the PR 34 `sys/dev/nvme` change | the fix; now the default |

Test kernels were built with the host toolchain in an isolated objdir on the
build host and booted once with `nextboot -k`, so that a hang fell back to the
original kernel.

## Characterization

The controller's registers were read through `/dev/mem` (BAR0). Before
failure, CAP was `0x00000020_f0010080` (MQES 128, timeout 120 s), CC was
`0x00470001` (IOSQES 7, 128-byte SQEs) and CSTS was `0x1`. At failure CSTS was
`0x3` (RDY and CFS). After the reset began, CC was `0x00470000` and CSTS
stayed `0x3`. PCIe AER uncorrectable status stayed 0 and device status did not
change, so the link was healthy and the controller itself had failed.

| Test (stock 1.3.1 kernel unless noted) | Result |
| --- | --- |
| 8× parallel `tar -xf` of 400 cached packages into ZFS (`/stress/run.sh`), 32 trackers | CFS after about 8 s |
| the same, single-threaded `tar` | CFS after about 6 s, at about 3.7k writes/s |
| the same, `hw.nvme.io_trackers=4` | 3 rounds passed (the October 22 workaround) |
| 8× 2 GiB parallel raw reads of `nda0`, 2.8 GB/s | passed |
| 160k random 16 KiB raw reads, 8 threads; also with buffers offset 512 or 2048 bytes within a page | passed (buffer alignment is not the trigger) |
| 8× 2 GiB parallel sequential ZFS writes, incompressible and compressible | passed (about 1.2 GB/s in 128 KiB writes) |
| 8 writers × 3000 small incompressible ZFS files | passed |
| random raw reads mixed with 2 GB/s ZFS writes | passed |
| random 8 KiB raw writes to the swapped-off swap partition, QD 1, 100k | passed |
| same, QD 2, 200k | passed |
| same, QD 4 | CFS after about 100k writes |
| same, QD 8, 112 trackers | CFS within 1 s |
| same, QD 8, `io_trackers=16` | CFS |
| same, QD 8, `io_trackers=8` | one run passed 400k writes; a second faulted after about 200k |
| same, QD 8, `io_trackers=4` | passed 400k writes |
| 1.1.1 kernel: QD 8 raw random writes, and the 8× `tar` stress | both CFS |

TRIM is not involved: `autotrim` is off and `kern.cam.nda.0.deletes` stayed at
0. The controller reports one power state and no APST, so power-state settings
do not apply. The driver has no `max_xfer_size` tunable; MDTS is 1 MiB, and the
failing raw writes were 8 KiB, so transfer size is not the trigger. The
random-write reproducer bypasses ZFS completely, so ZFS and UFS are not
involved either.

`dev.nvme.0.ioq.0.num_recovery_nolock` is 3 right after every boot on every
kernel, including the fixed one, and it did not change during any test. Those
three counts come from the shared interrupt handler firing during attach,
before the I/O queue is enabled. They are unrelated to this fault.

## Isolating the trigger

An experiment kernel exposed runtime switches in `hw.nvme.exp_flags`. Each
setting was tested with raw random 8 KiB writes to the swap partition.

| Driver change | QD 1 | QD 8 |
| --- | --- | --- |
| none (stock): one CQ doorbell write per batch, after the completions | passed | CFS in under 1 s |
| no INTMS/INTMC interrupt masking | — | CFS |
| FIFO tracker reuse instead of LIFO | — | CFS |
| doorbell written once per entry, before the completion, then a final write of the same value | **CFS at once** | — |
| final doorbell written twice with the same value | **CFS at once** | — |
| doorbell once per entry, before the completion, no repeated write | passed 100k | passed 1.6M |
| doorbell once per entry, after the completion | — | passed 1.6M |
| completions deferred until after one batched doorbell write | — | passed 1.6M |

Linux supports this controller with `SINGLE_VECTOR`, `128_BYTES_SQES`,
`SHARED_TAGS`, `SKIP_CID_GEN` and `IDENTIFY_CNS`. The FreeBSD fork already has
the equivalents. Linux has no dedicated quirk for this fault. Its interrupt path rings the
doorbell before finishing batched completions, so those tags are released only
after their completion entries are acknowledged, and it never rewrites the
doorbell with an unchanged value. That is consistent with T2 Linux systems not
reporting this fault, but it has not been tested on this machine.

## Fix and verification

The fix adds `QUIRK_APPLE_ACK_EACH_CPL` for `106b:2005` in
`sys/dev/nvme/nvme_qpair.c`, `nvme_private.h` and `nvme_pci.c`. Results with
`kernel.t2-cq-ack` (`d63d77f4` plus exactly that change):

| Test | Result | `num_recovery_nolock` before → after |
| --- | --- | --- |
| random 8 KiB raw writes, QD 8, 2.4M | passed | 3 → 3 |
| random 4 KiB raw writes, QD 48, 4.8M (about 100k IOPS) | passed | 3 → 3 |
| `/stress/run.sh` (8× `tar`, 400 packages, 3 rounds) | passed | 3 → 3 |
| 8× `tar` of 400 packages, 3 rounds, with old output removed | passed | 3 → 3 |
| 8× `tar` of all 1,906 packages, 5 rounds (67 GB, about 16k writes/s on average) | passed | 3 → 3 |
| after installing it as the default kernel and rebooting: `/stress/run.sh` | passed | 3 → 3 |

With the stock kernel, every one of these workloads faulted within seconds.

## State left on the machine

- `/boot/loader.conf` selects `kernel="kernel.t2-cq-ack"`. The original
  `/boot/kernel` (`d63d77f4`) is unchanged and can be selected from the loader
  menu. The previous file is saved as `/boot/loader.conf.before-t2fix`.
- The `hw.nvme.io_trackers` experiment line has been removed, so the default
  is 112 I/O trackers.
- `zroot/stress` has been destroyed, and swap is active again.
- `/boot/kernel.t2-cq-ack` is not listed in `/boot/manifest`. The installed
  system has `daemonarchy_secureboot="0"`, so the loader does not verify it.
  An enforcing secure-boot configuration would need a signed kernel that
  contains the fix.

## Remaining HW-002 work

- Select the fix in the source integration branch, build a release kernel that
  contains it, and repeat a fresh-image installation. Then repeat package
  integrity checks and desktop acceptance.
- The earlier false-success installer report is still unexplained.
