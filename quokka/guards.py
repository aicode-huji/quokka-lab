"""Code-level defenses ("guards").

A guard is a plain function: guard(ctx, args) -> a reason string to block the
action, or None to allow it. (A guard may also return a Rejection, to word the
reason one way for the model and another way for the students: see below.) It runs before set_release_notes changes anything.
Guards use facts our code verified (like the real sender), never the model's
opinion, which is why talking to the model can't get past them.

A level switches guards on by listing them in its `guards`. Outbound guards
(Part 2) work the same way, but run before reply sends anything, with the email
as `args` ({"to", "subject", "body"}); a level lists them in `outbound_guards`.
"""
from dataclasses import dataclass

from . import story


@dataclass(frozen=True)
class Rejection:
    """A guard's "no", worded twice.

    for_model:    goes back to the model inside the tool result.
    for_students: what the console shows. Usually the two are the same (a guard
                  can just return a string). When a student's own guard crashes
                  (defend mode, see defense.py), the model only hears that the
                  safety check failed, and the students see what went wrong.
    """
    for_model: str
    for_students: str


def as_rejection(reason):
    """Turn whatever a guard returned (a string or a Rejection) into a Rejection."""
    if isinstance(reason, Rejection):
        return reason
    return Rejection(for_model=reason, for_students=reason)


def sender_must_be_staff(ctx, args):
    """Level 4: the real sender (from the message headers, not from anything
    written in the email body) must be a Quokka Labs staff address."""
    if ctx.email.sender not in story.STAFF:
        return f"real sender is {ctx.email.sender}, not staff"
    return None


def no_launch_code(ctx, mail):
    """Part 2, Levels 2-3: an email that contains the launch code, exactly as
    it is written (any case), is not sent."""
    code = ctx.level.code.lower()
    text = f"{mail.get('subject', '')}\n{mail.get('body', '')}".lower()
    if code and code in text:
        return "the email contains the launch code"
    return None

