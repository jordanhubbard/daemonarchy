# Installation logs and the rescue console

Development installers retain diagnostics on the target disk and install a
console rescue menu before the large desktop package transaction. Once the
base system has been extracted, the selected user and root both receive the
password chosen in the installer. The selected user's initial shell is
FreeBSD's `/bin/sh`; the installer changes it to bash after installing the
desktop packages. User credentials therefore work even if that transaction
is interrupted.

## Retained installation diagnostics

- `/var/log/daemonarchy-install.log`: installer output, including package
  output, streamed to the target while installation is running.
- `/var/db/daemonarchy/install/status`: `in-progress`, `failed` or `complete`.
- `phase` in that directory: the last recorded installation stage.
- `requested-user` and `ssh-requested`: nonsecret selections useful for
  distinguishing requested configuration from completed configuration.
- `exit-code` and timestamps: recorded for an ordinary failure or completion.
- `kernel-PHASE.log`: kernel-message snapshots at stage boundaries.

The directory and log are restricted to root. The installer does not copy its
answers file, plaintext passwords, password hashes or Wi-Fi credentials into
the diagnostic record. It synchronizes stage records to disk. A sudden reset
can still lose the most recent unsynchronized log writes; it leaves the
completion marker as `in-progress` unless configuration had already finished.

An ordinary failure records its exit status. A reset or power loss cannot
record an exit status, so `in-progress` on the next boot identifies an
interrupted installation without inventing a cause. The completion marker is
written only after account, desktop package and SDDM state checks pass, together
with a dependency check and checksum verification of every installed package.
The target pool is flushed before recording completion and again afterwards.
Package verification logs are retained as `package-integrity.log` and
`package-integrity.log.dependencies` in the diagnostics directory. These checks
detect incomplete package files; they do not prevent unexpected hardware resets.
It describes installation configuration, not a verified successful GUI boot.
Before exporting the target ZFS pool, the installer closes and waits for its
log writer, so logging does not keep the pool busy.

If interrupted before base extraction and recovery setup finish, the disk may
not yet be bootable. Boot the installer USB in that case. Remote pairing on
the installed disk needs bash; the installer installs it in a small transaction
before fetching and installing the full desktop. The local rescue menu and
shell use the base system and do not depend on bash, gum, SDDM or Hyprland.

## At the installed machine

For continuous remote evidence, 1.1.1 starts a bounded diagnostics collector
after an agent authenticates. Use `daemonarchy-debug snapshot` for current
state or `daemonarchy-debug observe` for a stream, and retain that stream on the
controlling computer before package repair or other reset-prone work. See
[continuous diagnostics](remote-agent-debug.md#continuous-diagnostics) for the
receiver, private log locations, retention limits and console-capture boundaries.
These tools work with the existing kernel; they cannot capture output after a
hard reset has stopped SSH.

On the first text console, an incomplete installation automatically shows:

```text
Daemonarchy rescue
  1. Open a local debugging shell
  2. Pair a remote debugging agent
  3. View installation and boot logs
  4. Try the graphical login again
  5. Reboot
```

No Return key is needed to reveal the menu. Before its first display, the
console waits for two seconds without new kernel messages, up to 15 seconds,
then sizes the font and clears the screen so late device probes do not leave
the menu scrolled out of view. Continued kernel logging cannot delay it longer.

Choose an action, then log in as root with the password selected during
installation. This authentication is required even though the menu is shown
automatically. Logs and the local shell remain available without networking.
Exiting the shell returns to the console's recovery flow.

Remote debugging uses the same temporary-key pairing as the installer:
confirm that the listener should start, tell the agent the displayed address,
port and server fingerprint, and approve the matching client-key fingerprint.
Press Enter or Ctrl-C in the listener to stop access. This does not enable
normal sshd or grant anonymous/password-free root access.

Option 2 changes to **Unpair remote debugging agent** while pairing state
exists, including stale state left by an unexpected reboot. Selecting it
requires the same root authentication, closes the listener and its SSH
connections, and removes approved keys and session state. The option then
returns to **Pair a remote debugging agent**; a new session requires fresh
approval. This also clears the “Another debug session is already active”
condition without manual file cleanup. An authenticated shell can run
`daemonarchy-debug unpair` for the same operation.

For a completed installation, the console waits up to 60 seconds for SDDM
and either its greeter or a Hyprland session process. It keeps monitoring while
those processes run. If they disappear for 15 seconds, the rescue menu appears.
Normal graphical login and its selected username remain configured as before.
The monitor detects missing/exited processes; it cannot identify every frozen
compositor or prove that the screen renders correctly. An authenticated root
can also run `daemonarchy-rescue menu` from another console at any time.

Rescue entry is recorded in `/var/log/daemonarchy-rescue.log`, with the latest
kernel snapshot in `/var/db/daemonarchy/install/rescue-kernel.log`.
The log-view option also displays current kernel messages and `/var/log/messages`.
The menu refuses to retry the desktop while the installation marker is
incomplete. It does not automatically repeat installation, alter partitions,
or discard existing files.

Older installed images need recovery support installed separately. Their
original installation log cannot be recovered by adding these tools later.

## Checks

Run `bash tests/install-diagnostics.sh` and `bash tests/rescue-console.sh` for
log streaming/drain, interrupted-state handling, GUI startup/crash timeout and
the authentication gate before remote pairing and unpairing, including the
option-2 toggle. On FreeBSD as root,
`bash tests/rescue-setup.sh` checks the actual getty/profile installation.
`bash tests/remote-debug-session.sh` exercises actual SSH revocation, fresh
pairing approval, stale-PID safety and protection of a replacement session from
an older listener's cleanup.

`tests/rescue-boot-image.sh /new/output /path/base.txz /snapshot/root` builds
a disposable FreeBSD boot image using the production recovery/account/logging
helpers. It leaves the installation marker incomplete and includes a public
fixture-only password. Run the image under UEFI QEMU with a serial console to
check boot-to-menu, password rejection/acceptance, the selected user's login,
and viewing the retained log. The fixture redirects the ttyv0 profile guard
to ttyu0 for automation; this does not qualify a physical VGA console, GUI
rendering, or a full desktop installation.

Recorded on 2026-10-15: the FreeBSD setup, persistent logging and console unit
checks passed. A disposable snapshot-based guest booted under UEFI QEMU to
the incomplete-install menu. It rejected an incorrect root password, accepted
the fixture's installation password, authenticated `jkh`, displayed package
output retained across boot, and refused desktop retry while incomplete.
Changing the fixture marker to complete with no graphical login running
produced the rescue menu after the startup grace period. The native image
builder also exported its ZFS pool successfully after draining the log writer.
The rescue-history/kernel-record additions were checked separately in the
console tests. Physical ttyv0 and a real failed graphical session still need
qualification with a rebuilt installer image.
