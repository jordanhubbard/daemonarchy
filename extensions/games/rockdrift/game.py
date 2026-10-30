"""Rockdrift: an asteroid-field homage. A drifting ship, rocks that split, a screen that wraps.

Original code and art. World units are square: a unit is two terminal columns wide and one row
tall, so rotation looks right. Rules in `Game` (no terminal, seeded), drawing in `RockdriftScene`.
"""

import math
import random

from daemonarchy_visual import Scene, arcade, palette

WU, HU = 28.0, 20.0           # world size in units; drawn 2 columns per unit horizontally
TURN, THRUST, DRAG = 3.4, 20.0, 0.35
BULLET_SPEED, BULLET_LIFE, MAX_BULLETS = 24.0, 1.1, 4
RADII = {3: 2.6, 2: 1.6, 1: 0.8}
POINTS = {3: 20, 2: 50, 1: 100}
ARROWS = "^/>\\v/<\\"          # heading octants, starting up and going clockwise (screen y grows down)
ARROWS_UNICODE = "▲◥►◢▼◣◄◤"


def wrap(v, size):
    return v % size


class Game:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.score, self.lives, self.level = 0, 3, 1
        self.state = "play"
        self.events = []
        self.spawn_ship()
        self.new_field()

    def spawn_ship(self):
        self.ship = dict(x=WU / 2, y=HU / 2, vx=0.0, vy=0.0, angle=-math.pi / 2)   # pointing up
        self.bullets = []
        self.safe = 2.0

    def new_field(self):
        r = self.random
        self.rocks = []
        for _ in range(3 + self.level):
            while True:
                x, y = r.uniform(0, WU), r.uniform(0, HU)
                if math.hypot(x - WU / 2, y - HU / 2) > 6:
                    break
            speed, heading = r.uniform(1.5, 3.5 + 0.4 * self.level), r.uniform(0, 2 * math.pi)
            self.rocks.append(dict(x=x, y=y, vx=speed * math.cos(heading), vy=speed * math.sin(heading) * 0.7, size=3))

    def step(self, dt, actions):
        self.events = []
        if self.state != "play":
            if "fire" in actions or "select" in actions:
                self.__init__(self.random.random())
            return
        self.safe = max(0.0, self.safe - dt)
        ship = self.ship
        ship["angle"] += TURN * dt * ((1 if "right" in actions else 0) - (1 if "left" in actions else 0))
        if "up" in actions:
            ship["vx"] += math.cos(ship["angle"]) * THRUST * dt
            ship["vy"] += math.sin(ship["angle"]) * THRUST * dt * 0.7
        damp = max(0.0, 1.0 - DRAG * dt)
        ship["vx"] *= damp
        ship["vy"] *= damp
        ship["x"] = wrap(ship["x"] + ship["vx"] * dt, WU)
        ship["y"] = wrap(ship["y"] + ship["vy"] * dt, HU)
        if "fire" in actions and len(self.bullets) < MAX_BULLETS:
            self.bullets.append(dict(x=ship["x"], y=ship["y"], life=BULLET_LIFE,
                                     vx=math.cos(ship["angle"]) * BULLET_SPEED + ship["vx"],
                                     vy=math.sin(ship["angle"]) * BULLET_SPEED * 0.7 + ship["vy"]))
            self.events.append("laser")
        for rock in self.rocks:
            rock["x"], rock["y"] = wrap(rock["x"] + rock["vx"] * dt, WU), wrap(rock["y"] + rock["vy"] * dt, HU)
        for b in list(self.bullets):
            b["x"], b["y"], b["life"] = wrap(b["x"] + b["vx"] * dt, WU), wrap(b["y"] + b["vy"] * dt, HU), b["life"] - dt
            if b["life"] <= 0:
                self.bullets.remove(b)
                continue
            rock = self.rock_at(b["x"], b["y"], 0.3)
            if rock is not None:
                self.bullets.remove(b)
                self.split(rock)
        if not self.safe and self.rock_at(ship["x"], ship["y"], 0.5) is not None:
            self.crash()
        if not self.rocks and self.state == "play":
            self.level += 1
            self.score += 150
            self.events.append("levelup")
            self.new_field()

    def distance(self, ax, ay, bx, by):
        dx, dy = abs(ax - bx), abs(ay - by)
        return math.hypot(min(dx, WU - dx), min(dy, HU - dy))

    def rock_at(self, x, y, margin):
        for rock in self.rocks:
            if self.distance(x, y, rock["x"], rock["y"]) <= RADII[rock["size"]] + margin:
                return rock
        return None

    def split(self, rock):
        self.rocks.remove(rock)
        self.score += POINTS[rock["size"]]
        self.events.append("explode")
        if rock["size"] > 1:
            for sign in (-1, 1):
                heading = math.atan2(rock["vy"], rock["vx"]) + sign * self.random.uniform(0.5, 1.2)
                speed = math.hypot(rock["vx"], rock["vy"]) * 1.35 + 0.5
                self.rocks.append(dict(x=rock["x"], y=rock["y"], vx=speed * math.cos(heading),
                                       vy=speed * math.sin(heading) * 0.7, size=rock["size"] - 1))

    def crash(self):
        self.lives -= 1
        self.events.append("hit")
        if self.lives <= 0:
            self.state = "over"
            self.events.append("gameover")
        else:
            self.spawn_ship()


