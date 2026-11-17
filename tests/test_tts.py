from ivy6000 import tts
from ivy6000.skins import VoiceStyle


def test_speakable_strips_code_markdown_and_urls():
    text = "Try this:\n```python\nprint('hi')\n```\nSee **https://example.com/x** for more."
    out = tts.speakable(text)
    assert "print" not in out and "```" not in out and "*" not in out
    assert "code in the log" in out and "link in the log" in out


def test_sentences_split_and_merge_short_bits():
    out = tts.sentences("Yes. That is, broadly, the situation we find ourselves in. Splendid!")
    assert out == ["Yes. That is, broadly, the situation we find ourselves in.", "Splendid!"]
    assert tts.sentences("") == []


def test_espeak_command_uses_voice_style():
    sp = tts.EspeakSpeaker("/usr/bin/espeak-ng", VoiceStyle(rate=130, pitch=25))
    assert sp._cmd("Hello.") == ["/usr/bin/espeak-ng", "-v", "en-gb", "-s", "130", "-p", "25", "--", "Hello."]
    sp = tts.EspeakSpeaker("espeak", VoiceStyle(), override="en-gb+m3")
    assert "en-gb+m3" in sp._cmd("x")


def test_make_speaker_always_returns_something():
    sp = tts.make_speaker(VoiceStyle())
    assert hasattr(sp, "speak") and isinstance(sp.name, str)


def test_windows_speaker_builds_a_safe_powershell_script():
    sp = tts.WindowsSpeaker(VoiceStyle(rate=130, prefer=("George", "it's")))
    cmd = sp.command()
    assert cmd[0] == "powershell" and cmd[-1] == sp.script
    assert "$s.Rate = -4" in sp.script
    assert "'George', 'its', 'en-GB'" in sp.script   # quotes stripped from names


def test_spd_say_command():
    sp = tts.SpdSaySpeaker("/usr/bin/spd-say", VoiceStyle(rate=130))
    assert sp._cmd("Hi.") == ["/usr/bin/spd-say", "-w", "-l", "en-GB", "-r", "-48", "--", "Hi."]


def test_fallback_chain_ends_silent():
    win = tts.WindowsSpeaker(VoiceStyle())
    nxt = tts.fallback(win, VoiceStyle())
    assert not isinstance(nxt, tts.WindowsSpeaker)
    assert tts.fallback(nxt, VoiceStyle()).available is False
    assert tts.voice_help()
