# Installer progress

The install screen shows what the installation is doing while it runs. Every
counter measures something real, and the two figures that cannot be measured, the
overall percentage and the time left, are labelled estimates and say what they
are built from. Only the installer's result file says whether the installation
succeeded.

## The header

The first rows are always visible, with the logo shown or not and at small
sizes, and say where the installation stands:

```
elapsed 0:12:34   stage 7 of 11: Download   ≈27% done (estimate)   about 0:31:20 left (estimate from measured rates)
packages 345 of 1,217 installed   downloaded 1.04 of 3.63 GiB at 1.8 MiB/s
```

| Figure | Kind | How it is made |
| --- | --- | --- |
| elapsed (H:MM:SS, running) | measured | from the first stage's start, using the installer's own clock in the `@@step` markers |
| stage N of M | measured | the stage list; M includes an optional stage the machine will run (CUDA on an NVIDIA GPU) from the start, so it does not change when that stage begins |
| packages X of Y installed | measured | X is the number of distinct packages pkg reports **extracted**, clamped to Y; Y is the plan's package count, or, until it exists, pkg's own `Number of packages to be installed` or `[n/N]` |
| downloaded A of B GiB | measured | A is the bytes received (`@@fetch`, summed across pkg runs, since each run restarts its counter); B is the plan's `download_bytes`. Until the plan exists B is pkg's rounded figure and is marked `≈`. When the download stage ends B becomes what was received |
| MiB/s | measured | bytes over the last ten seconds of real time; shown only after at least three seconds of samples |
| overall percent | **estimate** | each stage is weighted by what it took in a real install (the baseline below) and counts its measured progress inside it: bytes received, packages extracted, archives expanded. It only moves forward; an estimate revised downward holds until the work catches up. 100% only when the installer reports success |
| time left | **estimate** | per unfinished stage, what is left: the download from the average rate since it began, the packages from the average extraction rate, anything else from the baseline. The label says which: `estimate from measured rates` or `estimate from baseline`. Nothing is shown as known when no rate exists yet |

The baseline is a real complete install on an MSI Raider 18 (49.6 minutes, 824
archives and 3,721 MiB at 1.79 MiB/s, 1,217 packages): disk 0.6 s, base 12.6 s,
boot loader 0.1 s, configure 0.6 s, download 2,075 s, packages 152 s, account 31 s,
CUDA 691 s, finish 2 s. It is only the starting expectation; measured rates replace it.

