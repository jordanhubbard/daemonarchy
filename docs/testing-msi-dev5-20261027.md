# MSI capture candidate dev5, October 27

This replacement derives from the retained dev4 hardware trace image. It
repairs loader Lua without rebuilding its kernel, loader, ports or packages.
It is a hardware experiment image, not a qualified 1.4 release.

The [bounded qualification record](../native/hwtrace/dev5/qualification.json)
binds the image, source files, queue and retained VM evidence digests.

## Exact inputs

- Parent image: `daemonarchy-hwtrace-1.4.0-dev4-amd64.img`,
  SHA-256 `4961797855eee29c5a5f78f884bbebf7303ae6a28ece91ebc227d99180942e39`.
- Candidate: `daemonarchy-hwtrace-1.4.0-dev5-amd64.img`, 391153152 bytes,
  SHA-256 `7300f20205e2882c245790e74bded607100460e73236286e0536a4fbd6ce2afe`.
- Exact `splash.lua` and `netdebug.lua` from source
  `95eb020f9bb769b9f0ecb53b60470104bf7324c6`.
- Exact `menu.lua` from source `3d08a192a457f715664934fc84c461ae08c7615b`.
- These three files are the only intentional file changes in a private copy's
  HWTROOT filesystem. Native mount/unmount also changes filesystem bookkeeping.
  ESP, kernel, modules and DATRACE contents are retained. Embedded dev4 version
  strings remain unchanged; the candidate identity is the digest above.
- Kernel SHA-256:
  `12482ac842b55a168a5c3cad93960a8c7b4693ede6532e0ef1fe09110204f3e4`.
- Root loader SHA-256:
  `fbdb431c819881adc0b89683e6501ab718bdb89bddbb755233b7e5945b7ce015`.

The two source fixes have green native-loader and controller CI:
[runtime library fix](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/40574834182)
and [menu key fix](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/40574714779).
The source fixes use no table/math library that the loader does not open.

## Exact candidate USB boot evidence

The pristine candidate was copied to a separate test image. QEMU used
q35/smm, TCG, Westmere, two virtual CPUs, 2048 MiB, fresh OVMF 4M variables
and xHCI USB storage. No guest serial setting or loader configuration was
overridden. EFI/VGA screenshots retain the actual countdown and kernel startup.

1. First boot: 90 seconds, then QMP quit to simulate power loss. State advanced
   from `next=1,traces=0,pending=` to `next=2,traces=0,pending=0001`.
2. Second boot: same test image and persistent firmware variables, 45 seconds.
   Loader filed `TRACES/0001.TXT` and advanced to
   `next=3,traces=1,pending=0002`.
3. Trace 0001 identifies experiment `no-isa-hints`, prior loader cycle 1 at
   `booting`, current cycle 2 using raw blocks, and the kernel breadcrumb ring.
   Its status is INCOMPLETE because the first boot was intentionally stopped;
   its last recorded step is USB `umass0` attach. This is a VM test result,
   not an MSI diagnosis.
4. Both QEMU processes exited successfully; the raw block map still verifies
   all 201 files after the two boots.
5. The stdlib guard passed against all 19 Lua files extracted from the composed
   candidate. The bounded splash controls passed against that same extracted
   implementation, with table and math unavailable during splash execution.

The pristine candidate still starts at next 1, zero traces, empty pending, and
retains all four original queue files byte for byte: no-isa-hints, no-isa-bus,
no-isa-hints-one-cpu and rtc-vga-only. Test image state is separate from delivery.

A third, independent copy exercised the actual interactive menu: a QMP space
key during the countdown canceled autocycle, and the EFI/VGA screenshot showed
Boot trace, Hardware trace and Network debugging entries without a Lua exception.
The retained image lacks its optional gfx-daemonarchy branding include, so the
ordinary FreeBSD branding fallback remains visible. That cosmetic limitation does
not prevent menu operation or automatic trace capture.

## Readiness and limits

Candidate image, digest file, assembly digests, qualification JSON, persistent
VM variables, trace image and screenshots are retained in the private output
directory. No USB device was written during assembly or qualification.

Before delivery, the coordinator verifies the selected physical device identity,
unmounted partitions, exact candidate digest and an image-length readback digest
after writing. All device partitions must remain unmounted before unplugging.

Physical MSI raw-block persistence, reset/USB-cache behaviour and the four kernel
experiments remain untested. No native profile, lifecycle receipt or release
qualification is claimed. Prior images, packages, object trees and evidence are
preserved.


## USB delivery, October 28 UTC

The coordinator completed the physical write at 00:10:17 UTC. The
[sanitized delivery record](../native/hwtrace/dev5/usb-delivery.json) binds the
exact image and image-length readback SHA-256, both
`7300f20205e2882c245790e74bded607100460e73236286e0536a4fbd6ce2afe`,
over 391153152 bytes. This checks the written image prefix, not a claim that
the complete larger USB device equals the image.

The overwritten prefix and a separate final 128 KiB were preserved privately
before writing. The previous prefix digest matches the retained dev4 parent;
the unrelated device tail stayed unchanged. The coordinator verified device
identity privately, closed the exclusive writer and completed its cache flush
and readback before the following independent read-only checks:

- Actual STATE.TXT bytes match the pristine candidate: next 1, zero traces,
  empty pending, epoch 286014978.
- All four queue names and contents match the candidate.
- SLOTS.MAP matches the FAT extents for all 201 mapped files.
- All 200 preallocated trace slots are byte-identical empty placeholders.
- Partitions were unmounted; all verification file handles have closed.

The earlier assembly record's `usb_written: false` describes that earlier
test stage. The delivery record records the subsequent physical write.
Serial numbers, device nodes and private backup paths are intentionally omitted
from committed evidence. The coordinator owns final safe ejection.

The stick is prepared for the physical experiment. The MSI's firmware, raw
writes across its resets and the four kernel experiments remain pending; this
delivery check is not a native lifecycle or release receipt.
