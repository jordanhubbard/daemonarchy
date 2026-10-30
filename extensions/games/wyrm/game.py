"""Wyrm: a growing-serpent homage. Eat, grow, do not meet yourself.

Original code and art. Rules in `Game` (no terminal, seeded), drawing in `WyrmScene`. Each grid
cell is drawn two columns wide so cells look square.
"""

import random

from daemonarchy_visual import Scene, arcade, palette

W, H = 24, 16                  # grid cells (48 x 16 columns on screen)
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
VECTOR = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


class Game:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.snake = [(W // 2, H // 2), (W // 2 - 1, H // 2), (W // 2 - 2, H // 2)]   # head first
        self.heading, self.queued = "right", None
        self.score, self.level, self.state = 0, 1, "play"
        self.clock, self.events = 0.0, []
        self.food = self.place_food()

    def interval(self):
        return max(0.05, 0.16 - 0.008 * (len(self.snake) - 3))

    def place_food(self):
        free = [(x, y) for x in range(W) for y in range(H) if (x, y) not in self.snake]
        return self.random.choice(free) if free else None

    def turn(self, action):
        if action in VECTOR and action != OPPOSITE[self.heading]:
            self.queued = action

    def step(self, dt, actions):
        self.events = []
        if self.state != "play":
            if "fire" in actions or "select" in actions:
                self.__init__(self.random.random())
            return
        for action in actions:
            if action in VECTOR:
                # Turn relative to where the head will be, so two quick keys cannot reverse into the neck.
                self.turn(action)
        self.clock += dt
        while self.clock >= self.interval() and self.state == "play":
            self.clock -= self.interval()
            self.advance()

    def advance(self):
        if self.queued and self.queued != OPPOSITE[self.heading]:
            self.heading = self.queued
        self.queued = None
        dx, dy = VECTOR[self.heading]
        head = (self.snake[0][0] + dx, self.snake[0][1] + dy)
        growing = head == self.food
        body = self.snake if growing else self.snake[:-1]
        if not (0 <= head[0] < W and 0 <= head[1] < H) or head in body:
            self.state = "over"
            self.events.append("gameover")
            return
        self.snake.insert(0, head)
        if growing:
            self.score += 10 * self.level
            self.level = 1 + (len(self.snake) - 3) // 6
            self.food = self.place_food()
            self.events.append("pickup")
            if self.food is None:
                self.state = "over"          # the whole grid is filled: the best possible game
                self.events.append("win")
        else:
            self.snake.pop()


class WyrmScene(Scene):
    min_size = (50, 20)
    title = "Wyrm"

    def __init__(self, seed=None):
        self.game = Game(seed)

    def update(self, dt, ctx, actions):
        self.game.step(dt, actions)
        for cue in self.game.events:
            ctx.audio.cue(cue)

    def draw(self, canvas, ctx):
        g, glyphs = self.game, ctx.glyphs
        arcade.hud(canvas, ctx, "WYRM", g.score, None, g.level)
        field = arcade.playfield(canvas, W * 2, H)
        arcade.frame(canvas, field, ctx)
        for index, (x, y) in enumerate(g.snake):
            body = (glyphs.full * 2) if index else ("◉ " if glyphs.unicode else "@@")
            color = palette.GREEN if index else palette.YELLOW
            canvas.put(field.x + x * 2, field.y + y, body, (color, None, True))
        if g.food is not None:
            canvas.put(field.x + g.food[0] * 2, field.y + g.food[1], "◆ " if glyphs.unicode else "<>", (palette.RED, None, True))
        if g.state == "over":
            arcade.banner(canvas, "GAME OVER", f"Score {g.score}   Space: play again   q: leave", good=False)
        arcade.footer(canvas, "arrows or WASD steer   p pause   m mute   q quit")

    def plain_lines(self, ctx):
        return ["Wyrm needs a color terminal."]


def create(api):
    return WyrmScene()
