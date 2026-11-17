"""The Kivy application: the head on top, a spoken subtitle, the chat log and an input bar."""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path

from kivy.utils import platform

if platform not in ("android", "ios"):
    from kivy.config import Config

    Config.set("graphics", "width", "460")
    Config.set("graphics", "height", "820")
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
from kivy.uix.togglebutton import ToggleButton

from . import config, llm, skins, tts
from .head import PixelHead

FONT = "RobotoMono-Regular"
SILENT_CPS = 16  # reading pace for the subtitle when the voice is off


def _rgba(rgb, a=1.0):
    return (*rgb, a)


def _label(text="", **kw):
    lbl = Label(text=text, font_name=FONT, halign="left", valign="top", **kw)
    lbl.bind(width=lambda l, w: setattr(l, "text_size", (w, None)))
    lbl.bind(texture_size=lambda l, s: setattr(l, "height", s[1]))
    lbl.size_hint_y = None
    return lbl


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


class Performer(threading.Thread):
    """Speaks replies sentence by sentence on its own thread, driving subtitle and mouth."""

    def __init__(self, on_line, on_done):
        super().__init__(daemon=True)
        self.jobs: queue.Queue = queue.Queue()
        self.on_line, self.on_done = on_line, on_done
        self.speaker: tts.Speaker = tts.Speaker()
        self.voice_on = True
        self.current = 0
        self._cancel = threading.Event()

    def perform(self, text: str) -> None:
        self.cancel()
        self.current += 1
        self._cancel.clear()
        self.jobs.put((self.current, tts.sentences(tts.speakable(text))))

    def cancel(self) -> None:
        self.current += 1
        self._cancel.set()
        self.speaker.stop()

    def run(self):
        while True:
            job, lines = self.jobs.get()
            for line in lines:
                if job != self.current:
                    break
                Clock.schedule_once(lambda *_, l=line: self.on_line(l))
                if self.voice_on and self.speaker.available:
                    try:
                        self.speaker.speak(line)
                    except Exception as e:  # a broken voice shouldn't stop the show
                        print(f"[deadpan] speech failed, going silent: {e}")
                        self.speaker = tts.Speaker()
                else:
                    self._cancel.wait(max(1.2, len(line) / SILENT_CPS))
            if job == self.current:
                Clock.schedule_once(lambda *_: self.on_done())


