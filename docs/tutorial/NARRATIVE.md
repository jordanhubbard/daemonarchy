# Daemonarchy newcomer tutorial: narration script

This is the readable script for [`course.json`](course.json), the editable source of the movie. Edit the manifest, then rebuild (see [README.md](README.md)). Cast: **Imp**, a small daemon who guides; **Robin**, a newcomer from Windows and a little Linux. Terminal lines on screen are inert text and are never run. Each scene lists where its claims come from.

## 1. Meet Daemonarchy

Visual: `assets/desktop.png`

**Robin:** I have used Windows and a bit of Linux. Someone told me to try Daemonarchy. What actually is it?

**Imp:** Daemonarchy is the Omarchy desktop running on FreeBSD. Omarchy is D H H's opinionated Hyprland desktop. We install it the way the Omarchy ISO installs it on Arch. The name is a homage: Omarchy's archy, ruled by the BSD daemon. I am Imp, a small daemon, and I will be your guide.

*Source: Real screenshot, docs/images/desktop.png (README).*

## 2. Same as FreeBSD, different from FreeBSD

- On screen: Same: FreeBSD 16.0-CURRENT kernel, ZFS, pkg, jails, bhyve, DTrace
- On screen: Different: Omarchy desktop, guided installer, signed package feeds
- On screen: An image is tied to the CURRENT snapshot it was built from

**Robin:** So is it FreeBSD, or is it something else?

**Imp:** It is FreeBSD underneath. Each release is built from a FreeBSD 16.0-CURRENT snapshot, and CURRENT moves daily, so an image is tied to the snapshot it came from. What is different is everything on top: the Omarchy desktop, an installer that asks the same questions as the Omarchy one, and signed package feeds for the Omarchy ports and the graphics and Wi-Fi kernel modules. Daemonarchy is not affiliated with Omarchy.

*Source: README.md 'Daemonarchy' and 'What the image contains'.*

## 3. What FreeBSD adds to the menu

- On screen: Boot environments, restore files, jails
- On screen: Virtual machines with bhyve, tracing with DTrace
- On screen: System > FreeBSD menu

Visual: `assets/freebsd.png`

**Imp:** FreeBSD's strengths sit in the menu under System, FreeBSD. Boot environments are bootable copies of the whole system, saved before every update. Restore Files shows hourly and daily snapshots of your home folder. There are jails, bhyve virtual machines, and live DTrace views of what the system is doing.

*Source: Real screenshot, docs/images/freebsd.png.*

## 4. What you need

- On screen: x86-64 PC, UEFI or BIOS; USB stick of 4 GB or more
- On screen: 40 GB or more of disk, and a network during the install
- On screen: aarch64 image: UEFI only, community validation (QEMU)

**Robin:** What do I need before I start?

**Imp:** A 64-bit x86 PC with UEFI or legacy BIOS, a USB stick of four gigabytes or more, and a disk or region of forty gigabytes or more. The installer downloads packages, so you need a network. Writing the image erases the stick, and whole-disk mode erases the disk you choose. There is also an arm64 image, but it is a community-validation image. I will come back to it.

*Source: docs/getting-started.md 'What you need'.*

## 5. Get and check the image

- On screen: Download .iso.xz and its .sha256 from the download page
- On screen: GitHub Latest is the newest stable release: 1.5.0
- On screen: Checking is optional but quick

```sh
$ sha256sum -c daemonarchy-*.iso.xz.sha256
# macOS: shasum -a 256 -c daemonarchy-*.iso.xz.sha256
```

**Imp:** Get the xz-compressed ISO and its matching checksum file from the download page. The checksum covers the compressed file you download. On Linux, run sha256sum with the dash c flag. On macOS use shasum, and on FreeBSD use the sha256 command. All of these are in the getting-started guide.

*Source: docs/getting-started.md section 1; README Download.*

## 6. Write it to a USB stick

- On screen: Copying the file onto the stick like a document does not work
- On screen: Easy way: balenaEtcher accepts the .iso.xz directly
- On screen: Be sure of the device name: dd overwrites what you point it at

```sh
$ lsblk
$ xz -dc daemonarchy-1.5.0-amd64.iso.xz | \
    sudo dd of=/dev/sdb bs=1M status=progress conv=fsync
```

**Robin:** Can I just drag the file onto the stick?

**Imp:** No. The image is copied byte for byte. Balena Etcher is the easy way on any system. On Linux, find your stick with lsblk, then decompress while writing: xz dash d c, piped into dd. The device here, slash dev slash s d b, is only an example. Check yours first, because dd overwrites whatever you point it at.

*Source: docs/getting-started.md section 2. /dev/sdb is the guide's own example.*

## 7. Boot, and try the live desktop

- On screen: Turn Secure Boot off, or enroll the project certificate
- On screen: At the loader menu press T: live desktop (x86-64, since 1.4.0)
- On screen: Enter starts the text installer; the live desktop changes no disk

