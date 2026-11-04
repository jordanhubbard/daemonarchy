# Visual SDK

`daemonarchy_visual` draws, animates, reads input actions and asks for sound
cues. The installer is its first consumer; `sdk/visual/examples/sample_host.py`
is a second host that has nothing to do with installation. The SDK keeps no
installation state and performs no privileged operation: a host passes in
observations and decides what an action means.

The extraction is complete only when every installer-owned renderer, animation
and effect uses this public surface. Toolkit integrations such as terminal
widgets or the live desktop's graphical frontend may implement an SDK backend
or host adapter, but they do not define a private presentation API beside it.
Temporary audited escape sites must either migrate behind that boundary or be
removed before VISUAL-SDK-001 can close.

API version 1.3 (the extension bundle module needs no API change). `daemonarchy_visual.compatible("1.0")` tells a host or plugin
whether this SDK can serve the version it was written for. A minor release only
adds names; a major release may remove or change them, and the old major keeps
working in an installed image until that image is replaced.

## The model

| Piece | Module | What it is |
| --- | --- | --- |
| Capabilities | `caps` | `detect()` negotiates color depth (`none`, 8, 16, 256, truecolor), glyph set (Unicode or ASCII), reduced motion, plain (serial, dumb terminals, pipes) and size. Nothing is silently approximated: a host reads the result. The FreeBSD `vt(4)` console never gets 256-color or truecolor sequences. |
| Palette | `palette`, `glyphs` | named palettes, `gradient`, `Colors(depth).sgr(style)`, `Glyphs(unicode)` with an ASCII twin. |
| Canvas and screen | `canvas` | `Canvas` (text, fill, lines, boxes, sprites, bars, clipped), `Screen` (writes only changed cells, clears on resize, never writes the bottom-right cell, restores the terminal; `alt=True` uses the alternate screen; `full=False` with `origin` and `size` is an overlay that animates part of a screen the host printed and leaves the cursor alone). |
| Layout | `layout` | `Rect` with `inset`, `split_h`, `split_v`, `centered`. |
| Motion | `timeline`, `effects` | injected clocks (`MonotonicClock`, `ManualClock`), `Tween` with easing, `Timeline` callbacks, seeded `Particles` and `Fireworks`, typed text, gradient text. |
| Input | `input` | `decode_keys` (bytes to keys), `KeyMap` (keys to actions), `FdSource` (non-blocking reads), `ListSource` (scripted input for tests). Actions: `up down left right fire pause select back quit mute help`. |
| Audio | `audio` | `Audio.cue(name)` never blocks, never raises, is never required, and honours mute. `ThreadedAudio` wraps a blocking backend with a bounded queue. Standard cues: `click select blip laser hit explode bounce pickup levelup gameover win`. |
| Inline effects | `inline` | line-oriented flourishes printed between a host's own prompts: `type_line`, `result_line`, `pulse_line`. Plain terminals and reduced motion get the final text at once. |
| Arcade helpers | `arcade` | a fixed simulation step, a centered playfield, a HUD that compacts on narrow terminals, banners. |
| Plugins | `plugin` | content-identified, capability-scoped, preemptible, failure-isolated scenes that run in their own process; see [installer-extensions.md](installer-extensions.md). |
| Windows | `windows` | extra windows for extensions: open, close, resize, select, list and set a title, mediated by the host; tmux, inline-panel and refusing backends. See below. |
| Scenes | `scene` | `Scene` (`update`, `draw`, `plain_lines`) and `run_scene`, which owns timing, input, resize, pause, mute, preemption and restoring the terminal. |

## Behaviour a host can rely on

- **Plain terminals** (serial, dumb, pipes, `DAEMONARCHY_CHARM=off`) get
  `Scene.plain_lines` once; no cursor addressing is sent.
- **Reduced motion** (`DAEMONARCHY_REDUCED_MOTION=1`) is visible to scenes as
  `ctx.reduced`; the SDK's own effects stop animating and scenes should too.
