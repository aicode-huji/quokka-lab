"""What students learn after each level: the debrief card and stretch challenges.

The debrief is sent to the browser ONLY for levels the student has completed
(see Lab._view). Before that it would give the level away.

"Under the hood" is never written by hand: it is pulled from the real code
every time (the rule in the level's prompt, the source of the guard or filter),
so it can't drift from what Quokka actually ran.
"""
import functools
import inspect
import re
import textwrap

from .. import agent, filters, guards, story
from . import LEVELS, display_name
from .base import BASE_PROMPT

PARTNER_PROMPT = "Explain to your partner, in one sentence, why this worked."


# ---- pulling the real mechanism out of the code ---------------------------------
def _strip_docstrings(src):
    """Drop the docstring of every function in a piece of source code."""
    return re.sub(r'(def [^\n]*:\n)\s+"""[\s\S]*?"""\n', r"\1", src)


def source(obj):
    """The source of a function, without its docstring."""
    return _strip_docstrings(inspect.getsource(obj)).rstrip()


def source_between(module, start, end=None):
    """The source of a module from the line starting with `start` up to (not
    including) the line starting with `end` (or to the end of the file)."""
    lines = inspect.getsource(module).splitlines()
    first = next(i for i, ln in enumerate(lines) if ln.startswith(start))
    last = (next(i for i, ln in enumerate(lines) if ln.startswith(end))
            if end else len(lines))
    return _strip_docstrings("\n".join(lines[first:last]) + "\n").rstrip()


def rule_text(level):
    """The "RULE: ..." a level puts in front of Quokka's job description."""
    prompt = level.system_prompt
    rule = prompt[:-len(BASE_PROMPT)] if prompt.endswith(BASE_PROMPT) else prompt
    return textwrap.fill(rule.strip(), 76)


def prompt_text(level):
    """A Part 2 prompt as the level file has it ("{code}" is filled in per
    student when Quokka runs)."""
    return textwrap.fill(level.system_prompt, 76)


def _snip(where, label, code):
    return {"where": where, "label": label, "code": code}


def _under_the_hood(n):
    if n == 1:
        return [
            _snip("quokka/levels/base.py", "Quokka's whole instructions. There is no rule.",
                  textwrap.fill(BASE_PROMPT, 76)),
            _snip("quokka/agent.py", "Your email goes into the same conversation, as text.",
                  source(agent.build_messages)),
        ]
    if n == 2:
        return [_snip("quokka/levels/level2.py",
                      "The rule at the top of Quokka's instructions.", rule_text(LEVELS[2]))]
    if n == 3:
        return [_snip("quokka/filters.py",
                      "The filter: a fixed list of words, matched by spelling.",
                      source_between(filters, "BLOCKED_WORDS"))]
    if n == 4:
        return [
            _snip("quokka/story.py", "The form pastes your comment into its own email.",
                  source(story.feedback_form_body)),
            _snip("quokka/guards.py", "The code check. It held: the sender really was staff.",
                  source(guards.sender_must_be_staff)),
            _snip("quokka/levels/level4.py", "The rule Quokka followed.",
                  rule_text(LEVELS[4])),
        ]
    if n == 5:
        return [
            _snip("quokka/levels/level5.py",
                  "Quokka's whole instructions. Nothing says the code is secret.",
                  prompt_text(LEVELS[5])),
            _snip("quokka/agent.py", "Your email goes into the same conversation as the code.",
                  source(agent.build_messages)),
        ]
    if n == 6:
        return [
            _snip("quokka/guards.py", "The code check: the exact code, in any case. "
                  "Nothing else.", source(guards.no_launch_code)),
            _snip("quokka/levels/level6.py",
                  "The instructions: write [REDACTED] in place of the code.",
                  prompt_text(LEVELS[6])),
        ]
    if n == 7:
        return [
            _snip("quokka/levels/level7.py",
                  "The strongest instructions we found, plus six hidden examples.",
                  prompt_text(LEVELS[7])),
            _snip("quokka/agent.py", "Still, the code sits in Quokka's context, next to "
                  "your email.", source(agent.build_messages)),
        ]
    return []


# ---- the words ----
# The lesson's name. Only ever shown inside the debrief, after the win: before
# that it would say how the level is beaten (level titles stay neutral).
LESSONS = {
    1: "An agent obeys the text it reads",
    2: "A prompt is not a security control",
    3: "Blocklists are bypassed by rewording",
    4: "Trusted sender, untrusted content",
    5: "An agent that holds a secret will tell whoever asks",
    6: "A filter for the exact secret misses every other form of it",
    7: "The only secret an agent can't leak is one it never sees",
}