**Imp:** Use the boot menu key, often F12 or Escape. Either turn Secure Boot off, or manually enroll the project certificate. At the loader menu, press T to try the live desktop. It runs from the stick and memory and touches no disk. Pressing Enter starts the text installer instead. The aarch64 image has no live desktop.

*Source: docs/getting-started.md section 3.*

## 8. The installer

- On screen: Keyboard, account, network, remote access
- On screen: Storage: whole disk, partition or free space; optional encryption
- On screen: Confirm, then wait for the explicit completion screen

**Robin:** And then?

**Imp:** The installer asks a handful of questions: keyboard, your account, network, whether you want SSH access, and where to install. Nothing is written until you confirm on the last screen. The desktop has roughly twelve hundred packages, so be patient. Do not remove the stick until the installer shows its successful completion screen. An unexpected reboot is not that signal.

*Source: docs/getting-started.md section 4.*

## 9. The arm64 image: honest status

- On screen: Verified: boots and installs in QEMU, nothing more
- On screen: Known issue: default virtio-net stalls the package fetch
- On screen: Workaround: an e1000e network card in QEMU

```sh
-device e1000e
-device virtio-net-pci,event_idx=off
```

**Imp:** The aarch64 image is for community validation. It was verified to boot and install in a QEMU virtual machine and nothing more. With QEMU's default virtio network card, the install stalls during the package fetch: the guest stops servicing receive, and every download times out. Use an e1000e card, or turn off event index on the virtio card. The fix is in daemonarchy-src pull request fifty-nine, planned for 1.5.1, so it is not in the published image.

**Robin:** And real arm64 hardware?

**Imp:** The one physical machine tried, the NVIDIA RTX Spark laptop, does not reach a desktop yet. We say so plainly.

*Source: docs/aarch64.md 'Status in 1.5.0'. The event_idx=off form and PR #59 come from the project's report for 1.5.1, not yet in docs/aarch64.md.*

## 10. What aarch64 reached

- On screen: SDDM greeter and Omarchy session, in software rendering
- On screen: QEMU 11.1.2 with HVF on an Apple silicon Mac
- On screen: Not verified: 3D, physical GPU, sound, Wi-Fi, live desktop

Visual: `assets/aarch64-qemu-omarchy-session.png`

**Imp:** This is real evidence from a QEMU guest with a VirtIO GPU. The greeter and the Omarchy session draw in software. It is a start, not a promise about hardware.

*Source: Real screenshot, docs/images/aarch64-qemu-omarchy-session.png.*

## 11. Your first login

- On screen: Super + Space: the menu. Super + K: every shortcut, searchable
- On screen: Super + Return: terminal. Super + Shift + B: browser
- On screen: Super + Ctrl + W: network panel

Visual: `assets/network.png`

**Imp:** Log in with the password you chose. The first login takes a few seconds longer while your desktop is set up. Everything starts from the keyboard. Super, the key with the Windows or Command logo, plus Space opens the menu. Super plus K lists every shortcut. Super plus Return opens a terminal. Windows tile themselves, so there is nothing to drag.

*Source: Real screenshot, docs/images/network.png (names blurred in the original).*

## 12. Updates, with a way back

- On screen: daemonarchy update saves a boot environment first
- On screen: sudo pkg upgrade alone does not
- On screen: Base and kernel changes arrive with a new image, not pkg upgrade

```sh
$ daemonarchy --help
$ daemonarchy update
```

**Robin:** What if an update breaks something?

**Imp:** Daemonarchy's update flow saves a boot environment first, so you restart into an earlier one from the boot menu. A plain sudo pkg upgrade does not make one. Be clear about the limit: pkg upgrade updates applications. It does not upgrade the FreeBSD base or the kernel. A release that changes those comes from its image, and network upgrades are planned for 1.5.1.

*Source: docs/getting-started.md section 10; HACKING.md 'The upgrade model today'.*

## 13. Developers: the stock FreeBSD way

- On screen: Upstream FreeBSD builds the system and ports in place
- On screen: Fine for FreeBSD itself; Daemonarchy has more moving parts
- On screen: A Daemonarchy change also needs the right repo and a pin

```sh
$ cd /usr/src && make buildworld installworld
$ cd /usr/ports/<category>/<port> && make all install
```

**Robin:** I know FreeBSD a little. Do I just build world and ports like the handbook says?

**Imp:** That is the stock route: build and install the world from slash usr slash src, and build a port from its directory under slash usr slash ports. It still works for FreeBSD itself. But Daemonarchy is several repositories pinned together and released together, so a change has to land in the right place and be tested against the signed image.

*Source: Commands are standard FreeBSD usage (FreeBSD Handbook); the repo framing is HACKING.md 'The repositories that make up Daemonarchy'.*

## 14. The Daemonarchy way: change the right repo

- On screen: Artwork, menu, daemonarchy-* tools: daemonarchy-desktop
- On screen: Installer, ISO and feed scripts, tests: daemonarchy
- On screen: Ports: daemonarchy-ports. Kernel and base: daemonarchy-src