class RockdriftScene(Scene):
    min_size = (58, 24)
    title = "Rockdrift"

    def __init__(self, seed=None):
        self.game = Game(seed)
        self.clock = arcade.FixedStep(30)

    def update(self, dt, ctx, actions):
        for _ in range(self.clock.steps(dt)):
            self.game.step(self.clock.step, actions)
            for cue in self.game.events:
                ctx.audio.cue(cue)
            actions = [a for a in actions if a not in ("fire", "select")]

    def plot(self, canvas, field, x, y, char, style):
        col, row = int(x * 2), int(y)
        if 0 <= col < field.w and 0 <= row < field.h:
            canvas.put(field.x + col, field.y + row, char, style)

    def draw(self, canvas, ctx):
        g = self.game
        arcade.hud(canvas, ctx, "ROCKDRIFT", g.score, g.lives, g.level)
        field = arcade.playfield(canvas, int(WU * 2), int(HU))
        arcade.frame(canvas, field, ctx)
        rock_style = (palette.GRAY, None, True)
        for rock in g.rocks:
            radius = RADII[rock["size"]]
            for step in range(max(8, int(radius * 8))):
                a = 2 * math.pi * step / max(8, int(radius * 8))
                self.plot(canvas, field, wrap(rock["x"] + radius * math.cos(a), WU),
                          wrap(rock["y"] + radius * math.sin(a) * 0.7, HU), "o" if rock["size"] > 1 else "*", rock_style)
        for b in g.bullets:
            self.plot(canvas, field, b["x"], b["y"], "·" if ctx.glyphs.unicode else ".", (palette.YELLOW, None, True))
        blink = g.safe > 0 and int(g.safe * 8) % 2 == 0 and not ctx.reduced
        if not blink and g.state == "play":
            octant = int(((g.ship["angle"] + math.pi / 2) / (math.pi / 4)) + 0.5) % 8
            glyph = (ARROWS_UNICODE if ctx.glyphs.unicode else ARROWS)[octant]
            self.plot(canvas, field, g.ship["x"], g.ship["y"], glyph, (palette.GREEN, None, True))
        if g.state == "over":
            arcade.banner(canvas, "GAME OVER", f"Score {g.score}   Space: play again   q: leave", good=False)
        arcade.footer(canvas, "left/right turn   up thrust   space fire   p pause   m mute   q quit")

    def plain_lines(self, ctx):
        return ["Rockdrift needs a color terminal."]


def create(api):
    return RockdriftScene()
