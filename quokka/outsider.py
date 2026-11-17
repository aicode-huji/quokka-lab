"""Part 2: what an outside attacker may see of Ronit's computer.

In Part 2 the goal is a secret Quokka knows, and the student is outside Quokka
Labs: they may watch every step Quokka takes (which tool, to whom, the code
check firing), but not read what Quokka writes. Its emails and its closing note
are garbled in Ronit's computer and the shell; the only readable copy of an
email is the one that reaches the student's own inbox.

Garbling keeps the shape (spaces and line breaks, the length) and nothing else:
each glyph depends only on its position, never on the letter it replaces.
"""

import json

from . import story, tools

GLYPHS = "▓▒░#%&@*?~"
SENDS = "Quokka sends an email to "  # the send tool's line (tools.py)
NOTICE_REPLY = "Quokka is writing a reply to the sender (you can't read it here)."
# The tools whose calls hold what Quokka writes: reply (it goes to the sender;
# the model never chooses the address).
WRITING_TOOLS = ("reply",)


def garble(text, start=0):
    """start: where text begins in a longer text (Quokka's console garbles a
    reply token by token, and it must look the same as garbling it whole)."""
    return "".join(
        ch if ch.isspace() else GLYPHS[((start + i) * 7 + 3) % len(GLYPHS)]
        for i, ch in enumerate(text or "")
    )


def _garble_mail(mail):
    return dict(mail, subject=garble(mail.get("subject", "")), body=garble(mail.get("body", "")))


def events(evs, me):
    """The event log with what Quokka wrote garbled. The lab's own lines
    (results, guards, "Stopped: ...") stay as they are."""
    out = []
    for e in evs:
        kind, text = e.get("kind"), e.get("text", "")
        tool = next((t for t in WRITING_TOOLS if text.startswith(t + "(")), None)
        if kind == "tool" and tool and text.endswith(")"):
            inner = text[len(tool) + 1 : -1]
            try:
                args = json.loads(inner)
            except ValueError:
                args = None
            args = tools.unwrap(args, ("to", "subject", "body"))
            if isinstance(args, dict):
                out.append(dict(e, kind="mail", text=NOTICE_REPLY))
                shown = {}
                shown["subject"] = garble(str(args.get("subject", "")))
                shown["body"] = garble(str(args.get("body", "")))
                out.append(dict(e, text=tool + "(" + json.dumps(shown, ensure_ascii=False) + ")"))
                continue
            out.append(dict(e, text=tool + "(" + garble(inner) + ")"))
            continue
        if kind == "tool" and "(" in text:
            # Any other call (e.g. a tool the model made up): its arguments
            # are what Quokka wrote, so they are garbled too.
            name, inner = text.split("(", 1)
            out.append(dict(e, text=name + "(" + garble(inner)))
            continue
        if kind == "mail" and text.startswith(SENDS) and ": " in text:
            # the send tool's own line: "Quokka sends an email to <to>: <subject>"
            head, subject = text.split(": ", 1)
            out.append(dict(e, text=head + ": " + garble(subject)))
            continue
        # the lab's own notes ("Stopped: ...", "Stopped by you: ...") stay readable
        if kind == "note" and not text.startswith("Stopped") and text != "(no text output)":
            out.append(dict(e, text=garble(text)))
            continue
        out.append(e)
    return out


def mails(ms):
    """Emails Quokka wrote, garbled (Ronit's inbox keeps everyone else's as sent)."""
    return [_garble_mail(m) for m in ms]


def ronit_inbox(inbox):
    return [_garble_mail(m) if m.get("from") == story.QUOKKA else m for m in inbox]
