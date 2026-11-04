# Evidence for the newcomer tutorial

Every statement in [`course.json`](course.json) is taken from a repository document. Per-scene sources are listed in [NARRATIVE.md](NARRATIVE.md). The documents are:

- [Getting started](../getting-started.md): what you need, download, checksum, writing the stick, boot, live desktop, installer, first login, updates, what FreeBSD adds.
- [1.5.0 release notes](../release-1.5.0.md): what the release is and what was not verified.
- [aarch64](../aarch64.md): the community-validation status, the virtio-net receive stall and the e1000e workaround.
- [Installer trace](../install-trace.md) and [login trace](../login-trace.md).
- [1.5.1 plan](../roadmap/release-1.5.1.md) and the [active work queue](../roadmap/active-work.md): what moved to 1.5.1 and what is unscheduled.
- [Graphical package manager](../gui-package-manager.md): why `daemonarchy-pkg` has no real-desktop evidence.

Screenshots in `assets/` are byte copies of authentic files in [`../images/`](../images/): the desktop, the System > FreeBSD menu, the network panel, and two QEMU aarch64 captures. Nothing was staged or recorded for this film. The film shows no physical-desktop footage because none exists for the claims it makes.

Items that come from the project's report for 1.5.1 and are not yet in [aarch64](../aarch64.md): the alternative workaround `-device virtio-net-pci,event_idx=off` and the fix in daemonarchy-src pull request 59. Re-check them when the 1.5.1 notes are written.

Standard FreeBSD usage (`cd /usr/src && make buildworld installworld`, `cd /usr/ports/<category>/<port> && make all install`) is shown as the upstream route for contrast; it is general FreeBSD practice, not a command this repository documents.
