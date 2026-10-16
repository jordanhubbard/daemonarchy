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
| Foot, imv, mpv, Disk Usage and ported Omarchy applications | Native FreeBSD packages |
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
Cursor/OpenCode first-run Linux downloaders are disabled until qualified. Cudalab
remains an optional hardware qualification item and is not installed or advertised
by the default desktop package.

Validation covers the actual upstream 4.0.4 menu, router dispatch and exit status,
unsupported command guards, existing-user MIME/Docker migration, and real native
FreeBSD GIO process launches with quoted options and URLs containing percent,
quote, dollar and backtick characters. Package manifests and full installed desktop
checks are separate release gates; passing these tests alone is not a GUI or
Linuxulator acceptance claim.
