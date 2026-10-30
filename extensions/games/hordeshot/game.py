"""Hordeshot: a fixed-shooter homage. A cannon, a descending horde, one shot at a time.

Original code and art. The rules live in `Game`, which has no terminal in it and a seeded random
generator, so it can be tested; `HordeshotScene` only draws it.
"""

import random

from daemonarchy_visual import Scene, arcade, palette

W, H = 48, 20                 # playfield cells
ROWS, COLS = 4, 8             # the horde
ALIEN_W, GAP_X, GAP_Y = 3, 2, 2
SPRITES = ("<o>", "{#}", "/M\\", "|W|")
UNICODE_SPRITES = ("◖●◗", "▐█▌", "▟▲▙", "▐▼▌")
POINTS = (30, 20, 20, 10)
SHIP, SHIP_ASCII = " ▲ ", "/^\\"
PLAYER_SPEED, BULLET_SPEED, BOMB_SPEED = 26.0, 30.0, 11.0


class Game:
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.score, self.lives, self.level = 0, 3, 1
        self.state = "play"              # play, over
        self.reset_wave()
        self.ship_x = (W - 3) / 2.0
        self.invulnerable = 0.0
        self.events = []                 # cue names raised by the last step

    # -- setup

    def reset_wave(self):
        self.aliens = {(r, c) for r in range(ROWS) for c in range(COLS)}
        self.left, self.top, self.direction = 2.0, 1.0, 1
        self.step_clock = 0.0
        self.bullet = None               # [x, y]
        self.bombs = []                  # [x, y]
        self.bomb_clock = 1.0

    # -- geometry

    def alien_x(self, c):
        return self.left + c * (ALIEN_W + GAP_X)

    def alien_y(self, r):
        return self.top + r * GAP_Y

    def step_interval(self):
        """The horde speeds up as it thins and as levels rise."""
        base = 0.55 - 0.04 * (self.level - 1)
        return max(0.06, base * (len(self.aliens) / (ROWS * COLS)) ** 0.7 + 0.04)

    def bottom_alien(self):
        return max((self.alien_y(r) for r, _ in self.aliens), default=0)

    # -- one simulation step

    def step(self, dt, actions):
        self.events = []
        if self.state != "play":
            if "fire" in actions or "select" in actions:
                self.__init__(self.random.random())
            return
        self.invulnerable = max(0.0, self.invulnerable - dt)
        move = (-1 if "left" in actions else 0) + (1 if "right" in actions else 0)
        self.ship_x = min(W - 3.0, max(0.0, self.ship_x + move * PLAYER_SPEED * dt))
        if "fire" in actions and self.bullet is None:
            self.bullet = [self.ship_x + 1, H - 3.0]
            self.events.append("laser")
        self.move_horde(dt)
        self.move_shots(dt)
        self.drop_bombs(dt)
        if not self.aliens:
            self.level += 1
            self.score += 100
            self.events.append("levelup")
            self.reset_wave()
        elif self.bottom_alien() >= H - 3:
            self.lose_game()

    def move_horde(self, dt):
        self.step_clock += dt
        while self.step_clock >= self.step_interval() and self.aliens:
            self.step_clock -= self.step_interval()
            columns = [c for _, c in self.aliens]
            lo, hi = self.alien_x(min(columns)), self.alien_x(max(columns)) + ALIEN_W
            if (self.direction > 0 and hi + 1 >= W) or (self.direction < 0 and lo - 1 <= 0):
                self.direction = -self.direction
                self.top += 1
                self.events.append("blip")
            else:
                self.left += self.direction

    def move_shots(self, dt):
        if self.bullet is not None:
            self.bullet[1] -= BULLET_SPEED * dt
            hit = self.hit_alien(self.bullet[0], self.bullet[1])
            if hit is not None:
                self.aliens.discard(hit)
                self.score += POINTS[hit[0]]
                self.bullet = None
                self.events.append("explode")
            elif self.bullet[1] < 0:
                self.bullet = None
        for bomb in list(self.bombs):
            bomb[1] += BOMB_SPEED * dt
            if bomb[1] >= H - 1:
                self.bombs.remove(bomb)
            elif bomb[1] >= H - 2 and self.ship_x - 0.5 <= bomb[0] <= self.ship_x + 3.5 and not self.invulnerable:
                self.bombs.remove(bomb)
                self.lose_life()

    def hit_alien(self, x, y):
        for r, c in self.aliens:
            ax, ay = self.alien_x(c), self.alien_y(r)
            if ax <= x < ax + ALIEN_W and ay <= y < ay + 1:
                return (r, c)
        return None

    def drop_bombs(self, dt):
        self.bomb_clock -= dt
        if self.bomb_clock > 0 or not self.aliens or len(self.bombs) >= 2 + self.level:
            return
        self.bomb_clock = max(0.35, 1.1 - 0.1 * self.level) * self.random.uniform(0.6, 1.4)
        column = self.random.choice(sorted({c for _, c in self.aliens}))
        row = max(r for r, c in self.aliens if c == column)
        self.bombs.append([self.alien_x(column) + 1, self.alien_y(row) + 1.0])

    def lose_life(self):
        self.lives -= 1
        self.invulnerable = 1.5
        self.events.append("hit")
        if self.lives <= 0:
            self.lose_game()

    def lose_game(self):
        self.state = "over"
        self.events.append("gameover")


class HordeshotScene(Scene):
    min_size = (50, 24)
    title = "Hordeshot"

    def __init__(self, seed=None):
        self.game = Game(seed)
        self.clock = arcade.FixedStep(30)

    def update(self, dt, ctx, actions):
        for _ in range(self.clock.steps(dt)):
            self.game.step(self.clock.step, actions)
            for cue in self.game.events:
                ctx.audio.cue(cue)
            actions = [a for a in actions if a not in ("fire", "select")]  # one press, one shot

    def draw(self, canvas, ctx):
        g, glyphs = self.game, ctx.glyphs
        arcade.hud(canvas, ctx, "HORDESHOT", g.score, g.lives, g.level)
        field = arcade.playfield(canvas, W, H)
        arcade.frame(canvas, field, ctx)
        sprites = UNICODE_SPRITES if glyphs.unicode else SPRITES
        colors = (palette.MAGENTA, palette.RED, palette.ORANGE, palette.YELLOW)
        for r, c in g.aliens:
            canvas.put(field.x + int(g.alien_x(c)), field.y + int(g.alien_y(r)), sprites[r], (colors[r], None, True))
        for x, y in g.bombs:
            canvas.put(field.x + int(x), field.y + int(y), ":", (palette.RED, None, True))
        if g.bullet is not None:
            canvas.put(field.x + int(g.bullet[0]), field.y + int(g.bullet[1]), "|", (palette.WHITE, None, True))
        blink = g.invulnerable > 0 and int(g.invulnerable * 8) % 2 == 0 and not ctx.reduced
        if not blink:
            canvas.put(field.x + int(g.ship_x), field.y + H - 2, SHIP if glyphs.unicode else SHIP_ASCII,
                       (palette.GREEN, None, True))
        if g.state == "over":
            arcade.banner(canvas, "GAME OVER", f"Score {g.score}   Space: play again   q: leave", good=False)
        arcade.footer(canvas, "left/right move   space fire   p pause   m mute   q quit")

    def plain_lines(self, ctx):
        return ["Hordeshot needs a color terminal."]


def create(api):
    return HordeshotScene()
