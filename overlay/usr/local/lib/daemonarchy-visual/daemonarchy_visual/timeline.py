"""Clocks, easing, tweens and timelines. Time is injected, so animation is testable and repeatable."""

import time


class MonotonicClock:
    def now(self):
        return time.monotonic()

    def sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)


class ManualClock:
    """A clock tests and recordings advance by hand; sleeping advances it."""

    def __init__(self, start=0.0):
        self.time = start

    def now(self):
        return self.time

    def sleep(self, seconds):
        self.time += max(0.0, seconds)


def linear(t):
    return t


def ease_in(t):
    return t * t


def ease_out(t):
    return 1 - (1 - t) * (1 - t)


def ease_in_out(t):
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


EASINGS = dict(linear=linear, ease_in=ease_in, ease_out=ease_out, ease_in_out=ease_in_out)


class Tween:
    """A value moving from `start` to `end` over `duration` seconds."""

    def __init__(self, start, end, duration, ease="linear"):
        self.start, self.end, self.duration = start, end, max(1e-9, duration)
        self.ease = EASINGS[ease] if isinstance(ease, str) else ease
        self.age = 0.0

    def advance(self, dt):
        self.age = min(self.duration, self.age + dt)
        return self.value

    @property
    def value(self):
        return self.start + (self.end - self.start) * self.ease(self.age / self.duration)

    @property
    def done(self):
        return self.age >= self.duration


class Timeline:
    """Callbacks at times (seconds from the start), advanced by `advance(dt)`.

    `at(time, fn)` runs `fn()` once when the timeline passes `time`;
    `every(period, fn)` runs `fn()` each period. A timeline never sleeps and
    never raises into its host: a callback that raises is dropped.
    """

    def __init__(self):
        self.age = 0.0
        self.events = []     # [time, fn, period or None]
        self.finished = []

    def at(self, when, fn):
        self.events.append([when, fn, None])
        return self

    def every(self, period, fn, start=0.0):
        self.events.append([start + period, fn, period])
        return self

    def advance(self, dt):
        self.age += dt
        for event in list(self.events):
            while event in self.events and event[0] <= self.age:
                try:
                    event[1]()
                except Exception:  # noqa: BLE001 - a flourish never fails its host.
                    self.events.remove(event)
                    break
                if event[2] is None:
                    self.events.remove(event)
                    self.finished.append(event[1])
                else:
                    event[0] += event[2]
        return self.age

    @property
    def done(self):
        return not self.events
