"""Shatter: a brick-breaking homage. A paddle, a ball, a wall to take apart.

Original code and art. Rules in `Game` (no terminal, seeded), drawing in `ShatterScene`.
"""

import math
import random

from daemonarchy_visual import Scene, arcade, palette

W, H = 40, 20
BRICK_W, BRICK_ROWS, BRICK_COLS, BRICK_TOP = 4, 5, 10, 2
PADDLE_W, PADDLE_SPEED = 7.0, 30.0
ROW_POINTS = (50, 40, 30, 20, 10)
ROW_COLORS = (palette.RED, palette.ORANGE, palette.YELLOW, palette.GREEN, palette.CYAN)


class Game:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.score, self.lives, self.level = 0, 3, 1
        self.state = "play"
        self.bricks = set()
        self.paddle = (W - PADDLE_W) / 2
        self.events = []
        self.new_wall()
        self.serve()

    def new_wall(self):
        self.bricks = {(r, c) for r in range(BRICK_ROWS) for c in range(BRICK_COLS)}

    def serve(self):
        """The ball waits on the paddle until fire."""
        self.ball, self.velocity, self.stuck = [self.paddle + PADDLE_W / 2, H - 3.0], [0.0, 0.0], True

    def speed(self):
        return 15.0 + 2.5 * (self.level - 1)

    def launch(self):
        angle = math.radians(self.random.uniform(-35, 35))
        s = self.speed()
        self.velocity, self.stuck = [s * math.sin(angle) * 1.4, -s * math.cos(angle)], False

    def step(self, dt, actions):
        self.events = []
        if self.state != "play":
            if "fire" in actions or "select" in actions:
                self.__init__(self.random.random())
            return
        move = (-1 if "left" in actions else 0) + (1 if "right" in actions else 0)
        self.paddle = min(W - PADDLE_W, max(0.0, self.paddle + move * PADDLE_SPEED * dt))
        if self.stuck:
            self.ball = [self.paddle + PADDLE_W / 2, H - 3.0]
            if "fire" in actions:
                self.launch()
            return
        self.move_ball(dt)

    def move_ball(self, dt):
        # Move in small slices so a fast ball cannot pass through a brick or the paddle.
        slices = max(1, int(math.hypot(*self.velocity) * dt / 0.4) + 1)
        for _ in range(slices):
            self.ball[0] += self.velocity[0] * dt / slices
            self.ball[1] += self.velocity[1] * dt / slices
            self.walls()
            if self.hit_brick() or self.hit_paddle():
                pass
            if self.ball[1] >= H - 1:
                return self.drop()

    def walls(self):
        if self.ball[0] < 0:
            self.ball[0], self.velocity[0] = 0.0, abs(self.velocity[0])
            self.events.append("bounce")
        elif self.ball[0] > W - 1:
            self.ball[0], self.velocity[0] = W - 1.0, -abs(self.velocity[0])
            self.events.append("bounce")
        if self.ball[1] < 0:
            self.ball[1], self.velocity[1] = 0.0, abs(self.velocity[1])
            self.events.append("bounce")

    def hit_brick(self):
        row = int(self.ball[1]) - BRICK_TOP
        col = int(self.ball[0] // BRICK_W)
        if (row, col) in self.bricks:
            self.bricks.discard((row, col))
            self.score += ROW_POINTS[row]
            self.velocity[1] = -self.velocity[1]
            self.events.append("hit")
            if not self.bricks:
                self.level += 1
                self.score += 200
                self.events.append("levelup")
                self.new_wall()
                self.serve()
            return True
        return False

    def hit_paddle(self):
        if self.velocity[1] > 0 and int(self.ball[1]) == H - 2 and self.paddle - 0.5 <= self.ball[0] <= self.paddle + PADDLE_W + 0.5:
            offset = (self.ball[0] - (self.paddle + PADDLE_W / 2)) / (PADDLE_W / 2)   # -1 .. 1
            s = self.speed()
            angle = offset * math.radians(60)
            self.velocity = [s * math.sin(angle) * 1.4, -s * math.cos(angle)]
            self.ball[1] = H - 2.5
            self.events.append("bounce")
            return True
        return False

    def drop(self):
        self.lives -= 1
        self.events.append("hit")
        if self.lives <= 0:
            self.state = "over"
            self.events.append("gameover")
        else:
            self.serve()


class ShatterScene(Scene):
    min_size = (42, 24)
    title = "Shatter"

    def __init__(self, seed=None):
        self.game = Game(seed)
        self.clock = arcade.FixedStep(40)

    def update(self, dt, ctx, actions):
        for _ in range(self.clock.steps(dt)):
            self.game.step(self.clock.step, actions)
            for cue in self.game.events:
                ctx.audio.cue(cue)
            actions = [a for a in actions if a not in ("fire", "select")]

    def draw(self, canvas, ctx):
        g, glyphs = self.game, ctx.glyphs
        arcade.hud(canvas, ctx, "SHATTER", g.score, g.lives, g.level)
        field = arcade.playfield(canvas, W, H)
        arcade.frame(canvas, field, ctx)
        block = glyphs.full * (BRICK_W - 1) + " "
        for r, c in g.bricks:
            canvas.put(field.x + c * BRICK_W, field.y + BRICK_TOP + r, block, (ROW_COLORS[r], None, False))
        canvas.put(field.x + int(g.paddle), field.y + H - 1, glyphs.cap * int(PADDLE_W), (palette.WHITE, None, True))
        canvas.put(field.x + int(g.ball[0]), field.y + int(g.ball[1]), "●" if glyphs.unicode else "o",
                   (palette.YELLOW, None, True))
        if g.stuck and g.state == "play":
            arcade.banner(canvas, "", "Space to serve")
        if g.state == "over":
            arcade.banner(canvas, "GAME OVER", f"Score {g.score}   Space: play again   q: leave", good=False)
        arcade.footer(canvas, "left/right move   space serve   p pause   m mute   q quit")

    def plain_lines(self, ctx):
        return ["Shatter needs a color terminal."]


def create(api):
    return ShatterScene()