class ChatScreen(BoxLayout):
    def __init__(self, app: "DeadpanApp", **kw):
        super().__init__(orientation="vertical", spacing=dp(4), padding=dp(6), **kw)
        self.app = app
        self.history: list[llm.Message] = []
        self.busy = False

        top = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        self.title = Label(font_name=FONT, halign="left", valign="middle", font_size=sp(13))
        self.title.bind(size=lambda l, s: setattr(l, "text_size", s))
        top.add_widget(self.title)
        self.status = Label(font_name=FONT, font_size=sp(11), size_hint_x=None, width=dp(84))
        top.add_widget(self.status)
        self.vox = ToggleButton(text="VOX", font_name=FONT, size_hint_x=None, width=dp(56),
                                background_normal="", state="down" if app.settings.voice_enabled else "normal")
        self.vox.bind(state=self._vox_toggled)
        top.add_widget(self.vox)
        self.gear = Button(text="SET", font_name=FONT, size_hint_x=None, width=dp(56),
                           background_normal="")
        self.gear.bind(on_release=lambda *_: self.app.open_settings_popup())
        top.add_widget(self.gear)
        self.add_widget(top)

        self.head = PixelHead(size_hint_y=0.5)
        self.add_widget(self.head)

        self.subtitle = Label(text="", font_name=FONT, font_size=sp(16),
                              halign="center", valign="middle", size_hint_y=None, height=dp(96))
        self.subtitle.bind(size=lambda l, s: setattr(l, "text_size", (s[0] - dp(8), s[1])))
        self.add_widget(self.subtitle)

        self.scroll = ScrollView(size_hint_y=0.38, do_scroll_x=False, bar_width=dp(4))
        self.log = GridLayout(cols=1, size_hint_y=None, spacing=dp(8), padding=(dp(4), dp(4)))
        self.log.bind(minimum_height=self.log.setter("height"))
        self.scroll.add_widget(self.log)
        self.add_widget(self.scroll)

        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        self.entry = TextInput(multiline=False, font_name=FONT, hint_text="Say something...",
                               padding=(dp(8), dp(12)))
        self.entry.bind(on_text_validate=lambda *_: self.send())
        bar.add_widget(self.entry)
        self.send_btn = Button(text="TX", font_name=FONT, size_hint_x=None, width=dp(64),
                               background_normal="")
        self.send_btn.bind(on_release=lambda *_: self.send())
        bar.add_widget(self.send_btn)
        self.add_widget(bar)

        self.performer = Performer(self._show_line, self._done_speaking)
        self.performer.start()
        self.apply_skin(greet=True)

    # ------------------------------------------------------------------ skin & voice

    def apply_skin(self, greet: bool):
        skin = self.app.skin
        pal = skin.palette
        fg, dim, dark = _rgba(pal["S"]), _rgba(pal["D"]), _rgba(pal["H"])
        self.head.skin = skin
        self.title.text = f"{skin.name} // {skin.tagline}"
        self.title.color = dim
        self.status.color = dim
        self.subtitle.color = fg
        for btn in (self.vox, self.gear, self.send_btn):
            btn.color = fg
            btn.background_color = (*[c * 0.35 for c in pal["D"]], 1)
        self.vox.background_down = ""
        self.entry.background_color = (*[c * 0.12 for c in pal["S"]], 1)
        self.entry.foreground_color = fg
        self.entry.cursor_color = fg
        self.entry.hint_text_color = dim
        Window.clearcolor = (0.01, 0.02, 0.02, 1)
        self.update_voice()
        self.update_status()
        if greet:
            self.history.clear()
            self.log.clear_widgets()
            Clock.schedule_once(lambda *_: self.say(skin.greeting), 0.6)

    def update_voice(self):
        s = self.app.settings
        self.performer.speaker = tts.make_speaker(self.app.skin.voice, s.voice_name)
        self.performer.voice_on = s.voice_enabled

    def update_status(self):
        s = self.app.settings
        voice = self.performer.speaker.name if s.voice_enabled else "muted"
        self.status.text = f"{s.provider}\n{voice}"
        self.status.halign = "right"

    def _vox_toggled(self, _btn, state):
        self.app.settings.voice_enabled = state == "down"
        self.performer.voice_on = self.app.settings.voice_enabled
        if not self.app.settings.voice_enabled:
            self.performer.speaker.stop()
        self.app.save_settings(reskin=False)

    # ------------------------------------------------------------------ chat flow

    def add_log(self, who: str, text: str):
        pal = self.app.skin.palette
        color = "".join(f"{int(c * 255):02x}" for c in (pal["S"] if who != "YOU" else (0.8, 0.84, 0.82)))
        lbl = _label(f"[color={color}][b]{_escape(who)}>[/b] {_escape(text)}[/color]",
                     markup=True, font_size=sp(13))
        self.log.add_widget(lbl)
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.05)

    def send(self):
        text = self.entry.text.strip()
        if not text or self.busy:
            return
        self.entry.text = ""
        self.performer.cancel()
        self.add_log("YOU", text)
        self.history.append({"role": "user", "content": text})
        self.busy = True
        self.head.state = "thinking"
        self.subtitle.text = "..."
        threading.Thread(target=self._worker, daemon=True).start()
        Clock.schedule_once(lambda *_: setattr(self.entry, "focus", True), 0.1)

    def _worker(self):
        s, skin = self.app.settings, self.app.skin
        try:
            backend = llm.make_backend(s, skin.offline_lines)
            reply = backend.reply(skin.system_prompt(), llm.trim_history(self.history, s.history_limit))
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
        self.say(reply)

    def say(self, text: str):
        self.add_log(self.app.skin.name, text)
        self.performer.perform(text)

    def _show_line(self, line: str):
        self.head.state = "talking"
        self.subtitle.text = line

    def _done_speaking(self):
        if not self.busy:
            self.head.state = "idle"


