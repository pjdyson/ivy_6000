"""Kivy widget that draws and animates the floating pixel head for the current skin."""

from __future__ import annotations

import itertools
import math
import random
import threading

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.graphics.texture import Texture
from kivy.properties import ObjectProperty, OptionProperty
from kivy.uix.widget import Widget

from . import portrait

# Frame states the animation uses: (blink, mouth, brow, look).
STATES = [(False, 0, 0, 0), (True, 0, 0, 0), (False, 1, 0, 0), (False, 2, 0, 0)] + [
    (b, 0, br, lk) for b, br, lk in itertools.product((False, True), (0, 1), (-1, 0, 1))
]


def _texture_from_rgba(rgba: bytes, w: int, h: int) -> Texture:
    tex = Texture.create(size=(w, h), colorfmt="rgba")
    tex.blit_buffer(rgba, colorfmt="rgba", bufferfmt="ubyte")
    tex.flip_vertical()  # our rows are top-first; GL textures are bottom-first
    tex.mag_filter = tex.min_filter = "nearest"
    return tex


class PixelHead(Widget):
    state = OptionProperty("idle", options=["idle", "thinking", "talking", "listening"])
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
        self.glitch_until = 0.0
        self.glitch_shift = 0
        self._rgba: dict[tuple, bytes] = {}       # filled by the background renderer
        self._textures: dict[object, Texture] = {}
        self._generation = 0
        self.bind(skin=self._skin_changed)
        Clock.schedule_interval(self._tick, 1 / 24)

    # ------------------------------------------------------------------ frames

    def _skin_changed(self, *_):
        self._generation += 1
        self._rgba = {}
        self._textures = {}
        if self.skin is None:
            return
        if self.skin.frames:  # image skin: load PNGs
            for name, path in self.skin.frames.items():
                try:
                    tex = CoreImage(path).texture
                    tex.mag_filter = tex.min_filter = "nearest"
                    self._textures[name] = tex
                except Exception as e:  # a bad PNG shouldn't kill the app
                    print(f"[ivy-6000] couldn't load frame {path}: {e}")
            return
        # Generated portrait: render the idle frame now, the rest in the background.
        style, gen = self.skin.face, self._generation
        self._rgba[STATES[0]] = portrait.render(style, *STATES[0])

        def prerender():
            for key in STATES[1:]:
                if gen != self._generation:
                    return
                rgba = portrait.render(style, *key)
                if gen == self._generation:
                    self._rgba[key] = rgba

        threading.Thread(target=prerender, daemon=True).start()

    def _portrait_texture(self, key):
        tex = self._textures.get(key)
        if tex is None:
            rgba = self._rgba.get(key)
            if rgba is None:  # not rendered yet: fall back to the nearest ready frame
                for alt in ((key[0], 0, key[2], key[3]), (key[0], 0, 0, 0), STATES[0]):
                    if alt in self._rgba:
                        return self._portrait_texture(alt)
                return None
            tex = self._textures[key] = _texture_from_rgba(rgba, portrait.W, portrait.H)
        return tex

    # ------------------------------------------------------------------ animation

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
            if self.state in ("thinking", "listening"):
                self.look = rng.choice((-1, 1))
                self.next_look = t + rng.uniform(0.6, 1.4)
            else:
                self.look = rng.choice((0, 0, 0, -1, 1))
                self.next_look = t + rng.uniform(2.0, 5.0)
        if self.state == "talking":
            self.look = 0
            blink = blink and self.mouth == 0
            if t >= self.next_mouth:
                self.mouth = rng.choice((0, 1, 2, 2, 1))
                self.next_mouth = t + rng.uniform(0.07, 0.13)
        else:
            self.mouth = 0

        if t >= self.glitch_until and rng.random() < 0.005:
            self.glitch_shift = rng.choice((-2, 2))
            self.glitch_until = t + 0.1
        if t >= self.glitch_until:
            self.glitch_shift = 0

        thinking = self.state in ("thinking", "listening")
        if self.skin.frames:
            name = "blink" if blink else "think" if thinking else (
                {1: "talk1", 2: "talk2"}.get(self.mouth, "idle"))
            tex = self._textures.get(name) or self._textures.get("idle")
        else:
            tex = self._portrait_texture((blink, self.mouth, 1 if thinking else 0, self.look))
        if tex is not None:
            self._draw(tex)

    def _draw(self, texture):
        tint = self.skin.face.tint if not self.skin.frames else self.skin.palette["S"]
        tw, th = texture.size
        scale = max(0.1, min(self.width / tw, self.height / th) * 0.92)
        unit = scale * tw / portrait.W  # roughly one portrait pixel
        bob = math.sin(self.t * 1.3) * unit * 1.6
        sway = math.sin(self.t * 0.7) * unit * 0.7
        ox = self.x + (self.width - scale * tw) / 2 + sway + self.glitch_shift * unit
        oy = self.y + (self.height - scale * th) / 2 + bob

        self.canvas.clear()
        with self.canvas:
            Color(0.045, 0.034, 0.028, 1)                 # dark warm backdrop, like an oil portrait
            Rectangle(pos=self.pos, size=self.size)
            for i, a in enumerate((0.035, 0.04, 0.05)):   # faint warm halo, nudged by the screen colour
                r = unit * (24 - i * 3)
                Color(*[0.8 * w + 0.2 * c for w, c in zip((0.9, 0.55, 0.3), tint)], a)
                Ellipse(pos=(ox + scale * tw / 2 - r * 0.85, oy + scale * th / 2 - r),
                        size=(r * 1.7, r * 2))
            Color(1, 1, 1, 1)
            Rectangle(texture=texture, pos=(ox, oy), size=(scale * tw, scale * th))

            # CRT scanlines across the whole screen
            Color(0, 0, 0, 0.12)
            step = max(3.0, unit)
            y = self.y
            while y < self.top:
                Rectangle(pos=(self.x, y), size=(self.width, step / 3))
                y += step