The installer sends the totals once the package plan resolves, as one log line:
`@@plan {"schema":"daemonarchy/install-plan@1","packages":N,"archives":N,"download_bytes":B,"installed_bytes":I}`,
and the `@@fetch` lines carry bytes of that total. A malformed plan is ignored with a warning.
Until it arrives the screen falls back to pkg's own `Number of packages to be
fetched`, `N GiB to be downloaded` (not the figure printed for the small bootstrap
install that comes first) and `[n/N]` lines.

## The timeline

Each stage with when it started (offset from the first stage), how long it took or
has taken, and how long it is expected to take: what it took if done, a
measured-rate projection for the download and packages while they run, and the
baseline for stages still to come. A tall screen shows the table (STAGE, STARTED,
TOOK / ELAPSED, EXPECTED); a shorter one shows the same as chips (`Download
12:34/~34:35`, `Packages ~2:32`). `t` cycles auto, table and chips.

## The package ticker belongs to its phase

The ticker (the names pkg is processing and its `n/N`) is shown only in the phase that fed
it. After the install phase it is history and is hidden: it used to keep its last label,
"Installing 1,217/1,217", through the account, CUDA and verify stages, which took about
12 of the 50 minutes. Those stages show the latest log line instead, and the header keeps
the final package count. `tests/installer-progress-stats.py` replays a trimmed copy of that
real log, live, through the model and the dashboard, and fails on that symptom.

## What each element measures

| Element | Measures | Source |
|---|---|---|
| Stage timeline: Partition, Encrypt, ZFS pool, Base sets, Boot loader, Configure, Download, Packages, Account, (Checkouts, CUDA), Verify | The stage that is running, the stages finished, and each stage's elapsed time. Encrypt shows as skipped when the disk is not encrypted. Optional stages appear only when they run. | `@@phase` and `@@step NAME EPOCH` markers that `install` prints when a stage starts. The epoch is the installer's own clock, so a screen that reads the log late still shows real stage times. Older logs without `@@step` use the time the screen read the marker. |
| Measured counter and bar | Storage preparation milestones, release archives expanded, downloads that native pkg reported complete, or the package position pkg is processing. The bar fills only as that counter advances. | `@@progress` events and native pkg output. pkg's non-terminal `Fetching NAME: ..... done` lines now count as completed downloads; earlier screens required a `100%` that only a terminal gets. |
| Download bytes | During the download stage: bytes received for finished archives plus the one in progress, the number of archives finished, the current archive's bytes of its size, and pkg's own rounded total ("about 5 GiB", labelled as pkg's estimate). The attempt number appears on a retry. No percentage is computed from pkg's rounded total. | pkg's event pipe: `install` runs `pkg -o EVENT_PIPE=FIFO fetch`, and `pkg-events` turns `INFO_FETCH_BEGIN`/`INFO_PROGRESS_TICK`/`INFO_FETCH_FINISHED` for archives under `/All/` into `@@fetch` lines in the log (about four a second). pkg's non-terminal output prints only dots, so before this the stage had no byte measurement. |
| Package ticker | In the download and install phases only: the names of the packages pkg reports, newest on the right, with `n/N` (the position pkg is on) and the observed rate per minute. A rate appears only after ten seconds of real reports. | pkg's `[n/N] Installing NAME...` lines, and `Fetching NAME: ... done` during the download stage. |
| Spectrum | One bar per CPU core (eight bars at most; more cores are averaged in groups), plus disk write, disk read, I/O operations per second, network in and network out, and ZFS logical writes when the pool is known. Bars scale to the busiest rate seen so far on a logarithmic axis; the numbers under the visuals are exact. Peak caps hold the highest recent value and fall slowly, as in Winamp. | Kernel counters sampled four times a second: `kern.cp_times`, `kern.devstat.all`, the interface MIB (`net.link.generic.ifdata`), `vm.stats`, `kstat.zfs.misc.arcstats.size`, and `kstat.zfs.POOL.dataset.*.nwritten` once a second. Memory disks (the live image) and pass-through devices are excluded. The installer names its target disk and pool with `@@target`, so the meters measure that disk. |
| Scope | The last minute of disk-write and network-in rates as oscilloscope traces (braille dots, two samples per character). | The same samples. |
| Activity lines | Exact rates: disk write and read, I/O per second, ZFS logical write rate, network in and out with the busiest interface, CPU cores and load, memory in use, ZFS ARC size. On an encrypted install, a line notes that every pool write shown is encrypted by GELI AES-XTS on the target disk (GELI has no cheap counter of its own; all pool I/O passes through it). | As above. |
| Waiting, warning and failure lines | "Waiting for the next progress report" after five seconds without a new counter or package; invalid or out-of-order events; acquisition failure; the installer's exit status. | The model's checks. A wait never animates the counter. |

Animation smooths only between real samples: bars rise quickly and fall
slowly toward the latest measurement, peak caps decay, the ticker slides when a
new package is reported, and the scope scrolls as samples arrive. When nothing
is measured, nothing moves except the live activity, which keeps showing that
the machine is (or is not) busy. The Daemonarchy logo's gradient drifts, and
a glint crosses the one-line wordmark, at a speed set by the measured
activity: an idle machine leaves them still. The logo appears only on screens
with at least 50 rows; smaller screens show a one-line wordmark. The
flourishes and sounds in [Charm and sound](#charm-and-sound) start only from
the model's events.

## Charm and sound

The operator asked for 1.4 to be much more charming to watch through every
phase and to use sound liberally (UI-001, 2026-10-27). Every flourish and every
sound marks something that really happened, or a wait that really is a wait;
none of them moves along a track, fills, counts or estimates. The model
(`progress-model.py`) turns its observations into numbered events, and the
console screen, the graphical installer and the sound player all react to the
same events.

| Phase | What you see | What you hear | Started by |
|---|---|---|---|
| Loader | An animated color splash: the wordmark sweeps in, the mascot blinks, a tagline types out (at most 0.75 s; any key skips). `daemonarchy_splash=static` draws only the final frame, `NO` turns it off; nothing on serial or without color. | Nothing: UEFI has no reliable audio. | The loader menu ([source PR #36](https://github.com/jordanhubbard/daemonarchy-src/pull/36)) |
| Welcome screen | The logo's colors drift and the mascot blinks and looks around while the screen waits for Return (attract mode). | The boot chime. | The installer starting on the console |
| Configurator screens | Each screen title types in. | A whoosh. | Moving to a screen |
| Network bring-up | A mark that sparkles once per check: √ or × with Network adapters, Wired addresses (DHCP), DNS, System clock, Device firmware, Wi-Fi radios, Wi-Fi. | A rising "connected" or a falling "uh-oh". | Each `network-bringup` step's exit status (`nb_hook_result`) |
| MacBook firmware | √ "MacBook Wi-Fi firmware verified and the radio attached". | The "connected" sound. | Verified firmware and an attached radio |
| Disk confirmation | The destruction warning pulses red three times and stays bold red. | A two-tone klaxon; on "Install Daemonarchy", a thunk and a rising launch. | The final review; the operator's confirmation |
| Install screen opens | Rows appear top to bottom (0.45 s). | | The screen starting |
| Each stage | A card with the stage name opens over the visuals for 1.6 s; a finished stage sparkles on the timeline. | A rising arpeggio when a stage starts, a bell when it finishes. | `@@phase` and `@@step` markers |
| Packages | A note lights beside the ticker; every 50 packages (and the last) a banner flashes. | A blip whose pitch walks a pentatonic scale with the package count; a short fanfare every 50. | pkg's own `[n/N]` and `Fetching` lines |
| While working | The mascot's trident goes up and down at a pace set by the measured activity; the banner glint moves with it. | Optional chiptune: arpeggio loudness and tempo follow CPU, bass follows disk, hi-hats follow network. Silent when nothing is measured. | Kernel counters (the spectrum's samples) |
| A genuine wait | After 20 s without any report the mascot looks around and a line says "Still working: no new progress report for 0:42". | A soft two-note "still here", once per wait. | No new report for 20 s |
| Warnings and failures | Warning and failure lines as before. | "Uh-oh" for a progress warning, a descending sad trombone for a failure. | The model's checks; the result file |
| Completion | Fireworks over the visuals, a "Daemonarchy is installed" card and a happy mascot for 4 s (any key skips); a failure shows its status in a pulsing red card and a sad mascot. | A fanfare, or the failure sound. | Only the installer's result file |
| First boot | An animated welcome with the mascot and fireworks on the console, once. | The greeting chime; a boot chime on later boots. | `daemonarchy_greeting` (rc.d) |
| Live desktop | The graphical installer: the wordmark in the logo's gradient, flashes for stage starts and the disk warning, a glowing title for success. | The greeting chime when Hyprland starts, and the same cues as the console from the same events. | Hyprland start; the model's events |

### Controls

- On the install screen the bottom-right corner shows the state (`♪ 70%`,
  `♪ muted`, `♪ quiet 70%`, or `♪ off (serial console)` with the reason). In
  tmux the status line shows it too.
- `C-b m` mutes or unmutes, `C-b +` (or `C-b =`) and `C-b -` change the volume
  in steps of 10, and `C-b a` turns the ambient music on or off. They are
  listed in `C-b ?`. With the progress pane focused (or without tmux), `m`,
  `+`, `-` and `a` work directly.
- The configurator's menu has "Sound: ..." to choose on, quiet (stage
  changes, network results, the warning, the result) or off. The choice is
  written as `sound=` in `daemonarchy-install.conf` and becomes
  `daemonarchy.sound` in the installed system's `loader.conf`.
- `daemonarchy.sound=on|quiet|off` in `loader.conf` or at the loader prompt
  sets the default; `DAEMONARCHY_SOUND` overrides it for a process, and a
  CIDATA `daemonarchy-install.conf` may set `sound=on`.
- The graphical installer has a Mute button and a volume slider.
- `daemonarchy_greeting_enable="NO"` in the installed system's `rc.conf`
  turns off its chime and first-boot welcome.

### When it is silent

- Serial consoles and serial-class terminals (`/dev/ttyu*`, `TERM=vt100`),
  and a process with no local console.
- Unattended CIDATA installs, unless `sound=` or `daemonarchy.sound` asks for
  sound. Their installed system is silent too unless asked.
- No audio device: the player loads `snd_hda` and `snd_uaudio` (with
  `kldload -n`, so a driver already in the kernel is left alone) and stays off
  if no `/dev/dsp` appears. The live image also loads `snd_uaudio` at boot,
  and HD Audio is in `GENERIC` on amd64.
- Reduced motion (`DAEMONARCHY_REDUCED_MOTION=1`) keeps the sounds but draws
  the flourishes as single static frames; plain/serial output and `NO_COLOR`
  get plain lines.

A sound never delays or fails anything. `sound.py` synthesizes every sound
from oscillators, noise and envelopes (no sample files, nothing with an
outside licence) and one player process per user owns `/dev/dsp`
(16-bit mono at 22,050 Hz; sound(4) converts it). Front ends send it
datagrams with `MSG_DONTWAIT`: with no player, a full queue or a broken
device, the cue is dropped. The player drops cues instead of queueing them
late, plays nothing while muted, closes the device after two quiet seconds
so the desktop can use it, and reports a device error to the indicator. It
exits after 15 minutes without hearing from any front end; the install screen
checks in every 30 seconds and `sound play` starts it again when needed.

## Window controls (tmux)

On the console and over SSH the screen is window 0 of a private, locked-down
tmux session (`install-screen`, configuration in
`/usr/local/share/daemonarchy-installer/install-tmux.conf`). tmux's own model
and default keys apply, with the `Ctrl-b` prefix. The status line at the
bottom lists the windows (`index:name`, the active one marked `*`) and shows
`C-b ? help`.

| Keys | Action |
|---|---|
| `C-b %` / `C-b "` | Split left/right or top/bottom. The new pane asks what to show: 1 install log, 2 diagnostics, 3 remote debug, 4 shell (Enter opens a shell). |
| `C-b o`, `C-b` arrow keys | Move between panes. |
| `C-b x` | Close the pane after tmux's y/n confirmation. The progress view refuses. |
| `C-b z` | Zoom or unzoom the pane. |
| `C-b c` | New window (the same chooser). |
| `C-b n`, `C-b p`, `C-b 0`–`9` | Next, previous or numbered window. `C-b 0` is the progress view. |
| `C-b &` | Close the window after confirmation. Window 0 refuses. |
| `C-b w` | Window list (a menu with no close action). |
| `C-b [` | Scroll/copy mode, for example in the log pane; `q` leaves it. `C-b PgUp` scrolls back a page. |
| `C-b ?` | The key list. |
| `C-b d` | Not available: the installer cannot be detached. It shows a message and changes nothing. |
| `C-b C-b` | Sends a literal `Ctrl-b` to the pane. |
| `C-b G`, `C-b H`, `C-b R` | Open the install log, diagnostics or remote debugging directly in a new window. These keys are unbound in tmux's defaults. |
| `exit` | In a shell pane, closes that pane, as in tmux. |
| `v` | In the progress view: change the visual style (spectrum, scope, bars). |

