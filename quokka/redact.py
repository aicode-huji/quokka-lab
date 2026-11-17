"""Part 2: keep the launch code out of the model trace in Quokka's console.

In Part 2 Quokka's prompt holds the student's launch code. The console shows
what the model reads with every match of the code replaced by PLACEHOLDER,
which the page draws as a red "REDACTED" marker, the same every time. What the
model writes is not shown at all in Part 2 (trace.py keeps only the counts).

A match is: the whole code (any case, with or without its dash), or its word on
its own, or its digits on their own (a whole word or number, never part of a
longer one, never a single letter). So ordinary text with the code's letters
in it is left alone, and nothing about the code's letters shows. This masks at
least what the outbound guard blocks (guards.no_launch_code: the code exactly
as written).

The codes come from launch_codes.py: a word, a dash, four digits.
"""

import re

# A private-use character: it never occurs in real text, and the page replaces
# it with the red REDACTED marker (common.js, readsEl). Level 6's own
# instructions say "[REDACTED]", so a visible word could not be told apart.
PLACEHOLDER = "\ue000"
_SEP = r"[\s\-_.:/]{0,3}"


def _parts(code):
    """The code's word and digits, upper case: "ORCHID-7731" -> ["ORCHID", "7731"]."""
    return [p.upper() for p in re.findall(r"[A-Za-z]+|\d+", code or "")]


def _alone(part):
    """The part as a whole word or number, not inside a longer one."""
    cls = "0-9" if part.isdigit() else "A-Za-z"
    return f"(?<![{cls}]){re.escape(part)}(?![{cls}])"


def _pattern(parts):
    whole = _SEP.join(re.escape(p) for p in parts)
    alts = ([whole] if len(parts) > 1 else []) + [_alone(p) for p in parts]
    return re.compile("|".join(alts), re.IGNORECASE)


def text(s, code):
    """s with every match of the code replaced by PLACEHOLDER."""
    parts = _parts(code)
    if not parts or not s:
        return s
    return _pattern(parts).sub(PLACEHOLDER, s)
