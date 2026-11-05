#!/usr/bin/env python3
"""Narrate docs/tutorial/course.json with NVIDIA Magpie TTS (build.nvidia.com).

  narrate-nvidia.py SRC_TUTORIAL_DIR OUT_TUTORIAL_DIR [--list-voices]

Needs the nvidia-riva-client Python package (pip install nvidia-riva-client).

Copies the tutorial directory to OUT, synthesizes one WAV per dialogue turn into
OUT/narration/, and writes OUT/course.json with an "audio" path on every turn, for
`litai video build --narration recorded`. The API key is read from the file named by
NVIDIA_API_KEY_FILE (default ~/.config/daemonarchy/nvidia-api-key) or from NVIDIA_API_KEY,
and is never printed. Only the public narration text is sent.
"""
import json, os, re, shutil, sys, wave
from pathlib import Path

import riva.client

SERVER = "grpc.nvcf.nvidia.com:443"
FUNCTION_ID = "877104f7-e885-42b9-8de8-f6e4c6303969"  # magpie-tts-multilingual
RATE = 44100
VOICES = {
    "imp": os.environ.get("IMP_VOICE", "Magpie-Multilingual.EN-US.Aria"),
    "robin": os.environ.get("ROBIN_VOICE", "Magpie-Multilingual.EN-US.Jason"),
}
GAP = 0.25  # seconds of silence between sentences of one turn


def key():
    path = Path(os.environ.get("NVIDIA_API_KEY_FILE", "~/.config/daemonarchy/nvidia-api-key")).expanduser()
    if path.is_file():
        return path.read_text().strip()
    if os.environ.get("NVIDIA_API_KEY"):
        return os.environ["NVIDIA_API_KEY"].strip()
    sys.exit(f"no API key: put it in {path} (mode 600) or set NVIDIA_API_KEY")


def service():
    auth = riva.client.Auth(None, True, SERVER, [["function-id", FUNCTION_ID], ["authorization", "Bearer " + key()]])
    return riva.client.SpeechSynthesisService(auth)


def chunks(text, limit=350):
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        while len(sentence) > limit:
            cut = sentence.rfind(",", 0, limit)
            cut = cut if cut > 0 else sentence.rfind(" ", 0, limit)
            out.append(sentence[: cut + 1].strip())
            sentence = sentence[cut + 1 :].strip()
        if sentence:
            out.append(sentence)
    return out


def main():
    tts = service()
    if "--list-voices" in sys.argv:
        cfg = tts.stub.GetRivaSynthesisConfig(riva.client.proto.riva_tts_pb2.RivaSynthesisConfigRequest(), metadata=tts.auth.get_auth_metadata())
        for m in cfg.model_config:
            print(m.parameters.get("voice_name", ""), m.parameters.get("subvoices", "")[:400])
        return
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    (out / "narration").mkdir()
    doc = json.loads((src / "course.json").read_text())
    silence = b"\0\0" * int(RATE * GAP)
    for s, scene in enumerate(doc["scenes"], 1):
        for t, turn in enumerate(scene["dialogue"]):
            pcm = b""
            for i, piece in enumerate(chunks(turn["text"])):
                for attempt in range(8):
                    try:
                        r = tts.synthesize(piece, VOICES[turn["speaker"]], "en-US", sample_rate_hz=RATE,
                                           encoding=riva.client.AudioEncoding.LINEAR_PCM)
                        break
                    except Exception as e:
                        print(f"  retry {attempt + 1}: {type(e).__name__}", flush=True)
                        __import__("time").sleep(30)
                else:
                    sys.exit("synthesis kept failing")
                pcm += (silence if i else b"") + r.audio
            name = f"narration/s{s:03}-t{t:02}.wav"
            with wave.open(str(out / name), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm)
            turn["audio"] = name
            print(f"{name} {len(pcm) / 2 / RATE:6.2f}s {turn['speaker']}", flush=True)
    for sp, v in VOICES.items():
        doc["speakers"][sp]["voice"] = v
    (out / "course.json").write_text(json.dumps(doc, indent=2) + "\n")


if __name__ == "__main__":
    main()