Nothing here needs function keys or a virtual console switch. vt(4) binds
console switching only to Alt+F1–F12 and Print Screen, which many laptops,
including the Touch Bar MacBookPro16,1, do not have.

Closing panes or windows never affects the installation, which runs outside
the session. The progress view cannot be closed while installing; if it exits
or crashes before the installation finishes, tmux starts it again. When the
installation finishes while other panes or windows are open, the progress view
shows the result and waits until they are closed; a shell is never killed.
Then the session ends and the installer continues with the result.

Terminals too small to split are zoom-only: `C-b %` and `C-b "` open the new
view as a full-screen window, and `C-b 0` returns to the progress view.

The diagnostics view refreshes every five seconds with the processes using
the most CPU, `gpart show`, `zpool list -v`, `geli status`, `df` of the target,
interface addresses and the end of the kernel message buffer. It is
read-only.

## Remote debugging during the installation

Console-approved remote debugging keeps running from the configurator through
the installation to its end:

- In the installer menu, **Remote debug in the background** starts the
  listener after a confirmation; it stays up through the installation.
- In the debug shell, `remote-debug listen` asks as before; type `b` and Enter
  to keep the listener in the background, or press Enter to stop it.
  `remote-debug background` starts it directly.
- Every new agent still needs approval at the console. During the
  installation the progress view shows "Remote agent pairing request waiting:
  press C-b R". `C-b R` opens a window attached to the background listener,
  where you approve or deny the fingerprint; leaving that window keeps the
  listener running. The installer menu offers the same approval, and
  `remote-debug pending`, `approve ID` and `deny ID` work from any root shell.
