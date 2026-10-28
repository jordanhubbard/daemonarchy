# Documentation index

Product goals and completeness are in root `PROJECT.md`; build and release
commands remain in root `HACKING.md`. This index makes the retained evidence
reachable without changing its historical scope.

The current release is **1.3.1**: start with its
[release notes](release-1.3.1.md) and the [getting-started guide](getting-started.md).
Its published identity is recorded in
[`release/current.json`](../release/current.json); documents dated or named for
another version are historical records. 1.4 entries describe work in development.

- [Application note: MacBook Pro 16-inch (2019)](application-note-macbookpro16-1.md)
- [MacBookPro16,1 physical acceptance for 1.3.1](testing-macbookpro16-1-1.3.1.md)
- [Daemonarchy 1.3.1 release notes and evidence](release-1.3.1.md)
- [Product architecture and acceptance traceability](architecture/design-traceability.md)
- [Enterprise Wi-Fi](enterprise-wifi.md)
- [FreeBSD application and menu policy](freebsd-application-policy.md)
- [Pinned package dependency graphs](package-dag.md)
- [Native package resolution checks](native-package-plan.md)
- [Signed catalogue and package payload checks](signed-package-snapshot.md)
- [1.3.1 package repository key rotation](package-repository-key-rotation-1.3.1.md)
- [Getting started with Daemonarchy](getting-started.md)
- [Hardware quirks](hardware-quirks.md)
- [Hardware trace stick: reset-surviving boot trace](boottrace.md)
- [1.4 live5 unsigned release candidate and hwtrace dev6, October 28](testing-1.4-live5-20261028.md)
- [Lua-repaired live4: exact TUI/live-mode boot checks](testing-1.4-live4-lua4-20261028.md)
- [Hardware trace stick: QEMU/OVMF checks, October 27](testing-1.4-boottrace-20261027.md)
- [Hardware trace stick: raw-block writes, self-report and ring, October 27](testing-1.4-hwtrace-rawblock-20261027.md)
- [MSI capture candidate dev5: exact USB VM evidence](testing-msi-dev5-20261027.md)
- [MSI capture candidate dev7: legacy VGA probe skip](testing-msi-dev7-20261028.md)
- [MSI capture candidate dev8: no legacy VGA probe on UEFI boots](testing-msi-dev8-20261028.md)
- [MSI capture candidate dev10: AT RTC left alone on a UEFI port conflict](testing-msi-dev10-20261028.md)
- [Optional ports and system source: space estimate](optional-source-sizing.md)
- [Daemonarchy 1.1.0 release notes (historical)](release-1.1.0.md)
- [Installer remote agent debug mode](remote-agent-debug.md)
- [EFI loader cannot find loader.lua](repair-efi-root.md)
- [Installation logs and the rescue console](rescue-console.md)
- [Active work](roadmap/active-work.md)
- [Historical 1.3.2 network debugging plan](roadmap/release-1.3.2.md)
- [1.4.0 plan: Literate AI cross-repository build and release orchestration](roadmap/release-1.4.0.md)
- [aarch64 inventory and VMware worker bring-up (ARCH-001)](aarch64.md)
- [1.1.1-to-1.3.1 application package reuse inventory](evidence/release-1.3.1-package-reuse-inventory.md)
- [Earlier 1.3.1 diagnostics scope and preflight evidence](roadmap/release-1.3.1.md)
- [Owned FreeBSD source builds](source-builds.md)
- [Disposable QEMU worker ownership](native-qemu-worker.md)
- [Remote build worker (design and implementation, planned for 1.4.0)](remote-worker.md)
- [Remote build worker: hosted tests and sample workloads, October 28](testing-remote-worker-20261028.md)
- [Complete FreeBSD source and ports Component coverage](roadmap/freebsd-components.md)
- [Native Component execution and build performance](roadmap/build-performance.md)
- [Parallel native workspace and executor selection](roadmap/native-workspace.md)
- [Manual Secure Boot certificate enrollment](secure-boot.md)
- [1.1 BIOS development checks](testing-1.1-bios.md)
- [Bluetooth audio development checks](testing-1.1-bluetooth-audio.md)
- [Final 1.1 image qualification](testing-1.1-final-image.md)
- [Physical hardware observations](testing-1.1-hardware-observations.md)
- [Private headless rescue checks, 2026-10-15](testing-1.1-headless-rescue.md)
- [1.1 live image size qualification](testing-1.1-image-budget.md)
- [1.1 shallow checkout and driver development checks](testing-1.1-live-checkouts.md)
- [Native desktop application checks, 2026-10-15](testing-1.1-native-apps.md)
- [Testing the 1.1 partition installer](testing-1.1-partitions.md)
- [1.1 source and ports refresh preparation](testing-1.1-refresh.md)
- [Remote agent debug preview checks](testing-1.1-remote-debug.md)
- [Secure Boot development and production evidence](testing-1.1-secureboot.md)
- [Preliminary 1.0.1 upgrade and rollback checks](testing-1.1-upgrade.md)
- [Hyprland in QEMU: VirtIO DRM development checks](testing-1.1-vm-graphics.md)
- [LIVE-001 live desktop preview: native build and bhyve cases, October 26](testing-1.4-live-desktop-20261026.md)
- [LIVE-001 live desktop under QEMU/VirGL: desktop, fallback, network parity and graphical install, October 27](testing-1.4-live-desktop-virgl-20261027.md)
- [1.4 live4 development candidate (own-source kernel and loader) and hwtrace dev3, October 27](testing-1.4-live4-20261027.md)
- [Daemonarchy 1.1.1 refresh](testing-1.1.1.md)
- [MacBookPro16,1 first-boot investigation](testing-macbookpro16-1.md)
- [MacBook installer fatal NVMe investigation, October 22](testing-macbookpro16-1-installer-20261022.md)
- [Private MacBook Wi-Fi and EFI timer preview images, October 22](testing-macbookpro16-1-wifi-preview-20261022.md)
- [MacBook signed firmware handoff candidate, October 23](testing-macbookpro16-1-firmware-handoff-20261023.md)
- [MacBook physical S3 suspend and resume trial, October 24](testing-macbookpro16-1-s3-20261024.md)
- [MacBook Apple T2 NVMe fatal status: root cause and driver fix, October 26](testing-macbookpro16-1-nvme-20261026.md)

- [Unpublished 1.2.0 plan and worker model](roadmap/release-1.2.0.md)

- [1.2 loader test ISO and qualification](testing-1.2-test-iso.md)
- [1.4 development: network-debug native rerun, October 26](testing-1.4-network-debug-20261026.md)

- [NetGDB peer-close patch for human review](contributions/netgdb-peer-close.md)

- [Measured installer progress](installer-progress.md)
- [Upcoming 1.4 install screen demos](demos/installer-visuals/README.md)

- [Package reuse provenance inventory](package-reuse-inventory.md)

- [Release measurement and pending QA drivers](release-measurements.md)

- [Verified package retention and iterative installer cache](verified-artifact-cache.md)

- [Cross-repository retained input graph](release-input-graph.md)
