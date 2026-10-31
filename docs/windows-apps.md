# Windows programs and Steam

Status: planned for the 1.4.2 release; not yet released. The launchers are in the
repository, tested against stand-ins, and have not run on real hardware.

Daemonarchy on amd64 plans an Apps menu entry for **Steam** (the Windows client,
running under Wine) and one for **Windows Programs** (Wine itself). They follow the
pattern of [Cudalab](freebsd-application-policy.md): *virtual apps*. Nothing of
Wine's or Valve's is on the image or in the default package set, so installation time
and the ISO stay as they are.

## How it works

`daemonarchy-steam` and `daemonarchy-wine` are launchers in `/usr/local/bin`. The
installer puts them, their desktop entries (`Steam`, `Windows Programs`), icons and the
System > FreeBSD menu entries in the new system **on amd64 only**; on aarch64 the
entries are removed and the launchers refuse to run.

The first launch opens a window (no terminal needed) that:

1. installs `wine-devel`, `wine-mono-devel`, `wine-gecko-devel` and `winetricks` from the
   system's configured package repositories with `sudo pkg install` (one password prompt,
   in that window, and a network connection);
2. creates the user's Wine prefix in `~/.local/share/daemonarchy-wine/prefix`;
3. for Steam, downloads Valve's own `SteamSetup.exe` over HTTPS at that moment, prints its
   sha256, runs it silently in the prefix and records that Steam is installed.

Every later launch goes straight to Wine or Steam: no window, no sudo, no download (Steam
updates itself, as it does on Windows). If the first run fails, usually because the
machine is offline, the window says why and waits for Enter; the log is
`~/.local/state/daemonarchy-wine/setup.log` and the next launch tries again.

```
daemonarchy-steam [steam://URL | ARG...]     open Steam
daemonarchy-wine [PROGRAM.exe | PROGRAM.msi] run a Windows program (no argument: Wine's file manager)
daemonarchy-wine --steam ...                 what daemonarchy-steam runs
daemonarchy-wine --status                    what is set up
daemonarchy-wine --setup                     set up now and open nothing
daemonarchy-wine --rebuild                   forget the setup record and set up again
daemonarchy-wine --reset [--yes]             delete the Wine prefix and everything in it
```

`daemonarchy-steam` accepts `--status`, `--setup`, `--rebuild` and `--reset` too. Steam
starts with `-no-cef-sandbox` (what the commonly documented Wine setups use);
`DAEMONARCHY_STEAM_ARGS` replaces that list, for example to add `-cef-disable-gpu` if the
Steam window stays blank.

`wine-devel` is built for both 32-bit and 64-bit Windows programs (Wine's WoW64 mode),
so no 32-bit FreeBSD libraries are installed. On the build VM (kernel
`16.0-CURRENT #3 303b3646270f`), the upstream `wine-devel-11.20,1` ran a 64-bit and a
32-bit (`syswow64`) console program.

## What Daemonarchy does not do

- It does **not** ship, host or mirror Wine, Mono, Gecko, Steam or any Windows program.
  The four packages come from the repositories the installed system already uses, so the
  application feed, the closure feed and the ISO do not change.
- It does **not** ship Valve's client, installer, logos or marks. The Steam entry uses its
  own icon. The Steam Subscriber Agreement and Valve's installer terms apply to the
  downloaded client and to the games, between the user and Valve.
- Linux Steam through the Linuxulator (`games/linux-steam-utils`) is out: the
  [application policy](freebsd-application-policy.md) requires a retained,
  version-specific Linuxulator receipt, and there is none.
- No DirectX-on-Vulkan layer is packaged (there is no `dxvk` or `vkd3d` package for
  FreeBSD). Wine's built-in translation runs the games. `winetricks dxvk` fetches DXVK
  from its authors if the user asks; it is neither tested nor supported here.

## Licences and the source offer

| Component | Licence | Source |
| --- | --- | --- |
| `wine-devel` | LGPL 2.1 / LGPL 3 | https://dl.winehq.org/wine/source/ and the FreeBSD port `emulators/wine-devel` |
| `wine-mono-devel` | MIT, GPL 2, LGPL 2 | FreeBSD port `emulators/wine-mono-devel` |
| `wine-gecko-devel` | MPL 2, GPL 2/3, LGPL 2.1/3 | FreeBSD port `emulators/wine-gecko-devel` |
| `winetricks` | LGPL 2.1 | FreeBSD port `emulators/winetricks` |
| Steam client, games | Valve's and the publishers' terms | not distributed by Daemonarchy |

Daemonarchy distributes none of these, so it carries no source obligation for them. The
packages are built and redistributed by the FreeBSD project; their corresponding source is
the port's distfiles, named in each package's `pkg info` record. The launchers and icons
in this repository are under the repository's licence.

## Not verified

These need the operator's hardware and have **not** been checked:

- A Windows game, and Steam, launching from the Apps menu on a fresh install of the final
  image on the MSI Raider 18 HX, including NVIDIA OpenGL and Vulkan under Wine, sound, and
  Steam's own updater and web view under Wine.
- The graphical Wine first-run window and the sudo prompt on a real desktop session.
- What Steam's window looks like and whether it is usable under Wine: the build VM has no
  display or GPU, so only the processes were observed (below), not the picture.

What was checked on the build VM (`16.0-CURRENT #3 303b3646270f`, headless, on a virtual X
display):

- The upstream packages install and run on this kernel (above).
- The real first run of `daemonarchy-steam --setup`: the Wine prefix was created, Valve's
  `SteamSetup.exe` (2.4 MB) was downloaded over HTTPS from `cdn.cloudflare.steamstatic.com`,
  its silent install put `Steam.exe` in the prefix, and the record was written. (Valve's
  installer writes `Steam.exe`, so the launcher looks for it without regard to case.)
- The first launch of Steam downloaded its own 242 MB update from Valve and exited with
  status 42, Steam's "start me again"; the launcher starts it again, up to three times. The
  next launch kept `steam.exe`, two `steamwebhelper.exe` processes and `steamservice.exe`
  running for 90 seconds, with only no-GPU and no-sound-device warnings from the VM.
- The launchers' state machine, flags, failure and retry paths run against stand-ins for
  `pkg`, `sudo`, `wine`, `curl` and the terminal (`tests/windows-launchers.sh`), and the
  installer's amd64-only placement runs in `tests/windows-apps-install.sh`.

Not run on the VM: the `sudo pkg install` step (the packages were already there) and any
game.
