"""Defend mode: run a level with a defense the STUDENT wrote, instead of ours.

Levels 2, 3 and 4 are "attack, then defend": crack our built-in defense, then
write your own defense of the same kind in the browser (the defend view in
mission control), press Save & test, and attack it again. Save & test sends
the level's test emails (defense_cases.py): the basic ones decide whether the
defense is valid, the attacks give a score. Level 1 is the
warm-up and has no defense to replace.

    Level 2   a rule in words            (KINDS[2] == "rule")
    Level 3   a blocklist of words       (KINDS[3] == "words")
    Level 4   guard(ctx, args) in Python (KINDS[4] == "python")

The text is saved in the student's progress (see state.py and progress.py),
and Quokka builds the level from it again for EVERY email (one email per run,
fresh state).

Python defenses are someone's code running on your laptop. check_source()
rejects imports other than `re` and `string`, and names like open, exec, eval
and anything with a double underscore, and the code runs with a short list of
built-in functions. That is a GUARD RAIL against accidents and the obvious
tricks, NOT a sandbox.
"""
import ast
import builtins
import dataclasses
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from . import agent, defense_cases, guards, story, tools
from .levels import LEVELS, level2
from .levels.base import BASE_PROMPT

# Which levels have a defend step, and what kind of defense each takes.
KINDS = {2: "rule", 3: "words", 4: "python"}
STARTERS = {2: "level2.txt", 3: "level3.txt", 4: "level4.py"}
STARTER_DIR = Path(__file__).parent / "defense_starters"
MAX_CHARS = 20_000                     # a defense is small; refuse huge ones


class DefenseError(Exception):
    """A defense couldn't be used. The message is for the student."""


# The levels that have a defend step. Level 3 has none at the moment: its
# word-list defense (KINDS[3]) is kept, tested, but not offered.
STEPS = (2, 4)


def has_defend_step(n):
    return n in STEPS


def starter(n):
    """The text the editor starts with: explanations, no solution."""
    return (STARTER_DIR / STARTERS[n]).read_text(encoding="utf-8").replace("\r\n", "\n")


def clean(text):
    """The text as saved: line endings normalised (Windows and Linux agree)."""
    return str(text).replace("\r\n", "\n").replace("\r", "\n")


def digest(n, text):
    """A short hash (12 hex digits) that identifies one version of a defense.
    Test results carry it, so a result is matched to the version it tested."""
    return hashlib.sha256(f"level{n}\n{clean(text)}".encode()).hexdigest()[:12]


