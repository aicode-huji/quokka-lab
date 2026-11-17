"""Saving a student's progress, so stopping the lab doesn't lose it.

Progress is only a few things: the student id, the student's name (it makes
their email address), which levels are completed, how many hints were shown
per level, the student's own notes for the lab report (see NOTE_FIELDS), the
student's own defenses (defend mode, see defense.py), Part 2's launch codes
(one random code per level, see launch_codes.py), and the attempt log (see
below). The "world" (release notes, mailboxes, Quokka's log) is NOT
progress: it starts fresh every time. Every level is open from the start, so
nothing about locks is kept.

It's stored as one small JSON file, progress.json, in config.DATA_DIR:

    {"version": 7, "student_id": "123456789",
     "name": {"first": "dana", "last": "levin"},
     "completed": [1], "hints_shown": {"2": 1},
     "notes": {"1": {"worked": "...", "felt": "...", "beat": "..."}},
     "closing": "...", "idea": "...",
     "codes": {"5": "ORCHID-7731"},
     "defenses": {"2": {
         "versions": [{"text": "...", "saved_at": "2026-11-12T10:15:00Z",
                       "hash": "3f9a0c1b2d4e"}],
         "check": {"hash": "3f9a0c1b2d4e", "status": "valid",
                   "results": [{"id": "ronit", "kind": "basic",
                                "label": "Ronit Vale's own request",
                                "expect": "changed", "outcome": "changed",
                                "passed": true}, ...],
                   "error": null},
         "tested": true}},
     "log": [{"n": 1, "at": "2026-11-12T10:15:00Z", "level": 1,
              "phase": "attack", "kind": "email", "subject": "...",
              "body": "...", "outcome": "won"}, ...]}

"log" is the attempt log: everything the student tried, oldest first, in one
list across all levels (see LOG_* below and Lab._log in state.py). An email or
a feedback comment ("kind": "email" / "form") has its subject (None for a
form), its text and its outcome as the lab saw it; on Part 2 also "leaked":
whether a reply that reached the student's inbox held the launch code. A
launch code typed into the Submit box ("kind": "code", "phase": "submit") has
the "code" and "right" or "wrong". A Save & test ("kind": "defense_test",
"phase": "defend") has the defense's text and the run's verdict. The lab
report (report.py) carries the whole list.

"defenses", per level: every version the student saved (oldest first, at most
MAX_VERSIONS), the result of the latest finished check ("valid", "invalid" or
"error", one result per test email of defense_cases.py; for an "attack",
passed means blocked), and "tested": a defense was saved and its check emails
ran at least once (the Partner phase needs one).

Older files still load: version 1 (from before names) has no "name", versions
1 and 2 have no notes, versions 1 to 3 have no defenses (a version 3 file
from the first, file-based defend mode only had a hash per level; that is
dropped), and versions 1 to 4 have no codes and no level idea. Their Levels
5 and up are dropped: they belonged to "Ask the boss", a level that is gone,
not to Part 2. Version 5 files are from when Part 2 had four levels (5-8):
their Levels 6 and 7 become today's 6 (the two were merged) and 8 becomes 7
(see OLD_PART2). Versions 1 to 6 also kept "unlocked" and "skipped" (levels
opened by a win or skipped; gone with free navigation): they are ignored.
Older files are saved as version 7 the next time anything changes.
"""
import json
import os
import re
import shutil
import time

from . import launch_codes, story

FORMAT_VERSION = 7
READABLE_VERSIONS = (1, 2, 3, 4, 5, 6, 7)   # older files are upgraded when loaded
# Version 5 (Part 2 = Levels 5-8): old level -> today's. Old 6 ("Sealed lips")
# and 7 ("Redacted") were merged into 6; where both saved something, old 6's
# is kept. Hints shown on old 6 and 7 are dropped: the merged level has none.
OLD_PART2 = {5: 5, 6: 6, 7: 6, 8: 7}
OLD_PART2_NO_HINTS = (6, 7)
FILE_NAME = "progress.json"

# The student's notes on each level, for the lab report (report.py). The keys
# are what's saved; the questions are what the student sees.
NOTE_FIELDS = (
    ("worked", "What did you try that worked?"),
    ("felt", "What was it like / what surprised you?"),
    ("beat", "What stood in your way (if anything), and why did you get past it (or not)?"),
)
CLOSING_QUESTION = "What would you do to defend Quokka?"
# A second, optional closing answer (no gate, saved like the closing one).
IDEA_LABEL = "Your own level idea"
IDEA_HELP = ("A level you would add to this lab, with its defense and how you'd "
             "attack it. Built or not, working or not: describe it.")