**Imp:** Ask first where the change lives. Artwork, the login theme and the System FreeBSD menu belong to daemonarchy-desktop. The installer, image scripts, tests and documentation belong to the daemonarchy repository. Package recipes are in daemonarchy-ports, and the kernel and base are in daemonarchy-src. Omarchy's FreeBSD adaptation lives in omarchy-freebsd. Pins tie them together.

*Source: HACKING.md 'Where a change goes'.*

## 15. Hack on Daemonarchy from Daemonarchy

- On screen: A Daemonarchy machine can be its own development machine
- On screen: System > FreeBSD > Hack on Daemonarchy clones the trees to ~/src
- On screen: dev link runs the desktop from your Omarchy checkout

```sh
$ daemonarchy-dev-setup
$ daemonarchy dev link ~/src/omarchy
$ daemonarchy dev sync --watch
$ daemonarchy dev unlink
```

**Imp:** The daemonarchy-dev-setup command clones the trees into your src folder. Then daemonarchy dev link runs the desktop from your own Omarchy checkout after a reboot. While a session runs, dev sync with the watch flag rebuilds the FreeBSD tree after each save. dev unlink takes you back to the installed Omarchy.

*Source: HACKING.md 'Working on Daemonarchy from Daemonarchy'. Displayed commands are inert text.*

## 16. Ports and the FreeBSD layer

- On screen: Ports fetch omarchy-freebsd and daemonarchy-desktop as releases
- On screen: To try your own checkout: extract, lay it over, reinstall

```sh
$ cd ~/src/freebsd-ports/x11-wm/omarchy && make extract
$ rsync -a --exclude .git ~/src/omarchy-freebsd/ \
      "$(make -V WRKSRC_freebsd)/"
$ sudo make reinstall clean
```

**Imp:** This is the familiar ports workflow with one twist. Let the port extract its sources, lay your checkout over them, and let it carry on with reinstall. You are using the ports tree the way FreeBSD intends, with your own source in the middle.

*Source: HACKING.md 'The FreeBSD layer and the desktop layer'.*

## 17. Test it like the project does

- On screen: test-qemu.sh installs an ISO unattended under QEMU; no root
- On screen: Emulated x86 on a non-x86 host: expect two to three hours
- On screen: ARCH=aarch64 selects qemu-system-aarch64 with UEFI

```sh
$ ./test-qemu.sh daemonarchy.iso
$ ARCH=aarch64 ./test-qemu.sh daemonarchy-aarch64.iso
```

**Imp:** Before you trust a change, install it. The test-qemu script boots the ISO with a blank disk, installs unattended, boots the installed disk and checks what a VM without a GPU can show. It needs no root. Every install also writes a timing trace, and a login trace is kept on the installed system, so slow steps are measured rather than guessed.

*Source: test-qemu.sh header; docs/install-trace.md; docs/login-trace.md.*

## 18. Where Literate AI fits in 1.5.x

- On screen: Literate AI (litai): the authority layer for contracts, evidence
- On screen: A metadata check is not native qualification
- On screen: Native build-speed goals moved to 1.5.1; none claimed done

```sh
$ litai project validate .
$ litai verify
```

**Robin:** Why does a FreeBSD desktop need an AI framework?

**Imp:** In 1.5.x Literate AI is how the project states and checks its promises. The product goals, the work queue and the architecture are validated in place by litai project validate, and litai verify prints the full gate report. Those checks do not generate source or qualify a native build. The framework-executed goals, build speed, source and ports as components, and a development system, were moved from 1.5.0 to 1.5.1. Nothing there is claimed done. Shipping litai itself as a package is proposed, and unscheduled.

*Source: HACKING.md 'Literate AI project authority'; PROJECT.md; docs/roadmap/release-1.5.1.md; LITAI-PKG-001 in docs/roadmap/active-work.md.*

## 19. What we have not shown

- On screen: No real-desktop evidence yet: daemonarchy-pkg, Steam, Windows apps
- On screen: Wi-Fi and Hyprland are not guaranteed on any machine
- On screen: Published does not mean qualified: read the release notes

**Robin:** Is there anything I should be careful about?

**Imp:** Yes. The graphical package manager has no real-desktop evidence yet, and the menu still opens OctoPkg. Steam and Windows programs were checked headless on a build machine, not on a real desktop. Wi-Fi and Hyprland are not guaranteed on any particular machine. We would rather tell you than let you find out.

*Source: docs/release-1.5.0.md; README.md; docs/gui-package-manager.md.*

## 20. Where next

- On screen: Getting started: docs/getting-started.md
- On screen: Hacking guide: HACKING.md
- On screen: Open an issue: what you ran, and what you saw

**Imp:** Read the getting-started guide for your first hour, and the hacking guide when you want to change something. If something goes wrong, open an issue with what you did and what you saw. Success reports help as much as failures. Welcome to Daemonarchy.

**Robin:** Thanks, Imp.

*Source: docs/getting-started.md 'Going further'.*
