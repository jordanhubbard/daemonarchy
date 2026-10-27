# 1.4 install screen demos

Recorded on 2026-10-26 on a FreeBSD 16.0-CURRENT amd64 test host (Python 3.12,
tmux 3.7c) with `scripts/installer-visuals-demo.py`. Each demo replays the
scrubbed log of a real 1.3.1 MacBookPro16,1 installation
(`tests/fixtures/installer-progress/macbook-1.3.1-install.log`, which stops
while pkg extracts package 976 of 1188) through the real install screen in a
pseudo-terminal. Stages, counters and the package ticker follow that log,
compressed into about a minute. The activity meters are live kernel counters
of the recording host while it copied `/usr/src/sys` between ZFS datasets and
downloaded a FreeBSD image, so they show real disk, CPU and network work, but
not the MacBook's. Network and hardware addresses in the diagnostics view are
masked (`DAEMONARCHY_DIAGNOSTICS_REDACT=1`).

| Recording | What it shows |
|---|---|
| [`console-spectrum.cast`](console-spectrum.cast) and [`console-spectrum.html`](console-spectrum.html) | The direct screen as the vt(4) console draws it (16 colors), 50x160. The HTML frames are rendered by sys/teken, the emulator inside vt(4). |
| [`console-tmux.cast`](console-tmux.cast) and [`console-tmux.html`](console-tmux.html) | The tmux session on the console: `C-b %` then the install log, `C-b "` then diagnostics, `C-b c` then a shell, `C-b 0`, `C-b z` zoom and unzoom, `C-b ?`, and `C-b x` closing a pane after its y/n prompt. |
| [`ssh-256color-tmux.cast`](ssh-256color-tmux.cast) | The tmux session over a 256-color terminal (SSH), scope style, with the log split, a diagnostics window and `v` changing the style. |
| [`serial-vt100.cast`](serial-vt100.cast) and [`serial-vt100.html`](serial-vt100.html) | A serial-class terminal (`TERM=vt100`): the direct screen in ASCII with eight colors, ending with a successful installer result. |

Play a cast in a terminal of at least 160x50 (80x24 for the serial demo):

    asciinema play docs/demos/installer-visuals/console-tmux.cast

Open the HTML files in a browser for still frames. To record again on a
FreeBSD host:

    scripts/installer-visuals-demo.py tests/fixtures/installer-progress/macbook-1.3.1-install.log \
        --console --tmux --size 50x160 --seconds 60 --cast demo.cast \
        --key '10:\x02%' --key '13:1' --load 'COMMAND THAT CREATES REAL ACTIVITY'

These are demonstrations of the screen, not installation evidence.
