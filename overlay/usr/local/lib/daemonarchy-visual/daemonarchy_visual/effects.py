"""Effects: particles and fireworks, typed text and gradient text. All are decorative and seeded."""

import math
import random

from .palette import DIM, SPARKS, gradient


class Particles:
    """Point particles with velocity, gravity and a lifetime, clipped to a width x height area."""

    def __init__(self, width, height, seed=1993, gravity=6.0):
        self.width, self.height = max(1, width), max(1, height)
        self.random = random.Random(seed)
        self.gravity = gravity
        self.particles = []   # [x, y, vx, vy, life, color]

    def emit(self, x, y, count, speed=(6, 14), life=(0.9, 1.6), color=None, flatten=0.5):
        r = self.random
        for index in range(count):
            angle = 2 * math.pi * index / count + r.uniform(-0.1, 0.1)
            v = r.uniform(*speed)
            self.particles.append([x, y, math.cos(angle) * v, math.sin(angle) * v * flatten,
                                   r.uniform(*life), color or r.choice(SPARKS)])

    def step(self, dt):
        alive = []
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += self.gravity * dt
            p[4] -= dt
            if p[4] > 0 and 0 <= p[0] < self.width and 0 <= p[1] < self.height:
                alive.append(p)
        self.particles = alive

    def cells(self, unicode=True):
        """(x, y, char, color) for each live particle; it fades through four stages."""
        chars = ("☼", "*", "+", "·") if unicode else ("@", "*", "+", ".")
        for x, y, _vx, _vy, life, color in self.particles:
            stage = 0 if life > 1.2 else 1 if life > 0.8 else 2 if life > 0.4 else 3
            yield int(x), int(y), chars[stage], color if stage < 3 else DIM


class Fireworks(Particles):
    """Bursts for a celebration; seeded, so recordings repeat."""

    def __init__(self, width, height, seed=1993):
        super().__init__(width, height, seed)
        self.next_burst = 0.0
        self.age = 0.0

    def burst(self):
        r = self.random
        self.emit(r.uniform(0.15, 0.85) * self.width, r.uniform(0.15, 0.6) * self.height, 18)

    def step(self, dt, spawning=True):
        self.age += dt
        if spawning and self.age >= self.next_burst:
            self.burst()
            self.next_burst = self.age + self.random.uniform(0.35, 0.7)
        super().step(dt)


def typed(text, age, per_char=0.018, limit=0.3):
    """The part of `text` visible `age` seconds into a type-in that lasts at most `limit` seconds."""
    step = min(per_char, limit / max(1, len(text)))
    return text[:int(age / step) + 1] if step > 0 else text


def gradient_text(canvas, x, y, text, stops, shift=0.0, bold=True):
    """Draw `text` with a color gradient that drifts by `shift` (0..1 wraps)."""
    for index, char in enumerate(text):
        t = (index / max(1, len(text) - 1) + shift) % 1.0
        canvas.put(x + index, y, char, (gradient(stops, t), None, bold))


def pulse(age, period=1.0):
    """0..1..0 smoothly, once per period."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * age / period)
