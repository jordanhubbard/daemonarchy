# Sandboxed Lua extensions

Status: implemented for the 1.4.2 branch (SDK API **1.5**), additive to the 1.4.1 extensions. Nothing about
the four Python games, the feed, the menu or the installer's trust model changes.

[Installer extensions](installer-extensions.md) run Python that we sign and ship from our own feed, in a
process that is limited but is "not a sandbox for hostile code". This adds a second kind of extension for
content we may not have written: a **Lua entry file inside a real sandbox**. It goes through the same manifest,
the same signed feed and bundle checks, the same menu, window, preemption and mute rules; only the runner
differs. It is how a community could publish a toy or a game from a release page without the installer having
to trust their code.

## What an author writes

A manifest as for any extension, with `"entry": "name.lua"`, `"api": "1.5"` and a type, plus capabilities from
`draw`, `input`, `audio` (`window` is refused for Lua). A Lua extension defines `init()` and `tick(dt)` and sees:

- a fixed **64x40 pixel surface**, 16 colours, colour 0 transparent; `W` and `H`; `gfx.clear()`,
  `gfx.pixel(x, y, c)`, `gfx.rect(x, y, w, h, c)`;
- `input.held(name)` for `left`, `right`, `up`, `down`, `fire` (also `space`) and `select`;
- `sfx.blip(freq, ms, wave, vol)`: a synthesized tone, `wave` one of `sq`, `tri`, `noise`;
- `math`, `string`, `table` and the basic functions. Nothing else.

The host draws the surface as half-blocks (two pixels per terminal row), scaled by whole numbers and centred.
Minimum 64x22 cells; below that the loop shows its usual "terminal too small". ASCII terminals get `#`.

## The sandbox

Python cannot sandbox code in-process, so each extension is a **separate process** (`flua` on FreeBSD, `lua`
elsewhere) owned by the host (`daemonarchy_visual/lua.py`):

- `lua -E`, empty environment, `/` as its directory, a new session, stdout the only channel, stderr discarded;
- limits set before it starts: `nice +10`, address space (the manifest's `memory_mb`), 16 descriptors, no file
  writes, no core files; run as root it drops to `nobody` and refuses to start otherwise;
- inside Lua (`sandbox.lua`): no `os`, `io`, `require`, `load`, `dofile`, `debug`, `getmetatable`, `pcall` or
  coroutines; source only (precompiled chunks are refused); an instruction budget per tick; `string.rep` capped
  and `string.dump` removed;
- the host treats the output as hostile: every line is validated and clamped (96 bytes a line, 4096 operations
  and 256 KiB a frame, 16 malformed lines at most), the frame has the manifest's `frame_ms` deadline, and the
  process group is killed on any breach.

The in-Lua restrictions are the second wall. The first is the process boundary, the limits and the host's
validation. A crash, hang, flood or escape attempt ends the extension as a failed result
(`{"failed": reason}`), the same as a Python extension; the host and the installation carry on. Next step on
FreeBSD is capability mode (`cap_enter`) in the child, so even an escape from Lua has no filesystem or network
access; it needs the real image to test.

## Sound

`sfx.blip` becomes `Audio.blip(freq, ms, wave, volume)` (new in this SDK level), beside the named cues. The Extensions
launcher routes it to the installer's player as a `blip` datagram (`sound.py`). Blips play only in mode `on`:
`quiet` keeps the moments that matter and a toy is not one; `off`, mute and a missing device are silent. Values
are bounded (30-8000 Hz, 5-400 ms, loudness never above a cue's), non-finite or mistyped values are refused, the
client allows 20 a second (burst 8), the player sounds at most 4 blips and 12 voices at once and drops the rest
rather than queueing them, and rendered blips are cached under a 64-entry cap.

## Input

Terminals report key repeat but not release, so an action counts as held for 0.40 s after the first press and
0.12 s after later repeats. Without the `input` capability the extension sees nothing.

## What ships

| Path | What |
|---|---|
| `daemonarchy_visual/lua.py`, `sandbox.lua` | surface, protocol, sandbox host, held keys, the scene |
| `daemonarchy_visual/audio.py`, `plugin.py` | `Audio.blip`; `.lua` entries and their manifest rules; dispatch to the Lua scene |
| `overlay/.../daemonarchy-extensions`, `sound.py` | the tone route to the player; the `blip` message |
| `extensions/games/fishtank/` | a first Lua extension, type `animation` ("Visuals" in the menu): fish chase food (space) |
| `tests/lua-extensions.py` | 30 tests: surface, protocol, sandbox escapes and limits, blip sound, the registry path |

## Not done yet

1. `cap_enter` hardening, and a check on the real image that `flua` exists (assumed from FreeBSD base) and that
   `RLIMIT_AS` and the root-to-`nobody` drop behave there.
2. A real-console check: block characters in `vt(4)`, key repeat over tmux and serial.
3. A read-only "progress" capability (a critter that walks along the real progress bar), if wanted.
4. Publish the fish tank in the feed (it is sealed in `extensions/games/index.json` but the feed is staged by
   `scripts/extension-bundle.py` as usual); more Lua toys and a third-party authoring guide.
5. Decide whether third-party content is signed with the package-repository key (as now) or a separate key so a
   plugin key compromise cannot sign packages.

## Risks

- Lua sandbox escapes: process isolation, limits and host validation come first; capability mode is next.
- CPU on slow hardware: `nice +10`, a frame cap and a deadline; the installation preempts it at any frame.
- Console font coverage of block characters: `vt(4)` has them and there is an ASCII fallback.
