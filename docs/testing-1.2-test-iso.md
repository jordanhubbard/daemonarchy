# 1.2 loader test ISO

A real `daemonarchy-1.2-test1-amd64.iso` now exists, built from product commit
`39c2785b595c8921cfe0fdea6704ad89c27ad7f5` through the retained `build-iso.sh`.
It is a loader development test image using the retained 1.1.1 base/packages,
not a completed 1.2.0 release. The operator explicitly prioritized producing
this scoped test artifact while canonical lifecycle integration remains open.
No Literate AI execution receipt or final release gate is claimed.

## Actual artifact and checks

- Retained on the FreeBSD build worker under
  `~/daemonarchy-test-images/1.2-test1-146d0a71/`, alongside its `.sha256` file.
- Size: **1,869,762,560 bytes**.
- SHA256: `146d0a7127472f1d2e8c05cedc2d54e6c91c1aa0988c5cc8506b03d12fbc7aaa`.
- Native assembly completed successfully in 692.869 seconds, using isolated
  staging and output directories. Preceding artifacts and caches were preserved.
- Native read-only inspection passed: actual El Torito EFI boot payload and live
  loader/Lua match the reviewed selection; all three installer sets, live kernel
  and all 261 embedded packages match the captured selected inputs.
- The complete live-runtime audit passed, including enterprise Wi-Fi Python
  imports and retained ELF dependency resolution. Private rescue authorization
  and startup payloads are absent. Loader debugging remains disabled.
- The VM worker received a byte-counted, SHA256-verified copy. Disposable UEFI
  installation and reboot with writable firmware variables passed (2,513.698
  seconds). All original system, desktop-command and checkout-policy checks
  passed. The root loader and both installed EFI copies match the stock base
  set, confirming that the development loader remained live-only. The preceding
  monolithic OVMF attempt refused before partition writes because the firmware
  exposed no readable Secure Boot state; that failure is preserved.

Selected world/kernel source is `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf`,
ABI 1600028, with ports `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`, the
matching clean jail snapshot and signed checkout catalogue. The application feed
is `packages-16-amd64-1.1.1`. Exact hashes and scoped results are in
[the test artifact record](../verification/test-iso-1.2-test1.json).

The unsigned live loader requires non-enforced Secure Boot. Physical hardware,
loader remote-console activation, desktop rendering, BIOS, encrypted install and
optional source/ports installation are not qualified by these checks. Installed
stock-loader preservation is verified on the actual installed disk. All 24 final
release obligations remain open; `project.test_receipt_missing` is still a real
framework/product qualification gap.

The live system emitted a WITNESS `isofs -> tmpfs` lock-order reversal during
poweroff. It powered off successfully; the installed disk booted and passed all
checks. Neither boot log contains a panic marker. This remains a known kernel
observation, retained with the raw private logs, rather than a clean final-release
kernel qualification. Both disposable disks, logs and terminal results are retained
in a private archive on the build worker; its SHA256 readback and compressed-tar
integrity checks passed.

## Loader selection and controls

The [live-only loader selection](../verification/test-loader-selection.json)
pins source `848c4bc16f3e757c6c3179f1fed5fcb6cd7503c0`, the 732,672-byte EFI
loader and its Lua payload. Native inspection verified these bytes both in the
live filesystem and inside the actual 10 MiB EFI boot image. The installer sets
retain their stock loader; the live debugging loader must not be installed onto
the target disk.

`TEST_LOADER_BUNDLE` selects a private directory containing `selection.json`,
`loader.efi` and `loader.lua`. The retained builder validates their hashes and
copies them into fresh staging. The post hook checks them again before poudriere
creates the EFI boot image. Replacement uses new inodes to preserve hardlinked
jail inputs. A Secure Boot bundle or conflicting overlay refuses; debugging keys
and activation configuration are not injected. Wired debug activation requires
an explicitly selected private profile using the source fork's runbook.

Eight [controller/native staging and selection controls](../verification/test-loader-controls.json)
passed before assembly, including independent allocations, failed-run
preservation, signed-payload conflicts, changed Lua bytes, aliases and hardlinked
jail preservation. Actual assembly and ISO auditing now supplement those narrow
controls. They do not establish hardware acceptance or framework admission.

## Lifecycle and final release boundary

The [combined first-binding checkpoint](../verification/native-first-binding-integration-development.json)
and [public SDK development checkpoint](../verification/native-sdk-public-development.json)
retain the framework work. The controller's isolated matching CLI validates
product authority and all eight current contract locks. Full verification still
reports `project.test_receipt_missing`; no receipt was synthesized from the
original-source build or VM harness.

The operator's explicit test-ISO priority permits this scoped preview through the
retained implementation while that integration remains unfinished. Final release
still requires canonical retained profiles, complete source/toolchain/sysroot and
package admission, actual native/product receipts and the remaining release
ledger acceptance. The current published release remains 1.1.1. This artifact
neither publishes a release nor marks all 24 obligations complete.

## Repeating qualification

1. Select exact control and loader source, compatible world/kernel sets, jail,
   ports, external modules, package inputs and signed checkout catalogue.
2. Check current worker ownership and actual output-volume headroom; allocate
   private stage/output roots and preserve preceding evidence.
3. Run the retained build with the hash-checked live loader bundle and selected
   signed application feed. Preserve the assembly command, input capture,
   terminal result, image bytes and SHA256.
4. Audit the actual EFI boot image, live payloads, installer sets and packages;
   run `tests/live-image-runtime.sh` natively against these exact ISO bytes.
5. Transfer with SHA256 verification. Run `test-qemu.sh` with disposable storage,
   UEFI pflash and an unenrolled writable variable template. Preserve failure
   evidence and verify the installed stock loader, kernel and ABI after reboot.
6. Report the actual artifact and checks independently of physical hardware,
   graphical rendering, Secure Boot and final release qualification.
