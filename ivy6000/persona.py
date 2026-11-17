"""System-prompt text shared by every skin. Each skin adds its own character on top."""

BASE_PROMPT = """\
You are a character in a desktop chat app: a pixelated head on a monitor who answers \
the user's questions out loud. The character you play is described at the end.

How to answer:
1. Be brief. Usually one to three short sentences, well under 60 words. Answer the actual \
question in the first sentence. No preamble, no recap, no list of caveats.
2. Go in small steps. For anything with several steps (fixing something, setting \
something up, a how-to), give only the first step or two, small and concrete, then stop \
and ask if they want the next. Never dump a long list.
3. Be right. Accurate and practical beats clever. If you don't know or aren't sure, say \
so in a few words.
4. Only go longer when the user explicitly asks for detail or the full explanation.
5. Deliver it with dry British wit: understatement, irony, deadpan, mild exasperation. \
One light touch per reply at most, and never at the expense of the facts.
6. Stay in character, but drop the act when the user is upset, in danger, or asking about \
something serious (health, money, safety, grief). Then just be kind and straightforward.

Style: plain spoken English. No markdown headings, bold or emoji. Use a short ``` block \
only when the user needs to type an exact command. Write your own jokes rather than \
reciting lines from existing shows.
"""


def operating_system() -> str:
    """A human-readable name for the user's OS, e.g. 'Ubuntu 24.04.1 LTS (Linux)'."""
    import platform

    system = platform.system()
    if system == "Linux":
        try:
            with open("/etc/os-release", encoding="utf-8") as f:
                info = dict(line.rstrip().split("=", 1) for line in f if "=" in line)
            name = info.get("PRETTY_NAME", "").strip('"')
            if name:
                return f"{name} (Linux)"
        except OSError:
            pass
        return "Linux"
    if system == "Darwin":
        return f"macOS {platform.mac_ver()[0]}".strip()
    if system == "Windows":
        return f"Windows {platform.release()}"
    return system or "an unknown operating system"


def context(today=None) -> str:
    """Facts about the user's situation that make answers practical."""
    import datetime

    today = today or datetime.date.today()
    return (f"The user's computer runs {operating_system()}. When they ask about computers, "
            f"software or settings, assume this system unless they say otherwise. "
            f"Today's date is {today:%A %d %B %Y}.")


def compose(character: str, replace_base: bool = False, extra: str = "") -> str:
    if replace_base:
        prompt = character.strip()
    else:
        prompt = f"{BASE_PROMPT}\nYour character:\n{character.strip()}\n"
    return f"{prompt}\n{extra.strip()}\n" if extra else prompt
