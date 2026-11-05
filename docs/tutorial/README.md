# Daemonarchy newcomer tutorial movie

A narrated walkthrough for a complete newcomer: what Daemonarchy is, what it shares with FreeBSD and where it differs, how to get, verify and write the image and install it, the honest status of the aarch64 image, and for developers the Daemonarchy way of working compared with building FreeBSD world and ports directly, and the role of Literate AI in 1.5.x. It follows the `literate-ai/video-course@1` format of `litai video`.

- [`course.json`](course.json): the editable source. Edit this, not the video.
- [NARRATIVE.md](NARRATIVE.md): the script, with the source of each scene's claims.
- [EVIDENCE.md](EVIDENCE.md): where the facts come from and what is not claimed.
- `assets/`: authentic screenshots copied from [`../images/`](../images/).

Imp (a small daemon) guides and Robin (a newcomer) asks. Displayed commands are inert text; `litai video` never runs them.

## Status of the media

Built for 1.5.1 on 2026-11-05 with recorded narration: every dialogue turn was synthesized by NVIDIA's Magpie TTS Multilingual on build.nvidia.com (voices `Magpie-Multilingual.EN-US.Aria` for Imp and `Magpie-Multilingual.EN-US.Jason` for Robin) with [`narrate-nvidia.py`](narrate-nvidia.py), then assembled with `litai video build --narration recorded`. The result is an MP4 of 481.4 seconds at 1280x720 with embedded subtitles, plus SRT and VTT files, and `litai video verify` accepted its `video-result.json`. The media are published as assets of the 1.5.1 release (`daemonarchy-newcomer-tutorial-1.5.1.mp4`, `.srt`, `.vtt`), not committed here, and the repository README links to them. The generated WAV files are not committed either; rerun the script to recreate them.

The release owner watched an earlier espeak-ng build and asked for these voices; the owner reviews the film before it is published.

## Rebuild

Needs `ffmpeg`, `ffprobe`, `magick` (ImageMagick 7), a TrueType font file, and either `espeak-ng` or an `audio` file for every dialogue turn. For the published voices you also need a build.nvidia.com API key in `~/.config/daemonarchy/nvidia-api-key` (mode 600) and the `nvidia-riva-client` Python package; only the narration text is sent to NVIDIA.

```sh
docs/tutorial/narrate-nvidia.py docs/tutorial _build/tutorial-nv
cd _build/tutorial-nv
litai video plan course.json
litai video build course.json --output ../videos \
  --font /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf --narration recorded
litai video verify ../videos/<course-dir>/video-result.json --manifest course.json
```

For a quick draft without a key, use `--narration espeak` on `docs/tutorial/course.json` directly.
```

See Literate AI's instructional-video guide for the backends. A person must listen to the speech and check the frames before the film is published.