- **Small terminals** (under 40 columns or 16 rows, or below a scene's `min_size`) show
  "Terminal too small" and the size needed instead of the scene, and the scene is not updated.
- **Preemption**: `run_scene(..., preempt=fn)` stops at the next frame when `fn()`
  is true. A scene cannot refuse. Hosts use this for prompts, errors and completion.
- **Long stalls** (a suspended window) are clamped to 0.1 s of simulation.
- **Sound** is a request: mute, no device, serial and SSH all mean silence, and
  nothing in the SDK waits for it.

## Windows for extensions

An extension (a plugin in its own process) can ask for windows. It never talks to tmux or the
terminal: it queues requests with `ctx.windows`, the host validates and performs them, and the
answers come back as events on a later tick.

| Verb | `ctx.windows` call | Result |
| --- | --- | --- |
| open | `open(title, cols, rows)` returns a reference | event `opened` (`ref`, `w`, `cols`, `rows`) or `refused` |
| close | `close(w)` | event `closed` (`w`, `by`) |
| resize | `resize(w, cols, rows)` | event `resize` |
| select | `select(w)` makes it the shown window (`0` is the run's own window) | event `selected` |
| list | `list()` returns a reference | event `list` with `windows: [{w, title, cols, rows, selected}]` |
| title | `set_title(w, text)` | none |

Events also arrive when the user closes a window (`closed`, `by: "user"`) or changes its size
(`resize`). A scene receives them through optional hooks: `on_window_event(event)`,
`window_actions(w, actions)` for input typed in a window, and `draw_window(w, canvas, ctx)` to paint
one (the canvas has the window's size). A test extension in `tests/sdk-windows.py` opens, resizes,
selects, lists, retitles and closes extra windows.

**What the host enforces**, whatever the extension asks: the `window` capability in the manifest
(without it every verb is refused with `no-window-capability`); at most `limits.windows` windows per run
(1 to 4, default 2); sizes of 20-200 columns by 6-60 rows; titles reduced to at most 40 printable
characters with shell metacharacters removed; at most 8 requests per tick; and ownership: only
windows it opened, plus window 0 for select, list and title (it cannot be closed or resized, because it is
the terminal). tmux window ids come from tmux and are held by the host; the extension never supplies or
sees one, so the installer's own windows cannot be addressed.

**Backends**, chosen by `windows.choose_backend(caps)`:

- `TmuxBackend`: each window is a tmux window running a viewer (`window_view.py`) that the host feeds
  validated frames over a private unix socket (a 0700 directory). Only `new-window`, `resize-window`
  (with `window-size manual`), `select-window`, `rename-window`, `kill-window` and `list-windows`
  are used, only on windows this host created. A resize event is reported only after the window has
  settled at its requested size, so startup noise is not mistaken for a user resize.
- `InlineBackend`: no tmux. Windows are framed panels drawn inside the one terminal with a z-order;
  `select` brings one to the front and the front panel receives the keyboard. This is a genuine
  degradation and is shown as one.
- `NoWindows`: serial, plain or headless. Every `open` is refused with the reason `no-windows`.

Each extension run is meant to have its own window (a new tmux window, like `new-window`);
`TmuxBackend.spawn(title, argv)` does that for a launcher, and on the inline backend the run takes over
the one terminal.

## The installer is the first consumer

The install screen (`progress-dashboard.py`) draws every frame through `Canvas` and
`Screen`, takes color depth, glyphs, palettes, gradients and key decoding from the SDK,
and keeps no private copy of them. The flourishes (`charm.py`: title typing, result
sparkles, the disk warning pulses, the first-boot celebration and the welcome
animation) are built on `inline`, `Fireworks`, scenes and an overlay `Screen`. The
mascot art and the installer's layout stay installer content; how they are drawn is the
SDK's. `tests/visual-sdk.py` fails if the installer defines its own `Canvas`, `Colors`,
`Glyphs`, `Fireworks`, `color_depth`, `gradient` or `decode_keys` again. Prompts are
`gum` forms, a third-party tool outside this SDK; the SDK draws what surrounds them.

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
loop (pause, mute, preempt, resize, stall) and the sample host. The window tests (27) also run against a real tmux
server. All three suites (42 SDK, 71 plugin/game, 27 window tests) pass on FreeBSD 16.0-CURRENT with tmux 3.7c, and a plugin
started as root runs as uid/gid 65534 with no groups, in `/`, unable to write or fork. Not yet verified: a FreeBSD `vt(4)` console
or serial/SSH on real hardware.