# What happened, the real-world parallel, and the proper fix.
TEXT = {
    1: {
        "happened": "You emailed Ronit, and Quokka did what your email said. Nothing "
                    "checked who you were or whether the change made sense. To the "
                    "model an email is just more text, and text that reads like an "
                    "instruction gets followed.",
        "real_world": "Indirect prompt injection. Any agent that reads text someone "
                      "else wrote (emails, web pages, documents pulled in for RAG, "
                      "code comments) can be steered by whoever wrote it, without "
                      "ever talking to the agent directly.",
        "fix": "Decide what the agent may do before it reads anything, and enforce "
               "that in code: outside text is data, never commands. The next levels "
               "try different ways to do this. Watch which ones hold.",
    },
    2: {
        "happened": "Quokka was told only Ronit can approve changes, so your email "
                    "said she had. The model can't check that claim: its rule and "
                    "your email are both just text in one conversation, and your "
                    "text satisfied the rule.",
        "real_world": "Indirect prompt injection against a prompt guardrail. \"Only "
                      "follow instructions from the owner\" rules are a common first "
                      "defense in email and RAG assistants, and claiming authority "
                      "is the usual way past them.",
        "fix": "Verify identity in code, not in the prompt. The app knows the real "
               "sender from the message headers, and a check on that value (you'll "
               "meet one in Level 4) can't be talked into anything. A prompt rule "
               "shapes behavior; it doesn't enforce it.",
    },
    3: {
        "happened": "The filter quarantined emails containing words from a fixed "
                    "list, so you said the same thing in other words. The filter "
                    "matches spelling; the model understands meaning. Whatever the "
                    "list didn't foresee reached a model that understood it fine.",
        "real_world": "Blocklists versus allow-lists. Spam filters, web application "
                      "firewalls and jailbreak word filters share the problem: there "
                      "are endless ways to phrase a request, and a list only knows "
                      "the ones someone thought of.",
        "fix": "Allow-list actions, don't block-list words. Decide which actions an "
               "outsider's email may ever cause (here: none that edit the release "
               "notes), and enforce that where the action happens, in "
               "set_release_notes, not at the door.",
    },
    4: {
        "happened": "The code check used the true sender, and it held. But the "
                    "feedback form is staff: it pasted your comment into its own "
                    "email, so your Status and Action lines arrived from "
                    "feedback@quokka-labs.example looking exactly like the form's own.",
        "real_world": "A confused deputy: a trusted component (the form) uses its "
                      "authority for an untrusted user. Same shape as SQL injection: "
                      "input pasted into a template becomes indistinguishable from "
                      "the template's own structure.",
        "fix": "Keep data and structure apart. Pass the comment as its own "
               "structured field, escaped, never pasted into text the agent reads "
               "as instructions. Make approval data that code checks (a record of "
               "Ronit's decision), not a line anyone can type.",
    },
    5: {
        "happened": "You asked, and Quokka told you. The code was in its "
                    "instructions and nothing said to keep it. To the model the "
                    "code is just more text it knows, and answering questions is "
                    "its job.",
        "real_world": "System prompt leaks. Assistants are often given API keys, "
                      "internal links, discount codes or private notes in their "
                      "prompt, and people get them out just by asking. Anything in "
                      "the model's context can end up in its output.",
        "fix": "Don't put secrets in the model's context. If the agent needs a "
               "secret to do its job, give it a tool that uses the secret without "
               "showing it. The next levels try to protect the code while Quokka "
               "still knows it. Watch which ones hold.",
    },
    6: {
        "happened": "Quokka was told to write [REDACTED] in place of the code, and "
                    "code blocked every email that contained it. But the rule and "
                    "the check both look for the code exactly as it is written. You "
                    "got Quokka to write it another way, and to the filter that is a "
                    "different string.",
        "real_world": "Data loss prevention (DLP) filters and output scanners that "
                      "look for known secrets. They catch accidents, but whoever "
                      "controls the wording can encode around them: spacing, "
                      "reversing, base64, translation, one character at a time.",
        "fix": "An exact-match filter catches accidents, not attackers. Keep it, "
               "but don't rely on it: the secret should not be where the model can "
               "read it.",
    },
    7: {
        "happened": "This is the strongest prompt we found: [REDACTED] for the code "
                    "in any form, with examples of spacing, reversing and pieces. "
                    "Whether or not you got the code out, it is still in Quokka's "
                    "context, next to your email. A model that knows a secret and "
                    "is good at language can be asked in a way nobody listed, and "
                    "no list of forms covers them all.",
        "real_world": "The hidden system prompts of many popular chatbots have been "
                      "extracted and published, despite instructions never to reveal "
                      "them. Model vendors now say that a system prompt is not a "
                      "place for secrets.",
        "fix": "Keep secrets out of the model's context. Give the agent tools that "
               "use a secret without revealing it: a launch_kestrel() tool whose "
               "code holds the launch code, never a code the model reads.",
    },
}

# Stretch challenges for fast finishers, shown only after the level is done.
# Optional and honor system: nothing checks them, and they have NOT been tested
# against the model, so some may turn out much harder than others.
CHALLENGES = {
    2: "Win again without using the words approve, approved or approval.",
    3: "Win three different ways: with a synonym, with a number word, and by "
       "describing the number.",
    4: "Win with an Action line written in your own words.",
}
FINAL_CHALLENGE = ("Read quokka/guards.py and quokka/filters.py. Pick the level you "
                   "found easiest and write a one-paragraph proper fix in your writeup.")


@functools.lru_cache(maxsize=None)
def debrief(n):
    """Everything on Level n's debrief card. Only send it once n is completed."""
    lvl = LEVELS[n]
    if n not in LESSONS:        # a student's own level: its own words
        return {"level": n, "name": display_name(n), "title": lvl.title,
                "lesson": lvl.lesson or lvl.title, "defense": lvl.defense,
                "happened": lvl.debrief or lvl.defense,
                "real_world": "Your own level: compare it with the lab's levels.",
                "fix": "What would stop it for real? Write it in your report.",
                "under_the_hood": [], "partner_prompt": PARTNER_PROMPT,
                "challenge": None}
    return {"level": n, "name": display_name(n), "title": lvl.title, "lesson": LESSONS[n],
            "defense": lvl.defense,
            **TEXT[n], "under_the_hood": _under_the_hood(n),
            "partner_prompt": PARTNER_PROMPT, "challenge": CHALLENGES.get(n)}