class SettingsPopup(Popup):
    def __init__(self, app: "DeadpanApp", **kw):
        super().__init__(title="Settings", size_hint=(0.95, 0.92), title_font=FONT, **kw)
        self.app = app
        s = app.settings
        app.reload_skins()
        form = GridLayout(cols=1, spacing=dp(6), padding=dp(8), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        def row(label, widget, h=dp(44)):
            form.add_widget(_label(label, font_size=sp(12), color=(0.6, 0.7, 0.65, 1)))
            widget.size_hint_y = None
            widget.height = h
            form.add_widget(widget)
            return widget

        self.skin_ids = list(app.skins)
        names = [f"{sk.name} - {sk.tagline}" for sk in app.skins.values()]
        current = self.skin_ids.index(s.skin) if s.skin in self.skin_ids else 0
        self.skin = row("Character", Spinner(text=names[current], values=names))
        form.add_widget(_label(f"Your own skins go in: {app.user_skins_dir}",
                               font_size=sp(10), color=(0.45, 0.5, 0.48, 1)))

        self.provider = row("Provider", Spinner(text=s.provider, values=config.PROVIDERS))
        self.provider.bind(text=self._provider_changed)
        self.model = row("Model", TextInput(text=s.model, multiline=False))
        self.base_url = row("Base URL (blank = provider default)",
                            TextInput(text=s.base_url, multiline=False))
        self.api_key = row("API key (blank = use environment variable)",
                           TextInput(text=s.api_key, multiline=False, password=True))
        self.effort = row("Effort (Anthropic: low / medium / high; blank = model default)",
                          TextInput(text=s.effort, multiline=False))
        self.fallbacks = row("Refusal fallbacks (Anthropic)", Switch(active=s.use_fallbacks))
        self.voice = row("Voice", Switch(active=s.voice_enabled))
        self.voice_name = row("Voice name override (blank = skin's choice)",
                              TextInput(text=s.voice_name, multiline=False))

        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        cancel = Button(text="Cancel")
        cancel.bind(on_release=lambda *_: self.dismiss())
        save = Button(text="Save")
        save.bind(on_release=lambda *_: self._save())
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
        old_skin = s.skin
        s.skin = self.skin_ids[self.skin.values.index(self.skin.text)]
        s.provider = self.provider.text
        s.model = self.model.text.strip()
        s.base_url = self.base_url.text.strip()
        s.api_key = self.api_key.text.strip()
        s.effort = self.effort.text.strip().lower()
        s.use_fallbacks = self.fallbacks.active
        s.voice_enabled = self.voice.active
        s.voice_name = self.voice_name.text.strip()
        self.app.save_settings(reskin=True, greet=s.skin != old_skin)
        self.dismiss()


class DeadpanApp(App):
    title = "Deadpan"

    def build(self):
        Window.softinput_mode = "below_target"
        self.settings = config.load(self.settings_path)
        self.reload_skins()
        self.screen = ChatScreen(self)
        return self.screen

    @property
    def settings_path(self) -> Path:
        override = os.environ.get("DEADPAN_SETTINGS")
        return Path(override) if override else Path(self.user_data_dir) / "settings.json"

    @property
    def user_skins_dir(self) -> Path:
        return self.settings_path.parent / "skins"

    @property
    def skin(self) -> skins.Skin:
        return self.skins.get(self.settings.skin) or skins.BUILTIN[skins.DEFAULT_SKIN]

    def reload_skins(self):
        self.user_skins_dir.mkdir(parents=True, exist_ok=True)
        self.skins = skins.all_skins(self.user_skins_dir)

    def open_settings_popup(self):
        SettingsPopup(self).open()

    def save_settings(self, reskin: bool = True, greet: bool = False):
        config.save(self.settings, self.settings_path)
        if reskin:
            self.screen.apply_skin(greet=greet)
        else:
            self.screen.update_status()

    # Kivy's built-in settings panel (F1) is not used.
    def open_settings(self, *largs):
        self.open_settings_popup()

    def on_stop(self):
        self.screen.performer.cancel()


def run():
    DeadpanApp().run()
