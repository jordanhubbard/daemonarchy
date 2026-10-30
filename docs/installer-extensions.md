# Installer extensions

Extensions are optional extras that do work inside the installer when you choose them. The four arcade
games are the first, and the proof that the design works: they are built on the [visual SDK](visual-sdk.md),
loaded as plugins, and **downloaded from GitHub when chosen, not carried on the install media**. How they are
published and verified is in [extension-feed.md](extension-feed.md).

| Game | Style | Controls | Needs |
| --- | --- | --- | --- |
| Hordeshot | fixed shooter: a cannon against a descending horde | left/right, space | 50x24 |
| Shatter | brick breaking: a paddle, a ball, a wall | left/right, space to serve | 42x24 |
| Rockdrift | asteroid field: a drifting ship, rocks that split, a wrapping screen | left/right turn, up thrust, space | 58x24 |
| Wyrm | growing serpent | arrows or WASD | 50x20 |

They are original: names, code, art and generated sound, with no ROMs and no copied assets. `p` pauses,
`m` mutes, `q` leaves. Below a game's minimum size it says what it needs and does not run.

## The Extensions menu

It lists what the feed offers, grouped by category (Games, Tools, Visuals), with each extension's **name,
description, size, source and whether the network is needed**, and runs what you choose. It is reachable from:

- the installer's welcome and options screen: **Extensions (games and tools, downloaded when chosen)**;
- the progress screen: `x` for the menu, `g` for the menu at Games;
- any tmux window: `C-b e` (menu) and `C-b g` (Games).

Choosing an extension that is not yet downloaded fetches its compressed bundle (size and source are shown
first), verifies it, and only then runs it. Extensions already downloaded are marked `cached` and need no network.
Everything is kept in `/tmp` of the live environment (`DAEMONARCHY_EXTENSIONS_CACHE`) and is not installed
onto the target system.

**Network.** Listing the feed and downloading need the network. Offline, the menu says so, offers what is already
downloaded, runs nothing it cannot verify, and says to configure the network from the installer options. An image
without a pinned repository key, or without a release version, says extensions are unavailable and asks the
network for nothing. `DAEMONARCHY_GAMES=off` turns the whole thing off.

**Every run gets its own window.** In the installer's tmux session an extension opens in a new tmux window named
after it (the menu stays in its own window; `C-b w` lists windows, `C-b 0` returns to progress). Without tmux it
runs in the same terminal and returns to the menu. An extension with the `window` capability can ask for extra
windows of its own through the SDK ([Windows for extensions](visual-sdk.md)): open, close, resize, select, list
and title, mediated by the host and bounded; the installer's own windows can never be addressed.

## Installation is authoritative

- An extension is a separate low-priority (`nice` 19) process in its own window. It does not read installation
  state and cannot start, stop or change progress, prompts or the outcome; a test fails if the launcher names
  installer internals.
- The install screen asks extensions to stop by creating `/tmp/daemonarchy-games.preempt`
  (`DAEMONARCHY_GAMES_PREEMPT`) when the installation finishes or fails, or a remote-debug pairing request needs
  the operator. Every extension window checks it each frame and the process is killed at once, closing its extra
  windows with it; a lingering menu window is closed by the install screen 1.5 s after the request. While the file
  exists the menu will not open; it is removed when the request clears.
- While another tmux window is showing, an extension is suspended: no simulation, no drawing, no CPU.
- Sound goes through the installer's player and follows its mute, volume and quiet mode (game cues never play in
  quiet mode).

## How extensions are trusted and contained

Trust comes from the signed index and the bundle's own signature, both checked against the public key the image
already pins for its package repository ([extension-feed.md](extension-feed.md)). Once downloaded, an
extension is a directory with `manifest.json` (schema `daemonarchy/extension@1`: id, name, version, **type**
(game, tool, animation, visualizer), API, entry file and its SHA-256, **capabilities** (`draw`, `input`, `audio`,
`window`), minimum size, limits) that the plugin registry loads only if a local index names the manifest's hash and
the manifest names the entry file's hash; a link, an unlisted or altered file, a bad capability, an unsupported
API or an out-of-bounds limit is refused with a reason.

Each extension runs in its own process: memory, CPU time, open files and file size (zero) are limited, forking is
not allowed, and as root it drops to `nobody` and refuses to run otherwise. It draws to a virtual canvas and talks
over a pipe; the host owns the terminal and validates every frame. A crash, a hang (three missed frame budgets), a
malformed or oversized frame or a limit overrun ends the extension as a failed result and the host carries on.
Capabilities are enforced on both sides: without `input` it is sent no actions, without `audio` its cues are
dropped, without `window` every window request is refused. This is process isolation for an extension's bugs,
not a sandbox for hostile code: extensions are signed content from our own feed.

## Adding an extension

Put its directory under `extensions/` with a `manifest.json`, seal it (`scripts/seal-games.py` seals the games;
`plugin.seal_manifest` does one directory), and add it to the feed with `scripts/extension-bundle.py` (see
[extension-feed.md](extension-feed.md)). It appears in the menu once the feed is published and the image can
reach it; nothing in the ISO changes.

## What the installer still draws outside the SDK, and the decision

The installer's own screens draw through the visual SDK: the progress screen, every flourish, the welcome frame
and the logo, the log and diagnostics views, and this menu. `tests/installer-sdk-audit.py` allows only the
hand-written terminal escapes listed here and fails on any new one. What remains outside, and why:

| Outside the SDK | What it is | Decision |
| --- | --- | --- |
| `gum` prompts (about 50 uses in `configurator`: choose, input, confirm, spin, style, table) | the installer's forms: disk, network, account, Wi-Fi, firmware, sound | **Keep for 1.4.1.** They are a third-party widget layer with tested line editing, secret entry and keyboard handling on the console, and replacing them rewrites every setup form in the install path; the risk is not justified in a patch release. The SDK draws everything around them. A follow-up (EXT-001) is an SDK form layer (choose, input, secret, confirm) that replaces one screen at a time, starting with the screens that have no secret input. |
| `ttfx` colorshift on the welcome screen | an optional third-party text effect that runs only when installed | Keep; the SDK's own attract animation runs when it is absent. |
| The install log's colour prefix (`install`'s `log()`) | a log line format the progress screen parses and strips | Keep; it is a protocol, not a screen. |
| Coloured status dots in the network menu's labels | item text inside a `gum` choice | Goes with the `gum` decision. |
| The live desktop's graphical installer (GTK) | a separate toolkit for the desktop session | Out of scope for a terminal SDK; it shares the installer's rules, checks and answer file, not its drawing. |
| `sound.py` | the audio backend and daemon | It is the backend the SDK's audio cues use through an adapter; the installer's own sounds call it directly, which is a backend rather than a rendering path. |

## Verification status

Linux: `tests/installer-extensions.py` (22 tests: a signed feed served locally, the menu and launcher on a
pseudo-terminal, download-on-choose, the cached second run, offline, wrong key, missing key, tampered bundle,
undersized terminal, preemption, and the real tmux own-window launch), `tests/extension-bundles.py` (27),
`tests/sdk-windows.py` (27), `tests/plugins-and-games.py` (58), `tests/visual-sdk.py` (43), `tests/installer-sdk-audit.py` (8) and the installer
progress tests (54). FreeBSD 16.0-CURRENT (daemon.local, tmux 3.7c): the window, SDK and plugin suites pass and a
plugin started as root runs as `nobody`, unable to write or fork. Not verified: a `vt(4)` console or serial/SSH
on real hardware, the published feed on GitHub (it is staged, not yet published), or any extension played on
real hardware.
