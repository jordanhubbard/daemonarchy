# Daemonarchy newcomer tutorial movie

A narrated walkthrough for a complete newcomer: what Daemonarchy is, what it shares with FreeBSD and where it differs, how to get, verify and write the image and install it, the honest status of the aarch64 image, and for developers the Daemonarchy way of working compared with building FreeBSD world and ports directly, and the role of Literate AI in 1.5.x. It follows the `literate-ai/video-course@1` format of `litai video`.

- [`course.json`](course.json): the editable source. Edit this, not the video.
- [NARRATIVE.md](NARRATIVE.md): the script, with the source of each scene's claims.
- [EVIDENCE.md](EVIDENCE.md): where the facts come from and what is not claimed.
- `assets/`: authentic screenshots copied from [`../images/`](../images/).

Imp (a small daemon) guides and Robin (a newcomer) asks. Displayed commands are inert text; `litai video` never runs them.

## Status of the media

Built for 1.5.1 on 2026-11-05 with `litai video build --narration espeak` (espeak-ng scratch voices `en-us+f3` and `en-us+m3`; no recorded narration): an MP4 of 494.7 seconds at 1280x720 with embedded subtitles, plus SRT and VTT files. The media are published as assets of the 1.5.1 release (`daemonarchy-newcomer-tutorial-1.5.1.mp4`, `.srt`, `.vtt`), not committed here, and the repository README links to them.

The release owner watches the film before it is published. **There is no `video-result.json` receipt yet:** the build stopped at its final check because the concatenated film is 0.617 seconds longer than the sum of its narration, beyond Literate AI's fixed 0.25-second tolerance (`video.media_duration`). The per-clip checks passed; the drift is per-clip frame rounding that adds up over 114 caption segments. That is a framework issue, and `litai video verify` cannot be run on this film until it is resolved.

## Rebuild

Needs `ffmpeg`, `ffprobe`, `magick` (ImageMagick 7), a TrueType font file, and either `espeak-ng` or an `audio` file for every dialogue turn.

```sh
litai video plan docs/tutorial/course.json
litai video build docs/tutorial/course.json --output _build/videos \
  --font /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf --narration espeak
litai video verify _build/videos/<course-dir>/video-result.json \
  --manifest docs/tutorial/course.json
```

See Literate AI's instructional-video guide for the backends. A person must listen to the speech and check the frames before the film is published.