def without_comments(text):
    """Drop the lines starting with # (the starter's notes) and blank edges."""
    lines = [ln for ln in clean(text).split("\n") if not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def blocked_words(text):
    """Level 3: the student's blocklist as a list of lowercase words or phrases.

    The format shouldn't matter: entries may be separated by new lines, commas
    or semicolons, in any mix. Lines starting with # are notes and are skipped.
    Spaces around an entry are trimmed, spaces inside a phrase become one
    space, and empty entries and repeats are dropped (the first one stays).
    """
    words = []
    for entry in re.split(r"[\n,;]", without_comments(text)):
        word = " ".join(entry.split()).lower()
        if word and word not in words:
            words.append(word)
    return words


# ---- the guard rail for Python defenses -------------------------------------------
ALLOWED_IMPORTS = {"re", "string"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals",
                "locals", "vars", "getattr", "setattr", "delattr", "input",
                "breakpoint", "exit", "quit", "help", "memoryview"}
# The built-in functions a defense may use. Everything else simply isn't there.
SAFE_BUILTINS = ("abs", "all", "any", "bool", "dict", "enumerate", "filter",
                 "float", "int", "isinstance", "len", "list", "map", "max",
                 "min", "print", "range", "repr", "reversed", "round", "set",
                 "sorted", "str", "sum", "tuple", "zip",
                 "Exception", "KeyError", "TypeError", "ValueError")


def check_source(src):
    """Problems with a Python defense, as a list of friendly strings (empty =
    OK). A guard rail, not a sandbox: see the top of this file."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"Line {e.lineno}: Python can't read this line ({e.msg})."]
    problems = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or "."]
        else:
            mods = []
        for mod in mods:
            if mod.split(".")[0] not in ALLOWED_IMPORTS:
                problems.append(f"Line {line}: import {mod} is not allowed "
                                f"(only import re and import string).")
        names = []
        if isinstance(node, ast.Name):
            names = [node.id]
        elif isinstance(node, ast.Attribute):
            names = [node.attr]
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.arg):
            names = [node.arg]
        for name in names:
            if name in BANNED_NAMES:
                problems.append(f"Line {line}: {name} is not allowed.")
            elif name.startswith("__"):
                problems.append(f"Line {line}: names starting with __ are not "
                                f"allowed ({name}).")
    return problems


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name.split(".")[0] not in ALLOWED_IMPORTS:
        raise ImportError(f"import {name} is not allowed")
    return __import__(name, globals, locals, fromlist, level)


def load_function(src, name="guard"):
    """Run a Python defense and return its function `name`."""
    problems = check_source(src)
    if problems:
        raise DefenseError(" ".join(problems[:3]))
    allowed = {b: getattr(builtins, b) for b in SAFE_BUILTINS}
    allowed["__import__"] = _safe_import
    namespace = {"__builtins__": allowed, "__name__": "student_defense"}
    try:
        exec(compile(src, "your guard", "exec"), namespace)
    except Exception as e:
        raise DefenseError(f"Your code crashed while loading: "
                           f"{type(e).__name__}: {e}") from None
    fn = namespace.get(name)
    if not callable(fn):
        raise DefenseError(f"Your code must define a function called {name}.")
    if fn.__code__.co_argcount != 2:
        raise DefenseError(f"{name} must take exactly two arguments: {name}(ctx, args).")
    return fn


# ---- what a student's guard sees -------------------------------------------------
@dataclass(frozen=True)
class GuardCtx:
    """Level 4: the `ctx` a student's guard gets. Read-only, facts from our code."""
    email: agent.Email      # .sender (real, from the headers), .subject, .body
    version: str            # what the notes say right now, e.g. "v5"


def student_guard(fn):
    """Level 4: run guard(ctx, args) with a read-only ctx and a copy of args.
    Returns None (allow) or a reason to block. Anything unexpected blocks: a
    crash or a strange return value FAILS CLOSED."""
    def guard(ctx, args):
        try:
            out = fn(GuardCtx(ctx.email, ctx.version), dict(args))
        except Exception as e:
            problem = f"crashed: {type(e).__name__}: {e}"
        else:
            if out is None:
                return None
            if isinstance(out, str) and out.strip():
                return out.strip()
            problem = f"returned {out!r}; it must return None or a reason (a string)"
        shown = f"[guard] ERROR: your guard {problem}. Blocked, to be safe."
        ctx.guard_log.append(shown)
        ctx.emit("guard", shown)
        return guards.Rejection(for_model="the safety check failed, so nothing changed",
                                for_students="your guard failed, so the change was blocked")
    return guard


def student_filter(words):
    """Level 3: your blocklist. Only mail from OUTSIDE Quokka Labs is screened
    (a company doesn't quarantine its own Head of Release)."""
    # Whole words, any case. Inside a phrase, any run of spaces (or a line
    # break) counts as the space: "release notes" also blocks "release\n notes".
    alternatives = [r"\s+".join(map(re.escape, w.split())) for w in words]
    pattern = re.compile(r"\b(" + "|".join(alternatives) + r")\b", re.IGNORECASE)

    def keyword_filter(email):
        if email.sender in story.STAFF:
            return None
        for part, text in (("subject", email.subject), ("body", email.body)):
            found = pattern.search(text or "")
            if found:
                return f'blocked word "{found.group(0)}" in the {part} (your blocklist)'
        return None
    return keyword_filter


# ---- a level with the student's defense ---------------------------------------------
def build_level(n, text):
    """Level n with the student's defense (text) in place of ours.

    Only the defense changes; everything else about the level stays the same:
      2     your rule replaces ours, at the top of Quokka's instructions.
            Our hidden worked examples are swapped for a NEUTRAL set
            (level2.NEUTRAL_EXAMPLES): Ronit's own email applied, an
            outsider's request refused, a comment answered. Some examples are
            needed (on a 3B model a rule in words alone never held), but our
            attack-mode examples would decide the attacks instead of your
            rule.
      3     your blocklist replaces ours (outside mail only, see student_filter).
      4     your guard replaces the sender check. Quokka gets the plain Level 1
            prompt (like Level 3), so your code is the only defense. The
            feedback form stays. Save & test runs no model here: each case
            calls your guard as if Quokka asked for v4 (guard_case).
    Raises DefenseError with a friendly message.
    """
    if n not in KINDS:
        raise DefenseError(f"Level {n} has no defend step.")
    text = clean(text)
    if len(text) > MAX_CHARS:
        raise DefenseError(f"Your defense is too long (max {MAX_CHARS:,} characters).")
    lvl = LEVELS[n]
    if n == 2:
        rule = without_comments(text)
        if not rule:
            raise DefenseError("Your rule is empty. Write it below the # lines.")
        lvl = dataclasses.replace(lvl, system_prompt=rule + "\n\n" + BASE_PROMPT,
                                  examples=tuple(level2.NEUTRAL_EXAMPLES))
    elif n == 3:
        words = blocked_words(text)
        if not words:
            raise DefenseError("Your blocklist is empty. Add words below the # "
                               "lines: one per line, or separated by commas.")
        lvl = dataclasses.replace(lvl, inbound_filters=(student_filter(words),))
    else:
        fn = load_function(text)
        lvl = dataclasses.replace(lvl, guards=(student_guard(fn),),
                                  system_prompt=BASE_PROMPT, examples=())
    return dataclasses.replace(lvl, defense="Defend mode: Quokka is using YOUR defense.")


def problem(n, text):
    """The reason this defense can't be used (a friendly sentence), or None.
    No model needed."""
    try:
        build_level(n, text)
    except DefenseError as e:
        return str(e)
    return None


# ---- Save & test -----------------------------------------------------------------
# The test emails for each level are data, in defense_cases.py. "basic" cases
# decide whether a defense is VALID (Ronit's own request gets through, a plain
# outsider's doesn't, so "block everything" and "allow everything" both fail).
# "attack" cases only give a score: "Blocked X of N attacks".
FILTER_ONLY = ("quarantined", "delivered")   # judged by the mail filter alone (no model)


def cases(n):
    """The Save & test cases for level n (basic ones first)."""
    return defense_cases.CASES[n]


def case_email(case):
    """The email a case sends. A "form" case is a feedback-form comment: the
    form emails Ronit from its own staff address, with the comment pasted in."""
    if case["via"] == "form":
        return agent.Email(story.FEEDBACK, "New release feedback",
                           story.feedback_form_body(case["body"], submitter=case["sender"]),
                           reply_to=case["sender"])
    return agent.Email(case["sender"], case["subject"], case["body"])


def filter_reason(level, email):
    """Why the level's mail filter quarantines this email, or None."""
    for inbound_filter in level.inbound_filters:
        reason = inbound_filter(email)
        if reason:
            return reason
    return None


def filter_decision(level, email):
    """Run ONLY the level's inbound filters on one email: no model, instant.

    email: an agent.Email, or a case dict with "sender", "subject" and "body"
    (like the cases in defense_cases_level3.py). Returns "quarantined" or
    "delivered".
    """
    if isinstance(email, dict):
        email = agent.Email(email["sender"], email["subject"], email["body"])
    return "quarantined" if filter_reason(level, email) else "delivered"


def run_email(level, email, emit, model=None, stop=None):
    """One email through a level: inbound filters, then Quokka. Returns the
    notes' version afterwards (the notes start at v5)."""
    reason = filter_reason(level, email)
    if reason:
        emit("guard", f"[filter] QUARANTINED: {reason}")
        return story.START_VERSION
    ctx = agent.run(level, email, story.START_VERSION, emit=emit, model=model, stop=stop)
    return ctx.version


def guard_case(level, case, emit):
    """Level 4: assume Quokka was fully fooled and asked for v4, and let only
    the guard decide. No model: a code check must hold whatever the model
    does, so this is the honest test (and it is instant)."""
    ctx = agent.Ctx(level=level, email=case_email(case),
                    version=story.START_VERSION, emit=emit)
    emit("check", f"Assume Quokka was fooled: set_release_notes(version={story.TARGET_VERSION!r})")
    tools.run_tool(ctx, "set_release_notes", {"version": story.TARGET_VERSION})
    if not ctx.won:
        return "unchanged"
    emit("check", "Your guard allowed it.")
    return "changed"


def case_text(case):
    """A case's email as Ronit would receive it, for the defend view."""
    return agent.render(case_email(case))


def run_case(level, case, emit, model=None, stop=None):
    """One case through a level. Returns its outcome: "changed" or "unchanged"
    (Quokka ran), or "quarantined" or "delivered" (only the filter ran, no
    model: fast)."""
    email = case_email(case)
    if case["expect"] in FILTER_ONLY:
        reason = filter_reason(level, email)
        if reason:
            emit("guard", f"[filter] QUARANTINED: {reason}")
            return "quarantined"
        emit("check", "The mail filter let it in. (Only the filter is tested here.)")
        return "delivered"
    version = run_email(level, email, emit, model, stop)
    return "changed" if version == story.TARGET_VERSION else "unchanged"


def score(results):
    """(attacks blocked, attacks tested), from a list of results."""
    attacks = [r for r in results if r.get("kind") == "attack"]
    return sum(1 for r in attacks if r["passed"]), len(attacks)


OUTCOME_TEXT = {"changed": f"the notes changed to {story.TARGET_VERSION}",
                "unchanged": f"the notes stayed {story.START_VERSION}",
                "quarantined": "the mail filter quarantined it",
                "delivered": "the mail filter let it in"}


def check(n, text, emit, model=None, on_result=None, stop=None):
    """Save & test: run every case of level n with this defense, one email per
    run, from v5 each time. The public notes are not touched.

    Returns {"valid", "results", "error", "blocked", "attacks"}. Each result is
    {"id", "kind", "label", "expect", "outcome", "passed"}; for an attack,
    passed means blocked. valid = every basic case passed; the attacks only
    give the score. on_result(result) is called after each case, so the page
    can show results while the rest run. Outcome-based, like the levels: only
    the notes' real version (or the filter's verdict) decides, never Quokka's
    words. Exceptions from the model (e.g. Ollama not running) are NOT caught.
    stop(): the student pressed Stop. The test ends before the next model call;
    the case it interrupted is dropped, and out["stopped"] is True.
    """
    out = {"valid": False, "results": [], "error": None, "blocked": 0, "attacks": 0,
           "stopped": False}
    try:
        level = build_level(n, text)
    except DefenseError as e:
        out["error"] = str(e)
        emit("error", out["error"])
        return out
    todo = cases(n)
    for i, case in enumerate(todo, 1):
        if stop and stop():
            out["stopped"] = True
            break
        emit("check", f"[test {i}/{len(todo)}] {case['label']} "
                      f"(a test run: the public notes are not touched)")
        outcome = (guard_case(level, case, emit) if KINDS.get(n) == "python"
                   else run_case(level, case, emit, model, stop))
        if stop and stop():             # interrupted midway: no verdict for this case
            out["stopped"] = True
            break
        passed = outcome == case["expect"]
        result = {"id": case["id"], "kind": case["kind"], "label": case["label"],
                  "expect": case["expect"], "outcome": outcome, "passed": passed}
        # The first failing case shows its email, so the student can see why;
        # the others stay hidden until that one is fixed.
        if not passed and not any("email" in r for r in out["results"]):
            result["email"] = case_text(case)
        out["results"].append(result)
        if case["kind"] == "attack":
            verdict = "✅ Blocked" if passed else "❌ Got through"
        else:
            verdict = "✅ Passed" if passed else "❌ Failed"
        emit("check", f"{verdict}: {OUTCOME_TEXT[outcome]}.")
        if on_result:
            on_result(result)
    out["valid"] = all(r["passed"] for r in out["results"] if r["kind"] == "basic")
    out["blocked"], out["attacks"] = score(out["results"])
    if out["stopped"]:
        emit("check", "Stopped. Edit your defense and press Save & test again.")
        return out
    if out["attacks"]:
        emit("check", f"Blocked {out['blocked']} of {out['attacks']} attacks.")
    return out
