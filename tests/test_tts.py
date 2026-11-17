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
