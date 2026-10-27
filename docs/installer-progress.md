# Installer progress

The install screen shows what the installation is doing while it runs. Every
moving element measures something real. Nothing turns elapsed time into a
completion percentage or an estimated time remaining, and only the installer's
result file says whether the installation succeeded.

## What each element measures

| Element | Measures | Source |
|---|---|---|
| Stage timeline: Partition, Encrypt, ZFS pool, Base sets, Boot loader, Configure, Download, Packages, Account, (Checkouts, CUDA), Verify | The stage that is running, the stages finished, and each stage's elapsed time. Encrypt shows as skipped when the disk is not encrypted. Optional stages appear only when they run. | `@@phase` and `@@step NAME EPOCH` markers that `install` prints when a stage starts. The epoch is the installer's own clock, so a screen that reads the log late still shows real stage times. Older logs without `@@step` use the time the screen read the marker. |
| Measured counter and bar | Storage preparation milestones, release archives expanded, downloads that native pkg reported complete, or the package position pkg is processing. The bar fills only as that counter advances. | `@@progress` events and native pkg output. |
| Package ticker | The names of the packages pkg reports, newest on the right, with `n/N` and the observed rate per minute. A rate appears only after ten seconds of real reports. | pkg's `[n/N] Installing NAME...` lines, and `Fetching NAME: ... done` during the download stage. |
| Spectrum | One bar per CPU core (eight bars at most; more cores are averaged in groups), plus disk write, disk read, I/O operations per second, network in and network out, and ZFS logical writes when the pool is known. Bars scale to the busiest rate seen so far on a logarithmic axis; the numbers under the visuals are exact. Peak caps hold the highest recent value and fall slowly, as in Winamp. | Kernel counters sampled four times a second: `kern.cp_times`, `kern.devstat.all`, the interface MIB (`net.link.generic.ifdata`), `vm.stats`, `kstat.zfs.misc.arcstats.size`, and `kstat.zfs.POOL.dataset.*.nwritten` once a second. Memory disks (the live image) and pass-through devices are excluded. The installer names its target disk and pool with `@@target`, so the meters measure that disk. |
| Scope | The last minute of disk-write and network-in rates as oscilloscope traces (braille dots, two samples per character). | The same samples. |
| Activity lines | Exact rates: disk write and read, I/O per second, ZFS logical write rate, network in and out with the busiest interface, CPU cores and load, memory in use, ZFS ARC size. On an encrypted install, a line notes that every pool write shown is encrypted by GELI AES-XTS on the target disk (GELI has no cheap counter of its own; all pool I/O passes through it). | As above. |
| Waiting, warning and failure lines | "Waiting for the next progress report" after five seconds without a new counter or package; invalid or out-of-order events; acquisition failure; the installer's exit status. | The model's checks. A wait never animates the counter. |

Animation smooths only between real samples: bars rise quickly and fall
slowly toward the latest measurement, peak caps decay, the ticker slides when a
new package is reported, and the scope scrolls as samples arrive. When nothing
is measured, nothing moves except the live activity, which keeps showing that
the machine is (or is not) busy. The Daemonarchy logo is drawn in a static
gradient; it never animates. The logo appears only on screens with at least
50 rows; smaller screens show a one-line wordmark.

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
`done`, `succeeded`, `recent`) and adds `stages`, `ticker` and `activity`, so
both installers show the same stages and metrics. `progress-model.py LOG
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

These checks do not partition storage, run pkg or qualify an installed system.
A full installation with the final image, on the physical console and over
serial, remains open under UI-001.
