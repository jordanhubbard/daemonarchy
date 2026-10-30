"""Audio cues: a request a host may honour, mute or ignore. Never blocks, never raises, never required.

A host supplies a backend (the installer uses its sound daemon through
sound.py); a plugin only asks for a cue by name. Standard cue names a host
should understand: click, select, blip, laser, hit, explode, bounce, pickup,
levelup, gameover, win. Unknown names are ignored.
"""

import queue
import threading

CUES = ("click", "select", "blip", "laser", "hit", "explode", "bounce", "pickup", "levelup", "gameover", "win")


class Audio:
    """The interface scenes use. Subclasses override `_play`."""

    muted = False

    def cue(self, name, **params):
        if self.muted or name not in CUES:
            return False
        try:
            return bool(self._play(name, params))
        except Exception:  # noqa: BLE001 - sound is never allowed to fail a caller.
            return False

    def _play(self, name, params):
        return False

    def close(self):
        pass


class NullAudio(Audio):
    """No sound: mute, no device, serial or SSH."""


class RecordingAudio(Audio):
    """Remembers the cues requested; used by tests and by hosts that show a visual cue instead."""

    def __init__(self):
        self.heard = []

    def _play(self, name, params):
        self.heard.append(name)
        return True


class ThreadedAudio(Audio):
    """Wraps a blocking backend `play(name, **params)` so a cue never waits on it.

    Cues go through a small bounded queue to one worker thread; when the queue
    is full a cue is dropped rather than delaying a frame.
    """

    def __init__(self, play, limit=8):
        self.play = play
        self.queue = queue.Queue(maxsize=limit)
        self.dropped = 0
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _play(self, name, params):
        try:
            self.queue.put_nowait((name, params))
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def _run(self):
        while True:
            item = self.queue.get()
            if item is None:
                return
            try:
                self.play(item[0], **item[1])
            except Exception:  # noqa: BLE001
                pass

    def close(self):
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