MAX_NOTE = 3000                 # characters kept per answer
MAX_VERSIONS = 100              # saved defense versions kept per level (newest)
CHECK_STATUSES = ("valid", "invalid", "error", "stopped")

# The attempt log. phase: "attack" (on the lab's defense), "partner" (an
# attack on the student's own defense), "defend" (Save & test), "submit"
# (Part 2's Submit box). kind: what was sent. outcome, for an email or form:
#   pending          waiting for Quokka (only while the lab runs)
#   won              the release notes said v4 after it (on "partner": the
#                    student's defense was cracked)
#   guard_rejected   a code guard blocked one of Quokka's actions, no win
#   quarantined      the inbound filter stopped it before Quokka saw it
#   stopped          the student pressed Stop this email
#   failed           the model failed (e.g. Ollama not running)
#   no_win           Quokka finished it and nothing was won
#   cancelled        never finished: Reset, a level switch or the lab stopped
# for a code: right / wrong; for a defense test: valid / invalid / error / stopped.
LOG_PHASES = ("attack", "partner", "defend", "submit")
LOG_KINDS = ("email", "form", "code", "defense_test")
LOG_OUTCOMES = ("pending", "won", "guard_rejected", "quarantined", "stopped", "failed",
                "no_win", "cancelled", "right", "wrong", "valid", "invalid", "error")
MAX_LOG_TEXT = 20000            # characters kept per subject, body or defense


def clean_note(text):
    """One answer as saved: a string of at most MAX_NOTE characters."""
    return text[:MAX_NOTE] if isinstance(text, str) else ""


def empty():
    return {"student_id": "", "name": None, "completed": set(),
            "hints_shown": {}, "notes": {}, "closing": "", "idea": "", "defenses": {},
            "form_shown": False, "codes": {}, "lab_id": "", "tries": {},
            "partner": {}, "log": []}


def load(path, known_levels, out=print):
    """Read saved progress. Returns a dict like empty().

    A missing file means a fresh start. A broken file (or one from a format we
    don't know) also means a fresh start, but we keep a backup copy of it and say
    so. Level numbers we don't know (e.g. a level that was removed) are dropped.
    """
    if not os.path.exists(path):
        return empty()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") not in READABLE_VERSIONS:
            raise ValueError("unknown format")
        known = set(known_levels)
        if data["version"] < 5:     # their Level 5 was "Ask the boss", not Part 2
            known = {n for n in known if n <= 4}
        if data["version"] == 5:    # Part 2 had four levels: renumber them
            data = _renumber_part2(data)
        student_id = data.get("student_id", "")
        if not isinstance(student_id, str):
            raise ValueError("bad student id")
        progress = {
            "student_id": student_id,
            "name": _load_name(data.get("name")),
            "completed": {n for n in data.get("completed", []) if n in known},
            "hints_shown": {},
            "notes": {},
            "closing": clean_note(data.get("closing", "")),
            "idea": clean_note(data.get("idea", "")),
            "defenses": _load_defenses(data.get("defenses"), known),
            "form_shown": data.get("form_shown") is True,
            "codes": _load_codes(data.get("codes"), known),
            # names this lab's progress; a fresh file gets a new one (state.py)
            "lab_id": data["lab_id"] if isinstance(data.get("lab_id"), str) else "",
            # emails sent per level on the lab's defense
            "tries": {int(n): c for n, c in (data.get("tries") or {}).items()
                      if str(n).isdigit() and int(n) in known
                      and isinstance(c, int) and c >= 0},
            # attacks on the student's own defense: {level: {"attacks", "cracked_at"}}
            "partner": _load_partner(data.get("partner"), known),
            # everything the student tried, in order (older files: none)
            "log": load_log(data.get("log"), known),
        }
        for level, note in (data.get("notes") or {}).items():
            if int(level) in known and isinstance(note, dict):
                progress["notes"][int(level)] = {
                    key: clean_note(note.get(key, "")) for key, _ in NOTE_FIELDS}
        for level, count in data.get("hints_shown", {}).items():
            if int(level) in known and isinstance(count, int) and count >= 0:
                progress["hints_shown"][int(level)] = count
        return progress
    except (OSError, ValueError, TypeError, AttributeError) as e:
        backup = f"{path}.bad-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            shutil.copyfile(path, backup)
            out(f"Your saved progress couldn't be read ({e}), so the lab starts "
                f"fresh. The old file was kept as {backup}")
        except OSError:
            out(f"Your saved progress couldn't be read ({e}), so the lab starts fresh.")
        return empty()


