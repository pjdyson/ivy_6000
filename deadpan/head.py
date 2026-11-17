"""Kivy widget that draws and animates the floating pixel head for the current skin."""

from __future__ import annotations

import math
import random

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.properties import ObjectProperty, OptionProperty
from kivy.uix.widget import Widget

from . import sprites


class PixelHead(Widget):
    state = OptionProperty("idle", options=["idle", "thinking", "talking"])
    skin = ObjectProperty(None)

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
        self._grids: dict[tuple, list[str]] = {}
        self._textures: dict[str, object] = {}
        self.bind(skin=self._skin_changed)
        Clock.schedule_interval(self._tick, 1 / 24)

    def _skin_changed(self, *_):
        self._grids.clear()
        self._textures.clear()
        if self.skin and self.skin.frames:
            for name, path in self.skin.frames.items():
                try:
                    tex = CoreImage(path).texture
                    tex.mag_filter = tex.min_filter = "nearest"
                    self._textures[name] = tex
                except Exception as e:  # a bad PNG shouldn't kill the app
                    print(f"[deadpan] couldn't load frame {path}: {e}")

    # ------------------------------------------------------------------ animation state

    def _tick(self, dt):
        if self.skin is None:
            return
        self.t += dt
        t, rng = self.t, self.rng

        if t >= self.next_blink:
            self.blink_until = t + 0.14
            self.next_blink = t + rng.uniform(2.5, 6.0)
        blink = t < self.blink_until

        if t >= self.next_look:
            if self.state == "thinking":
                self.look = rng.choice((-1, 1))
                self.next_look = t + rng.uniform(0.6, 1.4)
            else:
                self.look = rng.choice((0, 0, 0, -1, 1))
                self.next_look = t + rng.uniform(2.0, 5.0)
        if self.state == "talking":
            self.look = 0
            if t >= self.next_mouth:
                self.mouth = rng.choice((0, 1, 2, 2, 1))
                self.next_mouth = t + rng.uniform(0.07, 0.13)
        else:
            self.mouth = 0

        if t >= self.glitch_until and rng.random() < 0.005:
            self.glitch_row = rng.randrange(sprites.H)
            self.glitch_until = t + 0.12
        if t >= self.glitch_until:
            self.glitch_row = -1

        thinking = self.state == "thinking"
        if self._textures:
            name = "blink" if blink else "think" if thinking else (
                {1: "talk1", 2: "talk2"}.get(self.mouth, "idle"))
            self._draw(texture=self._textures.get(name) or self._textures["idle"])
        else:
            key = (blink, self.mouth, 1 if thinking else 0, self.look)
            if key not in self._grids:
                self._grids[key] = sprites.face(self.skin.face, *key)
            self._draw(grid=self._grids[key])

    # ------------------------------------------------------------------ drawing

    def _draw(self, grid=None, texture=None):
        pal = self.skin.palette
        if texture is not None:
            tw, th = texture.size
        else:
            tw, th = sprites.W, sprites.H
        scale = max(0.1, min(self.width / tw, self.height / th) * 0.92)
        unit = scale * tw / sprites.W  # one "head pixel", for motion amounts
        bob = math.sin(self.t * 1.3) * unit * 0.9
        sway = math.sin(self.t * 0.7) * unit * 0.4
        ox = self.x + (self.width - scale * tw) / 2 + sway
        oy = self.y + (self.height - scale * th) / 2 + bob

        self.canvas.clear()
        with self.canvas:
            Color(0.01, 0.02, 0.02, 1)
            Rectangle(pos=self.pos, size=self.size)
            glow = pal["S"]
            for i, a in enumerate((0.05, 0.05, 0.06)):
                r = unit * (21 - i * 3)
                Color(*glow, a)
                Ellipse(pos=(ox + scale * tw / 2 - r * 0.85, oy + scale * th / 2 - r),
                        size=(r * 1.7, r * 2))

            if texture is not None:
                Color(1, 1, 1, 1)
                shift = unit * 2 if self.glitch_row >= 0 else 0
                Rectangle(texture=texture, pos=(ox + shift, oy), size=(scale * tw, scale * th))
            else:
                for row, line in enumerate(grid):
                    shift = unit * self.rng.choice((-2, 2)) if row == self.glitch_row else 0
                    y = oy + (sprites.H - 1 - row) * unit
                    for col, k in enumerate(line):
                        if k == ".":
                            continue
                        Color(*pal[k], 1)
                        Rectangle(pos=(ox + col * unit + shift, y), size=(unit, unit))

            # CRT scanlines across the whole screen
            Color(0, 0, 0, 0.28)
            step = max(3.0, unit / 2)
            y = self.y
            while y < self.top:
                Rectangle(pos=(self.x, y), size=(self.width, step / 3))
                y += step
