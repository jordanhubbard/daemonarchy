# Visual SDK

`daemonarchy_visual` draws, animates, reads input actions and asks for sound
cues. The installer is its first consumer; `sdk/visual/examples/sample_host.py`
is a second host that has nothing to do with installation. The SDK keeps no
installation state and performs no privileged operation: a host passes in
observations and decides what an action means.

API version 1.0. `daemonarchy_visual.compatible("1.0")` tells a host or plugin
whether this SDK can serve the version it was written for. A minor release only
adds names; a major release may remove or change them, and the old major keeps
working in an installed image until that image is replaced.

## The model

| Piece | Module | What it is |
| --- | --- | --- |
| Capabilities | `caps` | `detect()` negotiates color depth (`none`, 8, 16, 256, truecolor), glyph set (Unicode or ASCII), reduced motion, plain (serial, dumb terminals, pipes) and size. Nothing is silently approximated: a host reads the result. The FreeBSD `vt(4)` console never gets 256-color or truecolor sequences. |
| Palette | `palette`, `glyphs` | named palettes, `gradient`, `Colors(depth).sgr(style)`, `Glyphs(unicode)` with an ASCII twin. |
| Canvas and screen | `canvas` | `Canvas` (text, fill, lines, boxes, sprites, bars, clipped), `Screen` (writes only changed cells, clears on resize, never writes the bottom-right cell, restores the terminal). |
| Layout | `layout` | `Rect` with `inset`, `split_h`, `split_v`, `centered`. |
| Motion | `timeline`, `effects` | injected clocks (`MonotonicClock`, `ManualClock`), `Tween` with easing, `Timeline` callbacks, seeded `Particles` and `Fireworks`, typed text, gradient text. |
| Input | `input` | `decode_keys` (bytes to keys), `KeyMap` (keys to actions), `FdSource` (non-blocking reads), `ListSource` (scripted input for tests). Actions: `up down left right fire pause select back quit mute help`. |
| Audio | `audio` | `Audio.cue(name)` never blocks, never raises, is never required, and honours mute. `ThreadedAudio` wraps a blocking backend with a bounded queue. Standard cues: `click select blip laser hit explode bounce pickup levelup gameover win`. |
| Scenes | `scene` | `Scene` (`update`, `draw`, `plain_lines`) and `run_scene`, which owns timing, input, resize, pause, mute, preemption and restoring the terminal. |

## Behaviour a host can rely on

- **Plain terminals** (serial, dumb, pipes, `DAEMONARCHY_CHARM=off`) get
  `Scene.plain_lines` once; no cursor addressing is sent.
- **Reduced motion** (`DAEMONARCHY_REDUCED_MOTION=1`) is visible to scenes as
  `ctx.reduced`; the SDK's own effects stop animating and scenes should too.
- **Small terminals** (under 40 columns or 16 rows) show "Terminal too small"
  instead of the scene, and the scene is not updated.
- **Preemption**: `run_scene(..., preempt=fn)` stops at the next frame when `fn()`
  is true. A scene cannot refuse. Hosts use this for prompts, errors and completion.
- **Long stalls** (a suspended window) are clamped to 0.1 s of simulation.
- **Sound** is a request: mute, no device, serial and SSH all mean silence, and
  nothing in the SDK waits for it.

## Privilege boundary

The SDK does not import installer modules, read installation state, or touch
disks, packages or the network. `tests/visual-sdk.py` fails if a file under the
package names installer internals. Scenes see only a `Context`: capabilities,
colors, glyphs, audio and clock.

## Environment

`DAEMONARCHY_COLOR`, `NO_COLOR`, `DAEMONARCHY_GLYPHS`, `DAEMONARCHY_REDUCED_MOTION`,
`DAEMONARCHY_CHARM`, `DAEMONARCHY_CONSOLE`, `DAEMONARCHY_SOUND=off`.

## Verification status

Unit-tested on Linux with scripted input and a manual clock (`tests/visual-sdk.py`):
capability negotiation, drawing and diffing, motion, input decoding, audio, scene
loop (pause, mute, preempt, resize, stall) and the sample host. Not yet verified
on a FreeBSD `vt(4)` console or over serial/SSH on real hardware.
