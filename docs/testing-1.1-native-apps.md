# Native desktop application checks, 2026-10-15

These checks used a disposable snapshot of the preview.11 UEFI installation,
upgraded to `omarchy-4.0.4_14`. A temporary Xorg/scfb/Xfce session provided a
visible test surface in QEMU. Xfce is not a Daemonarchy session or a proposed
fallback: Hyprland remains required for VM acceptance.

| Native FreeBSD package | Result |
| --- | --- |
| Chromium 154.0.8037.57_1 | `omarchy-launch-webapp` opened and rendered a page served over loopback; the HTTP server recorded a successful request |
| OctoPkg 0.4.1 | Opened, refreshed the configured FreeBSD and Daemonarchy repositories, searched the FreeBSD collection, and installed `games/cowsay` 3.04_3 through its GUI |
| qt-sudo 2.4.1 | Displayed the actual password dialog and successfully authenticated the disposable test account for both repository refresh and package installation |

The installed package database independently confirmed the OctoPkg transaction.
Chromium used an isolated test profile with `--no-first-run`; no browser terms
were accepted and no user browser defaults were changed. Its desktop entry was
cloned only to add those test-profile flags; the packaged web-app launcher and
native Chromium executable handled the launch.

The first UI input attempt failed because the temporary Xorg fixture lacked
`xf86-input-libinput`. Installing that native driver restored QEMU keyboard
input. This is fixture evidence, not a Hyprland input qualification.

Screenshots, exact package versions, HTTP request output and the independent
privilege-handoff result are retained in the local
`2026-10-15-preview12/native-apps` evidence directory. Menu policy, browser
argument handling and first-run home preservation also have native automated
coverage in `omarchy-freebsd`. Physical desktop integration, Hyprland VM
rendering and an installation of the complete new ISO remain separate gates.

## Hyprland integration follow-up, 2026-10-16

The signed development-profile QEMU desktop and disposable copies of the fresh
UEFI plain/GELI installs subsequently passed real Hyprland keyboard/pointer
input, Chromium page rendering and the OctoPkg UI. Plain installation exercised
SDDM password login; GELI exercised password unlock and the configured desktop
autologin. These are development-authority results, not final production-image
qualification.

Fresh installs exposed a Linux-only browser enterprise-policy theme helper
requesting administrator authorization despite having no applicable policy
directories. Compatibility revision `aab8d9c385d23ca2ede9b6efd20855fc26682341`
disables that unsupported write on FreeBSD and corrects the welcome menu label.
All eight `test_desktop_defaults.py` checks passed natively on FreeBSD with this
source, including all three native GIO browser-launch cases. Its new package
still needs installation and first-run GUI qualification in the final image.

The subsequent command-help audit found Linux-only `dev install ydoo` and
`dev pkg test` routes. Compatibility revision
`59b5b191707c86ecf192920de0b714bb72f77fef` hides these routes and rejects direct
invocation before running their udev/uinput, systemd or Arch package operations.
All eight checks passed again natively, including real-router discovery and
direct unsupported-command guards. The final installed-system check now verifies
these exclusions before invoking the guarded commands.

The complete command audit then excluded Linux boot/AUR/OS-reinstall tools,
unqualified setup routes and raw sysfs-only probes from public discovery.
Compatibility revision `535e44bb6fa3e9b9f4fc3a870591688526279124` also removes
unsupported first-login invitations and dictation/screen-recording bar choices,
including filtering older saved layouts while retaining user-defined entries.
All nine native tests passed, including the actual QML settings functions.
The complete adapted installed catalogue exposed 231 routes, retaining the
portable battery, monitor-scaling, package and Hyprland helpers. A disposable
FreeBSD desktop loaded the two changed bar files, restarted Quickshell, reported
no Hyprland configuration errors and passed the graphical input/browser/package
manager checks again; a hover screenshot confirmed the unsupported indicators
were absent. This prototype precedes final production-image qualification.
