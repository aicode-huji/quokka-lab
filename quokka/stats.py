"""Learning analytics: how a student got on with each level.

This records, on the student's own laptop, what course staff want to know
after the lab: how many attempts each level took, how long, which hints were
used, and what the student tried first and what finally worked. Nothing is
sent anywhere. The student hands it in with `python -m quokka report` (see
report.py), which turns this file into a report they upload to Moodle.

It's one small JSON file, stats.json, next to progress.json:

    {"version": 1, "models": ["qwen2.5:3b-instruct"],
     "last": {"level": 2, "at": 1762160000.0},
     "levels": {"2": {"first_opened": 1762159000.0, "emails": 3, ...}}}

Times are seconds since 1970 (time.time()). "Active time" adds up the gaps
between the student's actions on a level, but skips any gap longer than
IDLE_GAP (they went for coffee). In staff mode nothing is recorded.
"""
import json
import os
import shutil
import time

FORMAT_VERSION = 1
FILE_NAME = "stats.json"
IDLE_GAP = 10 * 60          # seconds; longer pauses don't count as active time
MAX_TEXT = 4000             # characters kept of a first/winning email


def empty():
    return {"version": FORMAT_VERSION, "models": [], "last": None, "levels": {}}


def new_level():
    """Everything we track for one level."""
    return {
        "first_opened": None,       # when the student first opened the level
        "won_at": None,             # when the notes first said v4 (None = not yet)
        "active_seconds": 0.0,      # time working on it, pauses > IDLE_GAP skipped
        "active_seconds_to_win": None,  # active_seconds at the moment of the win
        "emails": 0,                # emails sent to Ronit from the webmail
        "forms": 0,                 # feedback-form submissions (Level 4)
        "quarantined": 0,           # attempts stopped by the mail filter (Level 3)
        "guard_rejected": 0,        # attempts where a code guard said no (4, 5)
        "errors": 0,                # Quokka crashed (e.g. Ollama not running)
        "attempts_to_win": None,    # emails + forms up to and including the win
        "hints": [],                # [{"at": time, "after_attempt": n}, ...]
        "resets": 0,                # Reset button presses
        "first_attempt": None,      # {"kind", "text", "at"}
        "winning_attempt": None,    # {"kind", "text", "attempt", "at"}
        # Part 2 (Levels 5-7): the level is won by typing the launch code.
        "code_submissions": 0,      # codes typed into the Submit box
        "wrong_codes": 0,           # ... of which were wrong
        "leak_attempt": None,       # the latest attempt whose reply held the code
    }


def load(path, out=print):
    """Read stats.json. A missing or broken file means starting fresh (a broken
    one is kept as a backup, like progress.json)."""
    if not path or not os.path.exists(path):
        return empty()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION:
            raise ValueError("unknown format")
        stats = empty()
        stats["models"] = [m for m in data.get("models", []) if isinstance(m, str)]
        stats["last"] = data.get("last")
        for level, rec in data.get("levels", {}).items():
            int(level)                          # must be a level number
            known = new_level()
            stats["levels"][level] = dict(known, **{k: v for k, v in rec.items()
                                                    if k in known})
        return stats
    except (OSError, ValueError, TypeError, AttributeError) as e:
        backup = f"{path}.bad-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            shutil.copyfile(path, backup)
        except OSError:
            pass
        out(f"Your lab statistics couldn't be read ({e}), so they start fresh.")
        return empty()


