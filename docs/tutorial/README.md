# Daemonarchy newcomer tutorial movie

A narrated walkthrough for a complete newcomer: what Daemonarchy is, what it shares with FreeBSD and where it differs, how to get, verify and write the image and install it, the honest status of the aarch64 image, and for developers the Daemonarchy way of working compared with building FreeBSD world and ports directly, and the role of Literate AI in 1.5.x. It follows the `literate-ai/video-course@1` format of `litai video`.

- [`course.json`](course.json): the editable source. Edit this, not the video.
- [NARRATIVE.md](NARRATIVE.md): the script, with the source of each scene's claims.
- [EVIDENCE.md](EVIDENCE.md): where the facts come from and what is not claimed.
- `assets/`: authentic screenshots copied from [`../images/`](../images/).

Imp (a small daemon) guides and Robin (a newcomer) asks. Displayed commands are inert text; `litai video` never runs them.

## Status of the media

The manifest passes `litai video plan`. **The MP4, SRT, VTT and `video-result.json` have not been built**: the build host lacked ImageMagick's `magick`, `espeak-ng` and any recorded narration, and no speech was faked. The `voice` fields (`en-us+f3`, `en-us+m3`) are espeak-ng voices intended only for a scratch track; recorded audio on each turn (`audio`) is the better path.

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
