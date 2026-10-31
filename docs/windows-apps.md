# Windows programs and Steam

Status: planned for the 1.4.2 release; not yet released. The launchers are in the
repository, tested against stand-ins and, headless, on the build VM; they have not run on
real hardware.

Daemonarchy on amd64 plans an Apps menu entry for **Steam** (the Windows client,
running under Wine) and one for **Windows Programs** (Wine itself, with a generic way to
install and run any Windows program you supply). They follow the pattern of
[Cudalab](freebsd-application-policy.md): *virtual apps*. Nothing of Wine's, Valve's or any
other vendor's is on the image or in the default package set, so installation time and the
ISO stay as they are. Steam is the one platform entry: no individual game or publisher has
one.

## How it works

`daemonarchy-steam` and `daemonarchy-wine` are launchers in `/usr/local/bin`. The
installer puts them, their desktop entries (`Steam`, `Windows Programs`), icons and the
System > FreeBSD menu entries in the new system **on amd64 only**; on aarch64 the
entries are removed and the launchers refuse to run.

The first launch opens a window (no terminal needed) that:

1. installs `wine-devel`, `wine-gecko-devel`, `winetricks`, `xwayland` and `vulkan-tools`
   from the system's configured package repositories with `sudo pkg install` (one password
   prompt, in that window, and a network connection), then runs the
   [graphics checks](#the-graphics-checks);
2. creates a **64-bit** Wine prefix in `~/.local/share/daemonarchy-wine/prefix` with no
   display and with Mono and Gecko off for that first boot
   (`WINEDLLOVERRIDES="mscoree,mshtml=" wineboot -i`, then `wineserver -w`), so Wine's
   download prompts for them cannot stop it;
3. installs **Wine Mono 10.4.1** from WineHQ's MSI (`wine msiexec /i wine-mono-10.4.1-x86.msi
   /qn`), downloaded over HTTPS and checked against the pinned sha256 (the one in the FreeBSD
   port's distinfo);
4. installs **DXVK 3.1.1** (Direct3D 8 to 11 on Vulkan), downloaded over HTTPS from its GitHub
   release and checked against the pinned sha256 (the digest GitHub records for the release
   asset): the 64-bit DLLs into `system32`, the 32-bit ones into `syswow64`, and
   `d3d8`, `d3d9`, `d3d10core`, `d3d11` and `dxgi` set to `native` in the registry;
5. for Steam, downloads Valve's own `SteamSetup.exe` over HTTPS at that moment, prints its
   sha256, runs it silently in the prefix and records that Steam is installed.

A download whose sha256 is not the pinned one is refused and not used. Wine Mono and DXVK
are downloaded at the first run from their authors; nothing of theirs is in this repository.

DXVK needs native Vulkan on NVIDIA (DXVK 3.x needs Vulkan 1.4), so by default
(`DAEMONARCHY_DXVK=auto`) it is installed only when the checks find that, and otherwise skipped
with the reason, and games use Wine's built-in OpenGL translation. `DAEMONARCHY_DXVK=yes` installs
it anyway and `DAEMONARCHY_DXVK=no` never does; to change the choice later, run
`DAEMONARCHY_DXVK=yes daemonarchy-wine --rebuild`.

Every later launch goes straight to Wine or Steam: no window, no sudo, no download (Steam
updates itself, as it does on Windows). If the first run fails, usually because the
machine is offline, the window says why and waits for Enter; the log is
`~/.local/state/daemonarchy-wine/setup.log` and the next launch tries again.

```
daemonarchy-wine install SETUP.exe [ARG...]  run an installer you supply, in the prefix, and wait for it
daemonarchy-wine run PROGRAM.exe [ARG...]    run a Windows program (a path in the prefix works too)
daemonarchy-wine [PROGRAM.exe | PROGRAM.msi] the same by file type (no argument: Wine's file manager)
daemonarchy-steam [steam://URL | ARG...]     open Steam
daemonarchy-wine --steam ...                 what daemonarchy-steam runs
daemonarchy-wine --check                     the graphics checks only
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
so no 32-bit FreeBSD libraries are installed. It is the upstream FreeBSD `wine-devel`
(11.20 when this was written), not `wine-proton`.

### Any other Windows program: `install` and `run`

`install` and `run` are the generic mechanism. You supply the installer or the executable;
Daemonarchy downloads and ships nothing for it. Rules that are the same for every program:

- What the program prints goes to a **log file** (`~/.local/state/daemonarchy-wine/programs/NAME.log`,
  one per program, trimmed at 1 MiB), and its input is `/dev/null`: the launcher runs it as
  `wine PROGRAM ARGS >> log 2>&1 < /dev/null`. Some launchers die on a pipe, and a terminal
  pipeline or the first-run window is a pipe, so the program never inherits one. Do not wrap the
  program in `| tee`: read its log instead.
- Extra arguments reach the program unchanged. An Electron or CEF based launcher usually
  wants `--no-sandbox` under Wine (`daemonarchy-wine run launcher.exe --no-sandbox`).
- `install` waits for the installer and says where its log is. A `.msi` goes through
  `msiexec /i`. `run` detaches when started from a terminal, so the terminal is free; set
  `DAEMONARCHY_WINE_FOREGROUND=1` to keep it attached.
- A path that is not a file on this system is taken as a Windows path inside the prefix:
  `daemonarchy-wine run 'C:\Program Files\Some Game\game.exe'`.
- The first call sets Wine up exactly as above, so `install` and `run` work from a fresh install.

### The graphics checks

`daemonarchy-wine --check` (and the setup) reports, and never refuses:

- the kernel (`uname -v`) and its OSVERSION: Daemonarchy's amd64 image is FreeBSD
  16.0-CURRENT, and the checks refer to the image's own kernel;
- that the `nvidia` and `nvidia-drm` kernel modules are loaded, and that the installed
  `nvidia-kmod` and `nvidia-drm-612-kmod` packages were built for this kernel (their versions end
  in its OSVERSION). The ISO builds both, with `x11/nvidia-driver` and `x11/linux-nvidia-libs`, for
  its own kernel (`ISO_ORIGINS` in `origins.sh`); this is the existing pinning, not a new one, and a
  module built for another kernel does not load;
- native Vulkan on NVIDIA (`vulkaninfo --summary` names an NVIDIA driver, and the API version is
  1.4 or later, which DXVK 3.x needs);
- that Xwayland is installed (the Hyprland session gives Windows programs an X server through it).

Each problem is a `WARNING:` line saying what will not work, in the window, in the log and in
`--check`'s exit status (1).

## What Daemonarchy does not do

- It does **not** ship, host or mirror Wine, Mono, Gecko, DXVK, Steam or any Windows program.
  The packages come from the repositories the installed system already uses; Wine Mono and DXVK
  come from their authors at the first run. The application feed, the closure feed and the ISO do
  not change.
- It does **not** ship Valve's client, installer, logos or marks. The Steam entry uses its
  own icon. The Steam Subscriber Agreement and Valve's installer terms apply to the
  downloaded client and to the games, between the user and Valve.
- It has no entry, setting or special case for any single game or publisher. A program you
  install keeps whatever terms its vendor gives it.
- Linux Steam through the Linuxulator (`games/linux-steam-utils`) is out: the
  [application policy](freebsd-application-policy.md) requires a retained,
  version-specific Linuxulator receipt, and there is none.
- DXVK is not a package (there is no `dxvk` or `vkd3d` package for FreeBSD), which is why it
  is fetched as above.

## Licences and the source offer

| Component | Licence | Source |
| --- | --- | --- |
| `wine-devel` | LGPL 2.1 / LGPL 3 | https://dl.winehq.org/wine/source/ and the FreeBSD port `emulators/wine-devel` |
| Wine Mono 10.4.1 (MSI from WineHQ) | MIT, GPL 2, LGPL 2 | https://dl.winehq.org/wine/wine-mono/ and the FreeBSD port `emulators/wine-mono` |
| `wine-gecko-devel` | MPL 2, GPL 2/3, LGPL 2.1/3 | FreeBSD port `emulators/wine-gecko-devel` |
| `winetricks` | LGPL 2.1 | FreeBSD port `emulators/winetricks` |
| DXVK 3.1.1 | zlib | https://github.com/doitsujin/dxvk |
| Steam client, games, any program you install | Valve's and the publishers' terms | not distributed by Daemonarchy |

Daemonarchy distributes none of these, so it carries no source obligation for them. The
packages are built and redistributed by the FreeBSD project; their corresponding source is
the port's distfiles, named in each package's `pkg info` record. The launchers and icons
in this repository are under the repository's licence.

## Example: a .NET and DirectX 11 game launcher

This recipe was contributed by Sam Sheridan, from his experience running EVE Online on
FreeBSD. It is documented here only as a worked example of the generic mechanism above: Daemonarchy
has no EVE Online entry, nothing of the game's or its publisher's is shipped, and the user
supplies the publisher's installer.

What worked for him, as he reported it:

1. Upstream `wine-devel` 11.20, **not** Valve's Proton fork of Wine, which crashed the game
   launcher.
2. Wine Mono, because the publisher's installer is a .NET program: the MSI from WineHQ,
   version 10.4.1, installed with `wine msiexec /i wine-mono-10.4.1-x86.msi /qn`.
3. DXVK 3.1.1 for Direct3D 11 on Vulkan, which is not a package: its release DLLs, 64-bit into
   `system32` and 32-bit into `syswow64`, with `d3d8`, `d3d9`, `d3d10core`, `d3d11` and `dxgi` set to
   `native`.
4. A 64-bit prefix created with no display and `WINEDLLOVERRIDES="mscoree,mshtml=" wineboot -i`
   followed by `wineserver -w`, so the Mono and Gecko download prompts do not block.
5. The publisher's installer, then the launcher it installs, started with its output going to a
   **file**: it dies on a pipe.
6. Underneath: the NVIDIA DRM and kernel modules built for the exact kernel (his was
   FreeBSD 15.1; on Daemonarchy it is the ISO's own 16.0-CURRENT kernel, which the ISO already
   builds the modules for), native Vulkan on NVIDIA's FreeBSD driver, and Xwayland on Hyprland.

With Daemonarchy, steps 2 to 4 are the first-run setup above, and the rest is:

```
daemonarchy-wine install ~/Downloads/the-publishers-setup.exe      # the user downloads it from the publisher
daemonarchy-wine run 'C:\path\to\the\launcher.exe' --no-sandbox     # if it is an Electron launcher
```

What we have **not** verified ourselves: that game, or its installer or launcher, which we have
not downloaded or run; that Sam's versions work together on 16.0-CURRENT; any DXVK rendering;
anything on NVIDIA hardware. What we did check is the mechanics, headless on the build VM (below):
Wine Mono 10.4.1 and DXVK 3.1.1 install from their pinned downloads, the prefix is 64-bit and
made without a display, and `run` logs to a file with a pipe on the launcher's own output. Where
his experience and ours differ (his kernel was 15.1), the checks above report what is actually
installed.

## Not verified

These need the operator's hardware and have **not** been checked:

- A Windows game, and Steam, launching from the Apps menu on a fresh install of the final
  image on the MSI Raider 18 HX, including NVIDIA OpenGL and Vulkan under Wine, DXVK
  rendering, sound, and Steam's own updater and web view under Wine.
- The graphics checks on a machine with the NVIDIA driver loaded (the build VM has none, so
  only the warning paths ran for real).
- The graphical Wine first-run window and the sudo prompt on a real desktop session.
- What Steam's window looks like and whether it is usable under Wine: the build VM has no
  display or GPU, so only the processes were observed (below), not the picture.

What was checked on the build VM (`16.0-CURRENT #3 303b3646270f`, headless, on a virtual X
display):

- The upstream packages install and run on this kernel: a 64-bit and a 32-bit (`syswow64`)
  console program ran under `wine-devel-11.20,1`.
- The real first run of `daemonarchy-wine --setup` with `DAEMONARCHY_DXVK=yes`: the 64-bit
  prefix was created, Wine Mono 10.4.1's MSI installed (`windows/mono/mono-2.0` present), DXVK
  3.1.1's DLLs went into `system32` and `syswow64`, and the five DLL overrides were set.
- `daemonarchy-wine run` on `C:\windows\system32\cmd.exe` and `C:\windows\syswow64\cmd.exe`
  logged their output to a file under `programs/`, with the launcher's own output a pipe.
- `daemonarchy-wine --check` on the VM, which has no NVIDIA GPU: Xwayland was found, and the
  missing modules, packages and Vulkan device each produced their warning, with exit status 1.
- The real first run of `daemonarchy-steam --setup`: Valve's `SteamSetup.exe` (2.4 MB) was
  downloaded over HTTPS from `cdn.cloudflare.steamstatic.com`, its silent install put
  `Steam.exe` in the prefix, and the record was written. (Valve's installer writes `Steam.exe`,
  so the launcher looks for it without regard to case.)
- The first launch of Steam downloaded its own 242 MB update from Valve and exited with
  status 42, Steam's "start me again"; the launcher starts it again, up to three times. The
  next launch kept `steam.exe`, two `steamwebhelper.exe` processes and `steamservice.exe`
  running for 90 seconds, with only no-GPU and no-sound-device warnings from the VM.
- The launchers' state machine, flags, failure and retry paths, the pinned-sha256 refusals, the
  graphics-check warnings and the log-file rule run against stand-ins for `pkg`, `sudo`, `wine`,
  `curl`, `vulkaninfo`, `kldstat` and the terminal (`tests/windows-launchers.sh`), and the
  installer's amd64-only placement runs in `tests/windows-apps-install.sh`.

Not run on the VM: the `sudo pkg install` step for `xwayland` and `vulkan-tools` was run by hand
from the upstream repository (the VM's own repositories do not carry them), and no game was run.
