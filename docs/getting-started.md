# Getting started with Daemonarchy

This guide takes you from a download to a working desktop, and through the things you will do in your first hour: get online, play sound, pair a keyboard, keep the system up to date, and use what FreeBSD adds. You do not need to know FreeBSD or Omarchy already.

Daemonarchy is the [Omarchy](https://omarchy.org) desktop running on [FreeBSD](https://www.freebsd.org). If you are curious how it is put together, or want to change it, read the [hacking guide](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md) when you are done here.

This guide covers Daemonarchy 1.1.1. The [download page](https://github.com/jordanhubbard/daemonarchy/blob/main/README.md#download) identifies what is published; [the 1.1.1 record](testing-1.1.1.md) records the image and outstanding qualification. Earlier 1.0.1 has whole-disk, UEFI-only
installation and needs Secure Boot off. See the [download page](https://github.com/jordanhubbard/daemonarchy/blob/main/README.md#download)
and the release
[qualification record](testing-1.1-final-image.md) before choosing hardware.

![The Daemonarchy desktop, with the System > FreeBSD menu open](images/desktop.png)

## What you need

- A 64-bit x86 PC. The 1.1 release supports UEFI and legacy BIOS.
- A USB stick of 4 GB or more. Writing the image erases it.
- A disk or installation region of 40 GB or more. Whole-disk mode erases the selected disk. In 1.1 you can instead replace a selected GPT partition or use existing free space. The installer does not shrink filesystems; create space from the other operating system first.
- A network connection during installation. Wired Ethernet or personal Wi-Fi is the simplest path. The 1.1 [enterprise Wi-Fi configuration](enterprise-wifi.md) is implemented, but real enterprise authentication remains unqualified.
- Graphics supported by the packaged FreeBSD drivers. The 1.1 release includes NVIDIA drivers; the RTX 4090 driver/compute probes passed, while its installed desktop remains unqualified. QEMU with VirtIO/VirGL passed actual Hyprland checks. Read the [hardware quirks](hardware-quirks.md), especially the ASRock, MSI Raider and T2 MacBook observations.

## 1. Download the image

Get the `.iso` and matching `.sha256` from the [download page](https://github.com/jordanhubbard/daemonarchy/blob/main/README.md#download). GitHub **latest** selects stable 1.1.1. Read its qualification record before installing: publication does not establish physical-hardware compatibility or completion of the final installation matrix.

Checking the download is optional but quick. In a terminal, in the folder you saved both files to:

- macOS: `shasum -a 256 -c daemonarchy-*.iso.sha256`
- Linux: `sha256sum -c daemonarchy-*.iso.sha256`
- FreeBSD: `sha256 -c "$(cut -d' ' -f1 daemonarchy-*.iso.sha256)" daemonarchy-*.iso`
- Windows (PowerShell): `Get-FileHash daemonarchy-*.iso`, then compare the result with the number in the `.sha256` file.

From 1.4.0 the image downloads xz-compressed as `daemonarchy-<version>-<arch>.iso.xz`, which is much smaller. Its `.iso.xz.sha256` file checks the compressed download, so use the same commands with `.iso.xz` in place of `.iso` (for example `sha256sum -c daemonarchy-*.iso.xz.sha256`).

## 2. Write it to a USB stick

The image is copied to the stick byte for byte; copying the file onto the stick like a document does not work.

- **Any system, the easy way:** [balenaEtcher](https://etcher.balena.io). Pick the `.iso`, pick the stick, press Flash.
- **Windows:** [Rufus](https://rufus.ie) works too; when it asks, choose **DD image mode**.
- **macOS:** find the stick with `diskutil list` (say it is `/dev/disk4`), then `diskutil unmountDisk /dev/disk4` and `sudo dd if=daemonarchy-1.1.0-amd64.iso of=/dev/rdisk4 bs=1m`.
- **Linux:** find the stick with `lsblk` (say `/dev/sdb`), then `sudo dd if=daemonarchy-1.1.0-amd64.iso of=/dev/sdb bs=1M status=progress conv=fsync`.

For a 1.4.0 or later `.iso.xz`, balenaEtcher can flash the compressed file directly. For `dd`, decompress while writing instead of passing `if=`: `xz -dc daemonarchy-<version>-amd64.iso.xz | sudo dd of=/dev/rdisk4 bs=1m` on macOS, or `xz -dc daemonarchy-<version>-amd64.iso.xz | sudo dd of=/dev/sdb bs=1M status=progress conv=fsync` on Linux. FreeBSD and most Linux systems include `xz`; on macOS install it with Homebrew (`brew install xz`). If another tool will not accept the `.xz`, extract the `.iso` first, for example with [7-Zip](https://www.7-zip.org) on Windows.

Be sure of the device name: `dd` overwrites whatever you point it at.

## 3. Boot from the stick

1. Plug the stick in and turn the machine on, pressing its boot menu key (often F12, F11, F10 or Esc; on Macs hold Option).
2. For earlier 1.0.1, turn Secure Boot off. The 1.1 release can also boot with it off; enforced Secure Boot requires [manual enrollment of the project certificate](secure-boot.md), preserving existing OEM/Windows keys. Factory keys alone reject the project loader.
3. Choose the USB stick. Use UEFI for Secure Boot; 1.1 also supports legacy BIOS boot.

## 4. Install

The installer asks a handful of questions, then installs on its own. Use the arrow keys, Tab and Enter.

1. **Welcome.** Press Enter to begin.
2. **Keyboard.** Pick your keyboard layout.
3. **Your account.** Your name, a user name, a password (you will log in with it, and give it when the system asks for your permission), a name for the computer, and your time zone.
4. **Network.** The installer lists your network adapters. A plugged-in cable is usually already connected; otherwise pick **Join Wi-Fi**, choose your network and type its password. You can also set an address by hand if your network has no DHCP. If the clock is wrong, choose **Set date and time** and enter the current UTC date and time; this works offline. **Synchronize time over network** tries NTP for up to 30 seconds. After either action the installer checks package access again. Package downloads still require internet access.
5. **Remote access.** Say yes only if you want to log in to this machine from another one over SSH.
6. **Storage.** Pick the disk and installation mode, review the selected region, and choose whether to **encrypt** it. Encryption requires your password each time the machine starts. Earlier 1.0.1 supports whole-disk mode only.
7. **Ready.** Check the summary and confirm. Writes to the selected disk/partition/free region begin after confirmation.

The 1.1 release also offers optional `/usr/ports` and `/usr/src` Git checkouts. They download separately when selected and use the release's pinned revisions. Leave them off if you only want to run the desktop.


The desktop has roughly 1,200 packages; download and installation time depend on the selected release and connection. Wait for the explicit successful completion screen before removing the stick and restarting. An unexpected reboot is not that completion signal.

## 5. Log in

At the login screen, type your password and press Enter. An encrypted 1.1 installation can open the desktop automatically after the boot-time unlock. The first login takes a few seconds longer while your desktop is set up.

## 6. Find your way around

Everything starts from the keyboard. The key with the Windows or Command logo is called **Super**.

| Keys | What it does |
|---|---|
| Super + Space | The Daemonarchy menu: apps, settings, setup, updates, FreeBSD tools |
| Super + K | Every keyboard shortcut, searchable |
| Super + Return | Terminal |
| Super + Shift + B | Web browser |
| Super + Shift + F | Files |
| Super + W | Close the window |
| Super + 1 ... 9 | Switch workspace (Super + Shift + number moves the window there) |
| Super + T | Float or tile the window |
| Super + F | Full screen |
| Print Screen | Screenshot |
| Super + Ctrl + L | Lock the screen |
| Super + Escape | Log out, restart, shut down |

Windows tile themselves side by side as you open them; there is nothing to drag. The bar at the top shows your workspaces, the time, and icons for network, sound and Bluetooth: click one to open its panel.


## 7. Get online

Open the network panel with **Super + Ctrl + W**, or click the network icon in the bar.

- With a cable plugged in you are already online.
- For Wi-Fi, turn **Wi-Fi** on (the first time, this sets up your Wi-Fi card), pick a network, and type its password. Daemonarchy remembers it and reconnects by itself.
- To forget a network, highlight it and choose **Forget**.

![The network panel](images/network.png)

A cable is enough. If a wireless card is present and no Wi-Fi switch appears, FreeBSD has no driver for that card.

## 8. Sound

Open the sound panel with **Super + Ctrl + A**, or click the speaker icon. Pick where sound plays (speakers, headphones, HDMI) and which microphone records, and set the volume. The volume keys on your keyboard work as well.


## 9. Bluetooth devices

Open the Bluetooth panel with **Super + Ctrl + B**, or click the Bluetooth icon.

1. Turn Bluetooth on.
2. Put your keyboard or mouse into pairing mode (usually by holding its connect button until a light blinks).
3. Pick it from the list of devices found. Once paired it reconnects by itself.

Earlier 1.0.1 supports classic Bluetooth input devices. The 1.1 release adds a native A2DP/SBC audio backend and output selection; real headset playback, reconnect/reboot and input-device regression checks remain unqualified. LE Audio and headset microphone profiles are outside this implementation. Use wired/USB audio while evaluating that support; see the [Bluetooth evidence](testing-1.1-bluetooth-audio.md).

## 10. Keep it up to date

Open the menu (**Super + Space**) and choose **Update**. Daemonarchy updates FreeBSD's packages and its own in one go, and before it changes anything it saves a **boot environment**: a snapshot of the whole system you can go back to if an update goes wrong (see below).

In a terminal, `daemonarchy update` uses the desktop update flow.
`sudo pkg upgrade` updates packages directly and does not create a boot
environment for you. Application-package upgrades do not migrate the FreeBSD
base/kernel or convert an old installation to Secure Boot. Verified installations
keep kernel-module packages locked to their signed snapshot. The 1.1.1 feed requires OSVERSION `1600028` in both the base system and kernel, with matching drivers; changing the feed URL alone does not perform that upgrade. Use the documented
[signed maintenance workflow](secure-boot.md#update-and-recovery-contract) for protected boot updates.

Installations made with an older image need a one-time
[boot-root mount-policy check](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#boot-environment-mount-policy)
before switching boot environments. New 1.1.1 installations set the correct
policy; an application-package update alone does not repair existing ZFS
dataset properties.

The 1.1 desktop includes Chromium and the **OctoPkg** graphical package
manager. Choose **Install > Packages** or **Remove > Packages** to search,
install or remove FreeBSD packages; OctoPkg asks for administrator
authentication when it needs it. The terminal package pickers remain
available as `daemonarchy pkg install` and `daemonarchy pkg remove`.

Use `daemonarchy --help` or `daemonarchy commands` to discover desktop
commands. For example, `daemonarchy update` runs Daemonarchy's update flow.
The desktop does not configure a local Docker engine, so it omits the stock
Docker application and Docker database/setup entries. Docker needs a Linux
VM or a separately configured remote engine on FreeBSD.

## 11. What FreeBSD adds

Open the menu and go to **System > FreeBSD**.

- **Boot Environments:** every update first saves a bootable copy of the system. If something breaks, pick an earlier one here (or from the boot menu at startup) and restart into it.
- **Restore Files:** your home folder is snapshotted every hour and every day. Browse a snapshot and copy back a file you deleted or changed by mistake.
- **Jails:** lightweight FreeBSD containers, each with its own packages, for trying things out without touching your system.
- **Virtual Machines:** run Linux, Windows or another BSD in a window, with bhyve.
- **Trace the System:** live views of what programs, files, disks and the network are doing, with DTrace.
- **Hack on Daemonarchy:** run the desktop from your own copy of its source code (see the [hacking guide](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md)).

![Hourly snapshots of your home in Files, a live DTrace view, the ZFS pool, and the sound panel](images/freebsd.png)

## 12. AI coding tools

Install available FreeBSD coding tools through **Install > Packages** or `pkg`. Daemonarchy does not offer upstream Omarchy’s automatic Linux agent downloads. Linux-only versions must pass version-specific Linuxulator testing before they can become release defaults.

## When something goes wrong

- **The machine will not boot the stick:** check the image/firmware mode and the [Secure Boot enrollment requirements](secure-boot.md). Check [known hardware blockers](hardware-quirks.md) before trying speculative loader changes.
- **The install stopped or restarted itself:** use the [rescue menu](rescue-console.md) to inspect the retained log and installation status before retrying. The live log is `/tmp/daemonarchy-install.log`; retained target evidence is `/var/log/daemonarchy-install.log` and `/var/db/daemonarchy/install`. The 1.1.1 integrity check refuses success when package files are missing or damaged. An unexpected reset is not evidence of completed installation; do not restart disk partitioning over the existing target to resume packages.
- **No rescue menu after boot messages:** 1.1.1 waits briefly for late probes and redraws the menu automatically. On an older image, pressing Return may redraw a menu that boot messages obscured. If pairing says another session is active, use **Unpair remote debugging agent** in rescue option 2, then **Pair** again on 1.1.1.
- **A black screen after login in a VM:** the tested 1.1 desktop path is QEMU with VirtIO/VirGL. Other virtual graphics configurations, including refreshed bhyve, remain unqualified. See the [VM graphics record](testing-1.1-vm-graphics.md).
- **An update broke something:** restart, choose an earlier boot environment in the boot menu, and you are back where you were.
- **Anything else:** [open an issue](https://github.com/jordanhubbard/daemonarchy/issues) with what you did and what you saw.

## Going further

- [The hacking guide](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md): how Daemonarchy is built, how to change it, and how to build your own image.
- The source: [daemonarchy](https://github.com/jordanhubbard/daemonarchy) (the installer), [daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop) (Daemonarchy's look and FreeBSD tools) and [omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd) (what lets Omarchy run on FreeBSD).
- [Omarchy's manual](https://learn.omacom.io/2/the-omarchy-manual) for desktop concepts and shortcuts. Use Daemonarchy's [FreeBSD application policy](freebsd-application-policy.md) for platform-specific software and commands.
- [The FreeBSD Handbook](https://docs.freebsd.org/en/books/handbook/) for the operating system underneath.
