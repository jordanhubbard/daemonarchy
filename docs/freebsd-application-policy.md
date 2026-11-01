# FreeBSD application and menu policy

Daemonarchy uses FreeBSD packages by default. Install and Remove > Packages open
OctoPkg, the graphical frontend to pkg. Chromium is a required desktop dependency,
including with the optional application bundle disabled.

The port's `freebsdize` pass adapts the upstream default menu before installation
and when linking a development checkout. The Daemonarchy vendor menu adds the
native boot-environment, snapshot, jail, bhyve, development and DTrace tools.
User extensions remain user-controlled.

| Upstream surface | Daemonarchy behavior |
| --- | --- |
| AUR and individual browser/editor/service/game/AI/development installers | Removed; browse the FreeBSD repository in OctoPkg instead |
| Docker application, database installer and passwordless Docker setup | Removed; no local Docker Engine is configured |
| Docker buildx, Compose and lazydocker desktop dependencies | Removed from the default development bundle |
| Arch development package-test and ydotool/uinput service installers | Hidden from command help and rejected before running; use native FreeBSD ports and input tools |
| AUR, Linux boot/hibernation, old Omarchy OS upgrade/reinstall and service subcommands | Hidden and rejected before package, service or disk operations; ordinary FreeBSD package updates remain available |
| Unqualified agent/dictation setup and fingerprint invitations | Not offered at first login; native packaged CLI tools remain independently available |
| Dictation and GPU screen-recording bar indicators | Removed from defaults/editor choices and filtered out of older layouts without changing saved user settings |
| Arch documentation and Omarchy release/community links | FreeBSD Handbook and Daemonarchy documentation/issues |
| Omarchy stable/RC/edge/dev selectors | Removed; system packages use the configured signed FreeBSD repositories |
| Plymouth, direct boot, factory reset, firmware updater, LUKS password action | Removed; these upstream paths target Linux boot/storage tooling |
| Upstream fingerprint/FIDO/SSH/security setup | Removed pending FreeBSD-specific implementation; use native system administration |
| NetworkManager DNS/QR and Linux hardware restart actions | Removed pending native replacements; Wi-Fi uses Daemonarchy's FreeBSD backend |
| Network panel DNS/band/QR controls and speed-test buttons | Hidden on FreeBSD; their NetworkManager and Linux-counter helpers are disabled |
| Network and disk benchmark menu items | Removed; upstream implementations depend on `/sys`, `findmnt` and other Linux interfaces |
| GPU screen recording, LocalSend sharing and crash capture | Removed until a native implementation is available |
| Linux-only browser/editor defaults, dead app shortcuts and automatic agent selection/download | Removed; no implied Linuxulator qualification |
| Browser web applications | Retained using the FreeBSD Chromium desktop entry through GIO |
| Browser theme enterprise-policy writer | Disabled on FreeBSD; changing a user theme does not request root access or change administrator-managed browser policies |
| Foot, imv, mpv, Disk Usage and ported Omarchy applications | Native FreeBSD packages |
| Windows programs and Steam (amd64 only; planned for 1.5.0, not yet released) | Virtual apps like Cudalab: launchers and menu entries only, Wine and Valve's client installed on first launch from the system's repositories and Valve's own download; see [Windows programs and Steam](windows-apps.md) |
| Unknown new upstream bundled application entries | Excluded until reviewed |

Native editor defaults use FreeBSD’s `hx` and `zedit` executables. Dead Docker,
Spotify, 1Password, Signal, agent and screen-recording shortcuts are removed.

Removed menu actions also become hidden, failing compatibility commands where
possible. They report that the action is unsupported before performing upstream
service, disk or download operations. Internal `omarchy-*` names remain for
ported components; the public command is `daemonarchy`.

A web service entry (Discord, WhatsApp, Zoom, and the other bundled sites) opens
its website; it does not install the vendor's Linux desktop client. The launch
path preserves desktop-entry options and URL argument boundaries without shell
interpretation. Browser behavior still needs hardware desktop acceptance.

Linux-only software requires a retained, version-specific native FreeBSD
Linuxulator receipt before inclusion: exact package/artifact and checksum, FreeBSD
and Linux userspace versions, actual launch and core-function results, and any
GPU/audio/network dependencies. A download, pkg origin, compatibility wrapper or
mocked test is insufficient. Moving `latest` Linux downloads are not defaults.
Cursor/OpenCode first-run Linux downloaders are disabled until qualified. Since
1.4.0, with a supported NVIDIA GPU the installer offers CUDA 13.2 and cudalab,
selected by default and downloaded over the network during installation; the
default desktop package alone neither installs nor advertises them. CUDA ran a
kernel on an RTX 5080 through the Linuxulator on the MSI Raider 18 HX; Unified
Memory crashes and is not supported.

cudalab is delivered as a virtual app, not a package, because it must be compiled
with CUDA inside the Linuxulator and a poudriere port cannot do that. The stable
launcher `daemonarchy-cudalab`, run as the desktop user with no sudo, chroot or
mount, checks out a pinned cudalab commit into the user's own
`~/.local/share/cudalab` (cudalab compiles in its source path and saves demo edits
into `examples/`), builds the Release preset with nvcc and SDL 3.2 in a first-run
window, records the build, and chain-launches it; later launches open the built
app directly. The installer's CUDA step runs the same builder
(`daemonarchy-linux-cuda prepare-cudalab USER`), and a failed build leaves the
virtual app in place to retry. The Linux SDL cannot reach FreeBSD sound devices and
cudalab refuses to start without an audio device, so the launcher runs it with
`SDL_AUDIODRIVER=dummy`; `LD_PRELOAD` of the UVM shim is given only to the Linux
executable, never to a native FreeBSD program. The same preload carries a small
fallback library (built by the launcher under the Linux gcc) that answers
`cudaMallocAsync` with `cudaMalloc` when CUDA reports the stream-ordered
allocator unsupported, as it does here with the UVM shim and no real `nvidia-uvm` (the
cause is the missing UVM layer, as for Unified Memory, not a down-rev driver); the
Choreograph demo needs it. Audio uses SDL's `pulseaudio,pipewire,dummy` driver list
and falls back to the silent driver, so a missing sound path never costs the user
the app.

Validation covers the actual upstream 4.0.4 menu, router dispatch and exit status,
unsupported command guards, existing-user MIME/Docker migration, and real native
FreeBSD GIO process launches with quoted options and URLs containing percent,
quote, dollar and backtick characters. Package manifests and full installed desktop
checks are separate release gates; passing these tests alone is not a GUI or
Linuxulator acceptance claim.


The current 1.4.0 release retains this policy, as did 1.3.1 and the 1.1.1 refresh. Since
1.1.1 the installer verifies package-file integrity and dependencies before
recording installation success, and the adoption helper checks the actual base and kernel against candidate
OSVERSION metadata before changing repository identities. These checks do not
convert an older base to the new snapshot. See the [1.3.1 release notes](release-1.3.1.md)
and the earlier [1.1.1 qualification record](testing-1.1.1.md) for each release's
exact package, image and runtime results.
