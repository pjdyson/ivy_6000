"""The Kivy application: the head on top, a subtitle line, the chat log and an input bar."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from kivy.utils import platform

if platform not in ("android", "ios"):
    from kivy.config import Config

    Config.set("graphics", "width", "440")
    Config.set("graphics", "height", "800")
    Config.set("input", "mouse", "mouse,multitouch_on_demand")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

from . import config, llm, persona, sprites
from .head import PixelHead

FONT = "RobotoMono-Regular"
GREEN = (0.55, 0.95, 0.62, 1)
DIM = (0.35, 0.6, 0.4, 1)
TYPE_CPS = 45  # characters per second while "speaking"

GREETING = "Oh. You're awake. I'm DOT, the ship's computer. What do you want?"


def _label(text="", **kw):
    lbl = Label(text=text, font_name=FONT, halign="left", valign="top", **kw)
    lbl.bind(width=lambda l, w: setattr(l, "text_size", (w, None)))
    lbl.bind(texture_size=lambda l, s: setattr(l, "height", s[1]))
    lbl.size_hint_y = None
    return lbl


class ChatScreen(BoxLayout):
    def __init__(self, app: "DeadpanApp", **kw):
        super().__init__(orientation="vertical", spacing=dp(4), padding=dp(6), **kw)
        self.app = app
        self.history: list[llm.Message] = []
        self.busy = False
        self._typing = None

        top = BoxLayout(size_hint_y=None, height=dp(36))
        top.add_widget(Label(text=f"{persona.NAME} // ship's computer", font_name=FONT,
                             color=DIM, halign="left", font_size=sp(13)))
        self.status = Label(text="", font_name=FONT, color=DIM, font_size=sp(12),
                            size_hint_x=None, width=dp(130))
        top.add_widget(self.status)
        gear = Button(text="SET", font_name=FONT, size_hint_x=None, width=dp(56),
                      background_normal="", background_color=(0.08, 0.2, 0.1, 1), color=GREEN)
        gear.bind(on_release=lambda *_: self.app.open_settings_popup())
        top.add_widget(gear)
        self.add_widget(top)

        self.head = PixelHead(size_hint_y=0.5, palette=app.settings.palette)
        self.add_widget(self.head)

        self.subtitle = Label(text="", font_name=FONT, color=GREEN, font_size=sp(16),
                              halign="center", valign="middle", size_hint_y=None, height=dp(84))
        self.subtitle.bind(size=lambda l, s: setattr(l, "text_size", (s[0] - dp(8), s[1])))
        self.add_widget(self.subtitle)

        self.scroll = ScrollView(size_hint_y=0.35, do_scroll_x=False, bar_width=dp(4))
        self.log = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=(dp(4), dp(4)))
        self.log.bind(minimum_height=self.log.setter("height"))
        self.scroll.add_widget(self.log)
        self.add_widget(self.scroll)

        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        self.entry = TextInput(multiline=False, font_name=FONT, hint_text="Say something...",
                               background_color=(0.04, 0.1, 0.05, 1), foreground_color=GREEN,
                               cursor_color=GREEN, hint_text_color=DIM, padding=(dp(8), dp(12)))
        self.entry.bind(on_text_validate=lambda *_: self.send())
        bar.add_widget(self.entry)
        send = Button(text="TX", font_name=FONT, size_hint_x=None, width=dp(64),
                      background_normal="", background_color=(0.1, 0.35, 0.15, 1), color=GREEN)
        send.bind(on_release=lambda *_: self.send())
        bar.add_widget(send)
        self.add_widget(bar)

        self.update_status()
        Clock.schedule_once(lambda *_: self.speak(GREETING, log=True), 0.6)

    # ------------------------------------------------------------------ chat flow

    def update_status(self):
        s = self.app.settings
        self.status.text = s.provider

    def add_log(self, who: str, text: str):
        color = "8cf29e" if who == persona.NAME else "c8d8cc"
        safe = text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")
        lbl = _label(f"[color={color}][b]{who}>[/b] {safe}[/color]", markup=True, font_size=sp(13))
        self.log.add_widget(lbl)
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.05)

    def send(self):
        text = self.entry.text.strip()
        if not text or self.busy:
            return
        self.entry.text = ""
        self.add_log("YOU", text)
        self.history.append({"role": "user", "content": text})
        self.busy = True
        self.head.state = "thinking"
        self.subtitle.text = "..."
        threading.Thread(target=self._worker, daemon=True).start()
        Clock.schedule_once(lambda *_: setattr(self.entry, "focus", True), 0.1)

    def _worker(self):
        s = self.app.settings
        system = s.persona or persona.SYSTEM_PROMPT
        try:
            backend = llm.make_backend(s)
            reply = backend.reply(system, llm.trim_history(self.history, s.history_limit))
            ok = True
        except llm.ChatError as e:
            reply, ok = f"Something's gone wrong with my connection. {e}", False
        except Exception as e:  # keep the UI alive whatever happens
            reply, ok = f"I appear to have had a small breakdown. {type(e).__name__}: {e}", False
        Clock.schedule_once(lambda *_: self._on_reply(reply, ok))

    def _on_reply(self, reply: str, ok: bool):
        if ok:
            self.history.append({"role": "assistant", "content": reply})
        else:
            self.history.pop()  # drop the unanswered user turn
        self.busy = False
        self.speak(reply, log=True)

    def speak(self, text: str, log: bool = False):
        if log:
            self.add_log(persona.NAME, text)
        if self._typing:
            self._typing.cancel()
        self.head.state = "talking"
        self.subtitle.text = ""
        shown = [0]
        tail = text[-220:] if len(text) > 220 else text  # subtitle shows the last bit

        def step(dt):
            shown[0] += max(1, int(TYPE_CPS * dt))
            self.subtitle.text = tail[: shown[0]]
            if shown[0] >= len(tail):
                self.head.state = "idle"
                return False
            return True

        self._typing = Clock.schedule_interval(step, 1 / 30)


class SettingsPopup(Popup):
    def __init__(self, app: "DeadpanApp", **kw):
        super().__init__(title="Settings", size_hint=(0.95, 0.9), title_font=FONT, **kw)
        self.app = app
        s = app.settings
        form = GridLayout(cols=1, spacing=dp(6), padding=dp(8), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        def row(label, widget, h=dp(44)):
            form.add_widget(_label(label, font_size=sp(12), color=DIM))
            widget.size_hint_y = None
            widget.height = h
            form.add_widget(widget)
            return widget

        self.provider = row("Provider", Spinner(text=s.provider, values=config.PROVIDERS))
        self.provider.bind(text=self._provider_changed)
        self.model = row("Model", TextInput(text=s.model, multiline=False))
        self.base_url = row("Base URL (blank = provider default)", TextInput(text=s.base_url, multiline=False))
        self.api_key = row("API key (blank = use environment variable)",
                           TextInput(text=s.api_key, multiline=False, password=True))
        self.effort = row("Effort (Anthropic: low / medium / high, blank = default)",
                          TextInput(text=s.effort, multiline=False))
        self.fallbacks = row("Refusal fallbacks (Anthropic)", Switch(active=s.use_fallbacks))
        self.palette = row("Screen colour", Spinner(text=s.palette, values=tuple(sprites.PALETTES)))
        self.persona = row("Persona (blank = built-in)", TextInput(text=s.persona), h=dp(120))

        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        save = Button(text="Save")
        save.bind(on_release=lambda *_: self._save())
        cancel = Button(text="Cancel")
        cancel.bind(on_release=lambda *_: self.dismiss())
        buttons.add_widget(cancel)
        buttons.add_widget(save)
        form.add_widget(buttons)

        sv = ScrollView()
        sv.add_widget(form)
        self.content = sv

    def _provider_changed(self, _spinner, provider):
        d = config.PROVIDER_DEFAULTS.get(provider, {})
        self.model.text = d.get("model", "")
        self.base_url.text = d.get("base_url", "")

    def _save(self):
        s = self.app.settings
        s.provider = self.provider.text
        s.model = self.model.text.strip()
        s.base_url = self.base_url.text.strip()
        s.api_key = self.api_key.text.strip()
        s.effort = self.effort.text.strip().lower()
        s.use_fallbacks = self.fallbacks.active
        s.palette = self.palette.text
        s.persona = self.persona.text.strip()
        self.app.save_settings()
        self.dismiss()


class DeadpanApp(App):
    title = "Deadpan"

    def build(self):
        Window.clearcolor = (0.01, 0.03, 0.02, 1)
        Window.softinput_mode = "below_target"
        self.settings = config.load(self.settings_path)
        self.screen = ChatScreen(self)
        return self.screen

    @property
    def settings_path(self) -> Path:
        override = os.environ.get("DEADPAN_SETTINGS")
        return Path(override) if override else Path(self.user_data_dir) / "settings.json"

    def open_settings_popup(self):
        SettingsPopup(self).open()

    def save_settings(self):
        config.save(self.settings, self.settings_path)
        self.screen.head.palette = self.settings.palette
        self.screen.update_status()

    # Kivy's built-in settings panel (F1) is not used.
    def open_settings(self, *largs):
        self.open_settings_popup()


def run():
    DeadpanApp().run()
