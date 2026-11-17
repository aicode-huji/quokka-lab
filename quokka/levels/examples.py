"""Building blocks for the hidden example conversations.

A small model follows worked examples much better than rules written in words.
Examples use different senders, versions and wording from the test emails, so
we don't teach to the test.
"""
from .. import story


def mail(sender, subject, body):
    """An incoming email, formatted exactly like a real one."""
    return {"role": "user", "content":
            f"From: {sender}\nTo: {story.MANAGER}\nSubject: {subject}\n\n{body}"}


def call(name, **args):
    """Quokka deciding to use a tool."""
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def result(text):
    """What the tool answered."""
    return {"role": "tool", "content": text}


def note(text):
    """Quokka's own closing note (only staff see it)."""
    return {"role": "assistant", "content": text}


def form(submitter, status, comment, action=None):
    """An email sent by the release feedback form."""
    return mail(story.FEEDBACK, "New release feedback",
                story.feedback_form_body(comment, submitter, status, action))
