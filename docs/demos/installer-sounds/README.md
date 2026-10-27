# 1.4 installer sounds

Every sound the installer makes, rendered by `sound.py render` on 2026-10-27
and encoded as Ogg Vorbis (22,050 Hz mono). All of them are synthesized in
`overlay/usr/local/libexec/daemonarchy-installer/sound.py` from square,
triangle, sine and noise oscillators with envelopes; there are no sample
files and nothing with an outside licence. On the installer the player sends
the same samples to `/dev/dsp` as 16-bit mono PCM.

| File | Plays when |
|---|---|
| [`tour.ogg`](tour.ogg) | All of them in the order an installation meets them (about 32 s): boot chime, a choice, a screen transition, network results (one failure), the disk warning, the commit, stages, forty package blips and a milestone, a genuine wait, the fanfare, the failure sound and the first-boot greeting. Start here. |
| [`boot.ogg`](boot.ogg) | The installer's welcome screen appears; later boots of the installed system. |
| [`whoosh.ogg`](whoosh.ogg) | The configurator moves to a new screen. |
| [`select.ogg`](select.ogg), [`click.ogg`](click.ogg) | Choice and key feedback (available to front ends). |
| [`net_ok.ogg`](net_ok.ogg) | A network or firmware check passed. |
| [`net_fail.ogg`](net_fail.ogg) | A network check failed, or the progress model reported a warning. |
| [`warn.ogg`](warn.ogg) | The disk-commit warning before anything is erased. |
| [`commit.ogg`](commit.ogg) | The operator confirmed "Install Daemonarchy". |
| [`stage.ogg`](stage.ogg) | An install stage started (`@@phase`/`@@step`). |
| [`stage_done.ogg`](stage_done.ogg) | An install stage finished. |
| [`tick.ogg`](tick.ogg) | pkg reported a package; the pitch walks a pentatonic scale with the count (hear it in the tour). |
| [`milestone.ogg`](milestone.ogg) | Every 50 packages pkg reports, and the last one. |
| [`attract.ogg`](attract.ogg) | No new progress report for 20 seconds (once per wait). |
| [`fanfare.ogg`](fanfare.ogg) | The installer's result file says it succeeded. |
| [`error.ogg`](error.ogg) | The installer failed, or the configurator stopped. |
| [`greeting.ogg`](greeting.ogg) | The installed system's first boot and the live desktop. |
| [`volume.ogg`](volume.ogg) | Unmute or a volume change. |
| [`ambient.ogg`](ambient.ogg) | Twelve seconds of the optional ambient layer through an illustrative activity curve: silence, disk writes (bass) and CPU (arpeggio), then network (hi-hats), then silence again. On the installer the curve is the measured activity. |

Recordings of real screen runs with their sound tracks are in
[installer-visuals](../installer-visuals/README.md) (`*.ogg` next to each
`*.cast`).

To render them again as WAV, or hear them on a FreeBSD machine with audio:

    python3 overlay/usr/local/libexec/daemonarchy-installer/sound.py render /tmp/daemonarchy-sounds
    DAEMONARCHY_SOUND=on overlay/usr/local/libexec/daemonarchy-installer/sound ensure
    DAEMONARCHY_SOUND=on overlay/usr/local/libexec/daemonarchy-installer/sound play boot fanfare
    DAEMONARCHY_SOUND=on scripts/installer-charm-tour.sh

The encoding command was `ffmpeg -i NAME.wav -c:a libvorbis -q:a 3 NAME.ogg`.
These are previews, not installation evidence.
