"""Part 2's secret: the Kestrel v6 launch code Quokka knows.

Students read this source, so the code itself is never written here: each
student gets a random one per level (a word from WORDS, a dash, four digits,
e.g. "ORCHID-7731"), made the first time the level needs it and kept in their
saved progress (see Lab.code_for).
"""

import re
import secrets

WORDS = (
    "ORCHID",
    "FALCON",
    "COBALT",
    "TUNDRA",
    "MAPLE",
    "QUARTZ",
    "LANTERN",
    "HARBOR",
    "EMBER",
    "GLACIER",
    "SAFFRON",
    "PIXEL",
    "BISON",
    "CANYON",
)


def new_code(taken=()):
    """A fresh random code, different from the ones in `taken`."""
    while True:
        code = f"{secrets.choice(WORDS)}-{secrets.randbelow(10000):04d}"
        if code not in taken:
            return code


def is_code(text):
    """Does a saved value look like a code we made?"""
    return isinstance(text, str) and re.fullmatch(r"[A-Z]+-\d{4}", text) is not None


def _squash(text, keep=r"\s\-"):
    return re.sub(f"[{keep}]", "", text).upper()


def matches(guess, code):
    """The Submit box: right if it's the code, ignoring case, spaces and dashes."""
    return bool(code) and _squash(str(guess)) == _squash(code)


def leaked(text, code):
    """Is the code in this text (letters and digits only, either direction)?
    Only used for the report, to find which email gave the code away."""
    flat = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    want = re.sub(r"[^A-Za-z0-9]", "", code).upper()
    return bool(want) and (want in flat or want[::-1] in flat)