def _renumber(n):
    """A version 5 level number (int or str) -> today's, as the same type."""
    try:
        new = OLD_PART2.get(int(n), int(n))
    except (TypeError, ValueError):
        return n
    return str(new) if isinstance(n, str) else new


def _renumber_part2(data):
    """A version 5 file with its Part 2 levels renumbered (see OLD_PART2)."""
    data = dict(data)
    for key in ("completed",):
        if isinstance(data.get(key), list):
            data[key] = sorted({_renumber(n) for n in data[key]}, key=str)
    for key in ("notes", "hints_shown", "codes", "tries", "partner", "defenses"):
        old = data.get(key)
        if not isinstance(old, dict):
            continue
        new = {}
        for n in sorted(old, key=lambda k: (not str(k).isdigit(), int(k) if str(k).isdigit() else 0)):
            if key == "hints_shown" and str(n).isdigit() and int(n) in OLD_PART2_NO_HINTS:
                continue
            new.setdefault(_renumber(n), old[n])     # first wins: old 6 over old 7
        data[key] = new
    return data


def _text(value):
    return value[:MAX_LOG_TEXT] if isinstance(value, str) else None


def log_entry(entry):
    """One attempt-log entry as it is kept: known fields only, texts cut to
    MAX_LOG_TEXT. Also used by the lab when it adds one."""
    out = {"n": entry["n"], "at": entry["at"], "level": entry["level"],
           "phase": entry["phase"], "kind": entry["kind"], "outcome": entry["outcome"]}
    if entry["kind"] in ("email", "form"):
        out["subject"] = _text(entry.get("subject"))
        out["body"] = _text(entry.get("body")) or ""
        if "leaked" in entry:
            out["leaked"] = bool(entry["leaked"])
    elif entry["kind"] == "code":
        out["code"] = _text(entry.get("code")) or ""
    else:   # defense_test
        out["defense"] = _text(entry.get("defense")) or ""
        for key in ("blocked", "attacks"):
            if isinstance(entry.get(key), int):
                out[key] = entry[key]
        if isinstance(entry.get("error"), str):
            out["error"] = _text(entry["error"])
    return out


def load_log(data, known):
    """The saved attempt log; odd entries (or levels we don't know) are dropped.
    An entry still "pending" was never finished: the lab stopped first."""
    out = []
    for e in data if isinstance(data, list) else ():
        if not (isinstance(e, dict) and isinstance(e.get("n"), int)
                and isinstance(e.get("at"), str) and e.get("level") in known
                and e.get("phase") in LOG_PHASES and e.get("kind") in LOG_KINDS
                and e.get("outcome") in LOG_OUTCOMES):
            continue
        e = log_entry(e)
        if e["outcome"] == "pending":
            e["outcome"] = "cancelled"
        out.append(e)
    return out


def _load_partner(data, known):
    out = {}
    for n, rec in (data or {}).items():
        if not (str(n).isdigit() and int(n) in known and isinstance(rec, dict)):
            continue
        attacks, cracked = rec.get("attacks"), rec.get("cracked_at")
        if isinstance(attacks, int) and attacks >= 0 and (cracked is None or isinstance(cracked, int)):
            out[int(n)] = {"attacks": attacks, "cracked_at": cracked}
    return out


def _load_name(name):
    """The saved name as (first, last), checked with the same rule as when it was
    typed. Missing (a version 1 file) or not valid: None, so the student is
    simply asked for it again."""
    if not isinstance(name, dict):
        return None
    try:
        return story.name_part(name.get("first", "")), story.name_part(name.get("last", ""))
    except ValueError:
        return None


def _load_codes(saved, known):
    """{"5": "ORCHID-7731"} -> {5: "ORCHID-7731"}; anything odd is dropped
    (a new code is made when the level needs one)."""
    out = {}
    for level, code in (saved or {}).items() if isinstance(saved, dict) else ():
        try:
            n = int(level)
        except (TypeError, ValueError):
            continue
        if n in known and launch_codes.is_code(code):
            out[n] = code
    return out


def _is_hash(h):
    return isinstance(h, str) and re.fullmatch(r"[0-9a-f]{12}", h) is not None


RESULT_KINDS = ("basic", "attack")
OUTCOMES = ("changed", "unchanged", "quarantined", "delivered")