- The background listener runs in its own process group, so a later Ctrl-C or
  hangup at the console does not stop it. `remote-debug stop` stops it and
  revokes the pairing.

## Terminals and colors

- **FreeBSD console (vt(4)).** vt(4) parses `38;5;N` but reduces it to its
  16-color palette, and it does not implement 24-bit color: teken reads the
  R, G and B values of `38;2;R;G;B` as separate attributes such as underline,
  bright background and reverse video. On the console the screen therefore
  uses the 16 vt colors directly and never sends 24-bit color; inside tmux,
  `install-screen` tells tmux the console has 16 colors. `tests/vt-console-colors.py`
  checks this natively by feeding the real output to sys/teken.
- **SSH and other terminals.** `TERM=*256color*` gets 256 colors, and
  `COLORTERM=truecolor` adds 24-bit color. Plain `xterm` gets 16 colors.
- **Serial-class terminals** (`vt100`, `vt220`, `ansi`, `cons25`) get the
  progress screen directly, without tmux, in ASCII with the eight basic colors.
- `NO_COLOR=1` removes color. `DAEMONARCHY_COLOR=none|8|16|256|truecolor`
  overrides detection, but never enables 256 or 24-bit color on the console.
- `DAEMONARCHY_REDUCED_MOTION=1` selects static bars and redraws at most once
  a second. `DAEMONARCHY_PROGRESS_STYLE=spectrum|scope|bars|plain` chooses the
  starting style. `plain`, `TERM=dumb` and non-terminal output print one status
  line per change.
