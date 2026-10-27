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
| [`console-charm.cast`](console-charm.cast), [`console-charm.html`](console-charm.html) and [`console-charm.ogg`](console-charm.ogg) | 1.4 charm and sound (recorded 2026-10-27): the direct screen on the vt(4) console, 50x160, with stage cards, finished-stage sparkles, package and download milestone banners, the mascot and banner glint keeping time with the measured activity, then (the demo writes a successful result after the log, which the real 1.3.1 install never reached) fireworks, the happy mascot and the fanfare. The `.ogg` is what the sound player wrote during the recording, silence included, so it plays in step with the cast. |
| [`console-tmux-sound.cast`](console-tmux-sound.cast) and [`console-tmux-sound.ogg`](console-tmux-sound.ogg) | The tmux session with sound: `C-b m` mutes (the status line and the screen show `♪ muted`), `C-b m` unmutes, `C-b +` twice and `C-b -` change the volume, `C-b ?` lists the Sound keys, then the result. |
| [`configurator-charm.cast`](configurator-charm.cast), [`configurator-charm.html`](configurator-charm.html) and [`configurator-charm.ogg`](configurator-charm.ogg) | `scripts/installer-charm-tour.sh`, 30x100 on the vt(4) console: the welcome screen's idle animation with the boot chime, typed-in screen titles, network check results (one failure, then a retry that passes), the MacBook firmware result, the pulsing disk warning with its klaxon, the commit sound and the first-boot welcome. The results are examples fed to the real `charm.py`; nothing touched a disk or the network. |

Play a cast in a terminal of at least 160x50 (80x24 for the serial demo):

    asciinema play docs/demos/installer-visuals/console-tmux.cast

To hear a 1.4 demo with its sound, start both together, for example:

    ogg123 docs/demos/installer-visuals/console-charm.ogg & asciinema play docs/demos/installer-visuals/console-charm.cast

The charm demos were recorded on FreeBSD 16.0-CURRENT amd64 (Python 3.12,
tmux 3.7c) with the sound player writing to a file instead of `/dev/dsp`
(`DAEMONARCHY_SOUND_DEVICE=file:...`), while a load loop wrote random data to
disk; the HTML frames are rendered by sys/teken. Every sound by itself is in
[installer-sounds](../installer-sounds/README.md).

Open the HTML files in a browser for still frames. To record again on a
FreeBSD host:

    scripts/installer-visuals-demo.py tests/fixtures/installer-progress/macbook-1.3.1-install.log \
        --console --tmux --size 50x160 --seconds 60 --cast demo.cast \
        --key '10:\x02%' --key '13:1' --load 'COMMAND THAT CREATES REAL ACTIVITY'

These are demonstrations of the screen, not installation evidence.