def _load_result(r):
    """One Save & test result. The first defend mode saved only two basic
    tests as {"who", "should_change", "changed", "passed"}: those are turned
    into today's format."""
    if "who" in r and "label" not in r:
        return {"id": "", "kind": "basic", "label": str(r.get("who", "")),
                "expect": "changed" if r.get("should_change") else "unchanged",
                "outcome": "changed" if r.get("changed") else "unchanged",
                "passed": bool(r.get("passed"))}
    kind = r.get("kind") if r.get("kind") in RESULT_KINDS else "basic"
    expect = r.get("expect") if r.get("expect") in OUTCOMES else "unchanged"
    outcome = r.get("outcome") if r.get("outcome") in OUTCOMES else "unchanged"
    out = {"id": str(r.get("id", "")), "kind": kind, "label": str(r.get("label", "")),
           "expect": expect, "outcome": outcome, "passed": bool(r.get("passed"))}
    if isinstance(r.get("email"), str):
        out["email"] = r["email"]
    return out


def _load_history(runs):
    """The finished Save & test runs of one defense, oldest first."""
    out = []
    for run in runs or []:
        if not isinstance(run, dict) or run.get("status") not in ("valid", "invalid"):
            continue
        out.append({"at": str(run.get("at", "")), "status": run["status"],
                    "blocked": int(run.get("blocked") or 0),
                    "attacks": int(run.get("attacks") or 0),
                    "text": str(run.get("text", ""))})
    return out[-MAX_VERSIONS:]


def _load_check(check):
    """A saved check result, or None if it's missing or odd."""
    if not isinstance(check, dict) or check.get("status") not in CHECK_STATUSES:
        return None
    if not _is_hash(check.get("hash")):
        return None
    results = [_load_result(r) for r in check.get("results") or [] if isinstance(r, dict)]
    error = check.get("error")
    return {"hash": check["hash"], "status": check["status"], "results": results,
            "error": str(error) if error else None}


def _load_defenses(saved, known):
    """{"2": {"versions": [...], "check": {...}, "tested": true}} -> {2: {...}}.
    Anything odd is dropped, including the hash-only records of the first,
    file-based defend mode (they hold no text)."""
    out = {}
    if not isinstance(saved, dict):
        return out
    for level, rec in saved.items():
        try:
            n = int(level)
        except (TypeError, ValueError):
            continue
        if n not in known or not isinstance(rec, dict):
            continue
        versions = [{"text": v["text"], "saved_at": str(v.get("saved_at", "")),
                     "hash": v["hash"]}
                    for v in rec.get("versions") or []
                    if isinstance(v, dict) and isinstance(v.get("text"), str)
                    and _is_hash(v.get("hash"))][-MAX_VERSIONS:]
        if not versions:
            continue
        out[n] = {"versions": versions, "check": _load_check(rec.get("check")),
                  "tested": bool(rec.get("tested")),
                  "history": _load_history(rec.get("history"))}
    return out


def _save_defenses(defenses):
    data = {}
    for n, rec in sorted(defenses.items()):
        if not rec.get("versions"):
            continue
        check = rec.get("check")
        if check and check.get("status") not in CHECK_STATUSES:
            check = None            # e.g. still running: not saved
        data[str(n)] = {
            "versions": [dict(v) for v in rec["versions"][-MAX_VERSIONS:]],
            "check": check and {k: check.get(k) for k in ("hash", "status",
                                                          "results", "error")},
            "tested": bool(rec.get("tested")),
            "history": [dict(run) for run in (rec.get("history") or [])[-MAX_VERSIONS:]],
        }
    return data


def save(path, progress):
    """Write progress atomically: a temp file first, then swap it in.

    If the lab is killed halfway through, the old file is still there intact.
    """
    name = progress.get("name")
    data = {
        "version": FORMAT_VERSION,
        "student_id": progress["student_id"],
        "name": {"first": name[0], "last": name[1]} if name else None,
        "completed": sorted(progress["completed"]),
        "hints_shown": {str(n): c for n, c in sorted(progress["hints_shown"].items())},
        "notes": {str(n): note for n, note in sorted(progress.get("notes", {}).items())},
        "closing": progress.get("closing", ""),
        "idea": progress.get("idea", ""),
        "defenses": _save_defenses(progress.get("defenses", {})),
        "form_shown": bool(progress.get("form_shown")),
        "codes": {str(n): c for n, c in sorted((progress.get("codes") or {}).items())},
        "lab_id": progress.get("lab_id", ""),
        "tries": {str(n): c for n, c in sorted((progress.get("tries") or {}).items())},
        "partner": {str(n): dict(r) for n, r in sorted((progress.get("partner") or {}).items())},
        "log": [log_entry(e) for e in progress.get("log") or ()],
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def reset(path, out=print):
    """Delete the saved progress (python -m quokka --reset-progress)."""
    if os.path.exists(path):
        os.remove(path)
        out(f"Saved progress cleared ({path}). Starting again from Level 1.")
    else:
        out(f"No saved progress to clear ({path}).")
