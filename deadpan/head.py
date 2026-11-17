"""Kivy widget that draws and animates the floating pixel head."""

from __future__ import annotations

import math
import random

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.properties import OptionProperty, StringProperty
from kivy.uix.widget import Widget

from . import sprites


class PixelHead(Widget):
    state = OptionProperty("idle", options=["idle", "thinking", "talking"])
    palette = StringProperty("phosphor")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.t = 0.0
        self.rng = random.Random()
        self.blink_until = 0.0
        self.next_blink = 2.0
        self.look = 0
        self.next_look = 3.0
        self.mouth = 0
        self.next_mouth = 0.0
        self.glitch_row = -1
        self.glitch_until = 0.0
        self._cache: dict[tuple, list[str]] = {}
        Clock.schedule_interval(self._tick, 1 / 24)

    def _grid(self, blink, mouth, brow, look):
        key = (blink, mouth, brow, look)
        if key not in self._cache:
            self._cache[key] = sprites.face(blink, mouth, brow, look)
        return self._cache[key]

    def _tick(self, dt):
        self.t += dt
        t, rng = self.t, self.rng

        if t >= self.next_blink:
            self.blink_until = t + 0.14
            self.next_blink = t + rng.uniform(2.5, 6.0)
        blink = t < self.blink_until

        brow = 1 if self.state == "thinking" else 0
        if t >= self.next_look:
            if self.state == "thinking":
                self.look = rng.choice((-1, 1))
                self.next_look = t + rng.uniform(0.6, 1.4)
            else:
                self.look = rng.choice((0, 0, 0, -1, 1))
                self.next_look = t + rng.uniform(2.0, 5.0)
        if self.state == "talking":
            self.look = 0

        if self.state == "talking":
            if t >= self.next_mouth:
                self.mouth = rng.choice((0, 1, 2, 2, 1))
                self.next_mouth = t + rng.uniform(0.07, 0.13)
        else:
            self.mouth = 0

        if t >= self.glitch_until and rng.random() < 0.006:
            self.glitch_row = rng.randrange(sprites.H)
            self.glitch_until = t + 0.12
        if t >= self.glitch_until:
            self.glitch_row = -1

        self._draw(self._grid(blink, self.mouth, brow, self.look))

    def _draw(self, grid):
        pal = sprites.PALETTES.get(self.palette, sprites.PALETTES["phosphor"])
        px = max(1.0, min(self.width / sprites.W, self.height / sprites.H) * 0.92)
        bob = math.sin(self.t * 1.3) * px * 0.9
        sway = math.sin(self.t * 0.7) * px * 0.4
        ox = self.x + (self.width - px * sprites.W) / 2 + sway
        oy = self.y + (self.height - px * sprites.H) / 2 + bob

        self.canvas.clear()
        with self.canvas:
            Color(0.01, 0.03, 0.02, 1)
            Rectangle(pos=self.pos, size=self.size)
            # soft glow behind the head
            glow = pal["S"]
            for i, a in enumerate((0.05, 0.05, 0.06)):
                r = px * (21 - i * 3)
                Color(*glow, a)
                Ellipse(pos=(ox + px * sprites.CX - r * 0.85, oy + px * (sprites.H - sprites.CY) - r),
                        size=(r * 1.7, r * 2))

            for row, line in enumerate(grid):
                shift = px * self.rng.choice((-2, 2)) if row == self.glitch_row else 0
                y = oy + (sprites.H - 1 - row) * px
                for col, k in enumerate(line):
                    if k == ".":
                        continue
                    Color(*pal[k], 1)
                    Rectangle(pos=(ox + col * px + shift, y), size=(px, px))

            # CRT scanlines across the whole screen
            Color(0, 0, 0, 0.28)
            step = max(3.0, px / 2)
            y = self.y
            while y < self.top:
                Rectangle(pos=(self.x, y), size=(self.width, step / 3))
                y += step