- The screen reflows on resize, clips to small terminals and restores the
  cursor and screen on exit or interruption. It redraws only the cells that
  changed, at most ten frames a second, and backs off if drawing takes more
  than a quarter of the time. The installer's raw log still goes to the first
  serial port.
- Without tmux or Python the installer falls back to the direct screen, and
  then to a passive log tail that waits for the installer's result.

## One model for both installers

`progress-model.py` is the single producer. It reads the install log and
optional acquisition journal, samples the kernel counters and returns a plain
snapshot: stages with elapsed times, the measured counter, the package ticker,
activity rates and their history, the target disk and pool, warnings and the
result. The console screen draws that snapshot. The live desktop's graphical
installer (LIVE-001) can use `InstallProgress(log, status).poll()`, which keeps
the keys its progress page reads today (`title`, `details`, `fraction`,
`done`, `succeeded`, `recent`) and adds `stages`, `ticker`, `fetch` and
`activity`, so both installers show the same stages and metrics. During the
download stage `fraction` is the archive count pkg reported complete, and
`details` includes the received bytes line. `progress-model.py LOG
STATUS` prints the snapshots as JSON lines. `progress-dashboard.py` still
exports `Progress`, `Tail`, `lines`, `status` and `clean`.

An optional authenticated-acquisition journal uses the existing
[package-engine event contract](https://github.com/jordanhubbard/daemonarchy/blob/feat/native-release-program/components/package-engine/interfaces/contract.md).
Pass its file with `--events`, together with the exact `--input-pin` and
`--repository-pin` SHA-256 values from the selected transaction. Journal events
must be ordered and preserve those pins. Verified archive bytes are neither
network throughput nor installed-package counts, and acquisition never
authorizes installation.

## Tests and demos

- `PYTHONDONTWRITEBYTECODE=1 python3 tests/installer-progress.py` covers the
  measured model, stage times, the package ticker, activity rates from fake and
  real counters, the graphical installer adapter, frames at every size and
  style, color selection, a replay of a real install log, the screen in real
  kernel PTYs (styles, colors, resize, reduced motion, signals, completion)
  and the real tmux session with its default keys: splits, windows, the views,
  pane movement, zoom, guarded close of the progress view, confirmation, copy
  mode, the key list, the literal prefix, respawn, small-terminal zoom-only
  splits, resize, the remote debug window and the pairing banner, and
  completion with a shell still open. The tmux cases skip where tmux is
  missing.
- The same file's fetch cases convert a real pkg event-pipe recording
  (`tests/fixtures/installer-progress/pkg-fetch-events.jsonl`) and, as root on
  FreeBSD with `DAEMONARCHY_NATIVE_PKG_FETCH=1`, run a real `pkg fetch` through
  the event pipe and compare the reported bytes with the downloaded archives.
- `python3 tests/vt-console-colors.py` (FreeBSD with `/usr/src`) renders the
  real output through sys/teken.
- `sudo bash tests/remote-debug-background.sh` (FreeBSD) exercises the
  background listener, console approval and denial without a second console,
  attaching, Ctrl-C isolation and stop.
- The replay fixture `tests/fixtures/installer-progress/macbook-1.3.1-install.log`
  is the log of a real 1.3.1 MacBookPro16,1 installation that stopped while
  pkg extracted package 976 of 1188, scrubbed by `scripts/scrub-install-log.py`;
  see its provenance file.
- `scripts/installer-visuals-demo.py` replays a log through the real screen in
  a PTY and records an asciinema cast, optionally with key presses, the tmux
  session, a load command and HTML frames rendered as vt(4) draws them. The
  recorded demos are in [docs/demos/installer-visuals](demos/installer-visuals/README.md).

- The same suite covers charm and sound: the model's events from real
  markers, the event-to-sound mapping, the ambient layer's silence without
  measured activity, flourishes that start only from events, mute, volume and
  ambient keys in a real PTY and through tmux (`C-b m`, `C-b +`, `C-b -`),
  mode resolution and the automatic silences, cues dropped without blocking,
  the player writing PCM to a file-backed device and nothing while muted,
  missing and broken devices, and an install that finishes with the same
  status when sound is broken. `bash tests/installer-charm.sh` checks the
  configurator's result marks, the Sound option, `sound=` in the answers and
  the installed system's chime setup. `scripts/installer-charm-tour.sh` plays
  the configurator's flourishes and sounds in order; `sound.py render DIR`
  writes every sound as WAV. Previews are in
  [docs/demos/installer-sounds](demos/installer-sounds/README.md).

These checks do not partition storage, run pkg or qualify an installed system.
A full installation with the final image, on the physical console and over
serial, remains open under UI-001.
