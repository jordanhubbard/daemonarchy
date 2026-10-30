# Installer arcade

Four small original arcade games to play while the installation runs, built as
plugins on the [visual SDK](visual-sdk.md). They are homages to classic mechanics
with original names, code, art and generated sound: no ROMs, no copied assets.

| Game | Style | Controls | Needs |
| --- | --- | --- | --- |
| Hordeshot | fixed shooter: a cannon against a descending horde | left/right, space | 50x24 |
| Shatter | brick breaking: a paddle, a ball, a wall | left/right, space to serve | 42x24 |
| Rockdrift | asteroid field: a drifting ship, rocks that split, a wrapping screen | left/right turn, up thrust, space | 58x24 |
| Wyrm | growing serpent | arrows or WASD | 50x20 |

`p` pauses, `m` mutes, `q` leaves (back to the menu, then out). Below a game's
minimum size it says what size it needs and does not run.

## Opening it

- On the progress screen press `g`, or from any window press `C-b g`. It opens
  in its own tmux window named `games`.
- It needs the installer's tmux windows. Without them (a plain serial console, no
  tmux) pressing `g` says so; nothing starts. `DAEMONARCHY_GAMES=off` disables it
  everywhere.
- `daemonarchy-games list` shows the sealed games; `daemonarchy-games play ID` runs one.

## It never changes the installation

- A game is a separate low-priority process (`nice` 19) in its own window. It does
  not read installation state and cannot start, stop or alter anything; a test
  fails if the launcher names installer internals.
- The install screen asks it to stop by creating `/tmp/daemonarchy-games.preempt`
  (`DAEMONARCHY_GAMES_PREEMPT`) when the installation finishes or fails, or a
  remote-debug pairing request needs the operator. The launcher checks the file every
  frame, kills the game process at once and closes its window with a one-line
  notice. If a `games` window is somehow still open 1.5 s after the request, the
  install screen closes it. While the file exists, `g` refuses to open it; it is removed
  when the request clears.
- While another tmux window is showing, the game is suspended: no simulation, no
  drawing, no CPU.
- Sound goes through the installer's player and follows its mute, volume and
  quiet mode; game cues never play in quiet mode.

## How plugins are trusted and contained

A plugin is a directory with `manifest.json` and one entry file under
`/usr/local/share/daemonarchy-games`. The loader accepts a plugin only if
`index.json` lists the SHA-256 of its manifest and the manifest lists the SHA-256 of its
entry file; an unlisted or altered file, a link, a bad capability, an unsupported SDK API or
an out-of-bounds limit is refused with a reason (`daemonarchy-games list` prints them).
`python3 scripts/seal-games.py` rewrites the hashes after a change and `--check` (run in CI)
fails if they are stale. The games are shipped content of the signed image, so the hashes
identify content; they are not a separate signature.

Each plugin runs in its own process (`plugin_child.py`): memory, CPU time, open files and
file size (zero) are limited, forking is not allowed, and when started as root it drops to
`nobody` and refuses to run otherwise. It draws only to a virtual canvas and talks over a
pipe; the host owns the terminal and validates every frame. A crash, hang (three missed
frame budgets), oversized or malformed frame, or limit overrun ends the plugin as a failed
result and the host carries on. Capabilities are enforced on both sides: a plugin without
`input` is sent no actions and one without `audio` has its cues dropped. This is process
isolation for the plugin's bugs, not a sandbox for hostile code: the plugins are trusted,
verified content.

## Environment

Reduced motion stops blink and shake effects; 16-color and ASCII glyph modes are supported;
serial and plain terminals get a one-line message instead of a screen.

## Verification status

Unit and process tests on Linux (`tests/plugins-and-games.py`, 71 tests): every game's rules with
seeded random numbers; every game drawn at its minimum and larger sizes in Unicode, ASCII,
16-color and reduced-motion modes; the registry's refusals; the real child-process runner
(crash, hang, memory limit, stray output, write and fork attempts, preemption, suspension,
capability scoping); the launcher on a pseudo-terminal (menu, launch, quit, preempt,
too-small, disabled, plain); and the install screen's preempt control. Not yet verified on
FreeBSD: the privilege drop to `nobody`, the resource limits, tmux window suspension, or a
`vt(4)` console, and no game has been played on real hardware.