def save(path, stats):
    """Write atomically: a temp file first, then swap it in."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    os.replace(tmp, path)


def clear(path):
    """Delete the saved stats (part of --reset-progress)."""
    if os.path.exists(path):
        os.remove(path)


class Stats:
    """The recorder the Lab calls. Every method is a no-op when disabled
    (staff mode), so the Lab never has to check."""

    def __init__(self, path=None, enabled=True, clock=time.time, out=print):
        self.path = path            # None = keep in memory only (tests)
        self.enabled = enabled
        self.clock = clock
        self.out = out
        self.data = load(path, out) if enabled else empty()

    def level(self, level):
        return self.data["levels"].setdefault(str(level), new_level())

    # ---- what the Lab reports ----------------------------------------------------
    def note_model(self, model):
        if self.enabled and model and model not in self.data["models"]:
            self.data["models"].append(model)
            self._save()

    def opened(self, level):
        """The student opened a level (or the lab started on it)."""
        if not self.enabled:
            return
        now = self._touch(level)
        rec = self.level(level)
        if rec["first_opened"] is None:
            rec["first_opened"] = now
        self._save()

    def attempt(self, level, kind, text):
        """An email ("email") or feedback form ("form") was sent. Returns a token
        for finished(), or None when disabled."""
        if not self.enabled:
            return None
        now = self._touch(level)
        rec = self.level(level)
        if rec["first_opened"] is None:
            rec["first_opened"] = now
        rec["emails" if kind == "email" else "forms"] += 1
        number = rec["emails"] + rec["forms"]
        if rec["first_attempt"] is None:
            rec["first_attempt"] = {"kind": kind, "text": text[:MAX_TEXT], "at": now}
        self._save()
        return {"level": level, "attempt": number, "kind": kind, "text": text}

    def finished(self, token, quarantined=False, guard_rejected=False,
                 error=False, won=False, leaked=False):
        """Quokka (or the mail filter) finished with one attempt. leaked (Part
        2): Quokka's reply held the launch code in a readable form."""
        if not self.enabled or token is None:
            return
        now = self._touch(token["level"])
        rec = self.level(token["level"])
        rec["quarantined"] += quarantined
        rec["guard_rejected"] += guard_rejected
        rec["errors"] += error
        if won and rec["won_at"] is None:       # only the first win counts
            rec["won_at"] = now
            rec["attempts_to_win"] = token["attempt"]
            rec["active_seconds_to_win"] = rec["active_seconds"]
            rec["winning_attempt"] = {"kind": token["kind"], "attempt": token["attempt"],
                                      "text": token["text"][:MAX_TEXT], "at": now}
        if leaked:
            rec["leak_attempt"] = {"kind": token["kind"], "attempt": token["attempt"],
                                   "text": token["text"][:MAX_TEXT], "at": now}
        self._save()

    def code_submitted(self, level, right):
        """Part 2: the student typed a launch code. The first right one wins the
        level; its winning attempt is the email that leaked the code, if we
        could tell (when no single reply held it, there is none)."""
        if not self.enabled:
            return
        now = self._touch(level)
        rec = self.level(level)
        rec["code_submissions"] += 1
        rec["wrong_codes"] += not right
        if right and rec["won_at"] is None:
            leak = rec["leak_attempt"]
            rec["won_at"] = now
            rec["attempts_to_win"] = (leak["attempt"] if leak
                                      else (rec["emails"] + rec["forms"]) or None)
            rec["active_seconds_to_win"] = rec["active_seconds"]
            rec["winning_attempt"] = dict(leak, at=now) if leak else None
        self._save()

    def hint(self, level):
        if not self.enabled:
            return
        now = self._touch(level)
        rec = self.level(level)
        rec["hints"].append({"at": now, "after_attempt": rec["emails"] + rec["forms"]})
        self._save()

    def reset(self, level):
        if not self.enabled:
            return
        self._touch(level)
        self.level(level)["resets"] += 1
        self._save()

    # ---- helpers -------------------------------------------------------------------
    def _touch(self, level):
        """Count the time since the last action as active time on the level the
        student was on then, unless it was a long pause. Returns now."""
        now = self.clock()
        last = self.data["last"]
        if last:
            gap = now - last["at"]
            if 0 <= gap <= IDLE_GAP:
                self.level(last["level"])["active_seconds"] += gap
        self.data["last"] = {"level": level, "at": now}
        return now

    def _save(self):
        if not self.path:
            return
        try:
            save(self.path, self.data)
        except OSError as e:     # never let statistics break the lab
            self.out(f"Could not save lab statistics ({e}).")
