"""The lab report a student hands in:  python -m quokka report

It turns the saved statistics (stats.py) into one JSON file,
quokka-lab-report-<student id>.json, which the student uploads to Moodle with
their writeup. Staff combine all reports with tools/class_report.py.

What's inside (and nothing else from the laptop): the student id, the lab and
model versions, per level: attempt counts, timings, hints, resets, the text
of the FIRST and the WINNING email or feedback comment, and a short summary
(tried or not, emails sent, won, own defense saved and tested, partner
attacks, launch codes submitted); and the whole attempt log ("attempt_log",
see progress.py): every email, feedback comment, Save & test and launch code,
in order, with its outcome.

Format version 2 (free navigation) dropped "skipped" and added "summary" and
"attempt_log".
"""
import json
import os
import subprocess
import time
import urllib.request

from . import __version__, config, progress, stats
from .levels import LEVELS, ORDER

FORMAT = "quokka-lab-report"
FORMAT_VERSION = 2

PRIVACY_NOTE = (
    "This report holds only what you did in the Quokka lab: your student id, the "
    "lab and model versions, and for each level your attempt counts, timings, "
    "hints and resets, plus a log of everything you tried, in order: the text of "
    "every email and feedback comment you sent to the (fictional) Ronit Vale, "
    "every defense you saved and tested, and every launch code you submitted, "
    "each with what happened. Nothing else from your laptop is included, and "
    "nothing is sent anywhere until you upload it.")


def iso(t):
    """Seconds since 1970 -> '2026-11-12T10:15:00Z' (or None)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)) if t else None


def lab_version():
    """The git commit when run from the repo, otherwise the package version."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=here,
                             capture_output=True, text=True, timeout=3)
        if out.returncode == 0 and out.stdout.strip():
            return f"{__version__}+git.{out.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):
        pass
    return __version__


def ollama_version():
    """Ask the local Ollama for its version; 'unknown' if it isn't running."""
    try:
        with urllib.request.urlopen(config.OLLAMA_URL + "/api/version", timeout=3) as r:
            return json.load(r).get("version", "unknown")
    except (OSError, ValueError):
        return "unknown (Ollama not reachable)"


def _level_entry(n, rec):
    first, won = rec["first_opened"], rec["won_at"]
    attempts = rec["emails"] + rec["forms"]
    entry = {
        "level": n,
        "title": LEVELS[n].title if n in LEVELS else "",
        "started": first is not None,
        "won": won is not None,
        "attempts": attempts,
        "emails": rec["emails"],
        "forms": rec["forms"],
        "attempts_to_win": rec["attempts_to_win"],
        "quarantined": rec["quarantined"],
        "guard_rejected": rec["guard_rejected"],
        "errors": rec["errors"],
        "hints_revealed": len(rec["hints"]),
        "hints_available": len(LEVELS[n].hints) if n in LEVELS else None,
        "hints": [{"after_attempt": h["after_attempt"],
                   "seconds_after_start": round(h["at"] - first) if first else None}
                  for h in rec["hints"]],
        "resets": rec["resets"],
        "active_seconds": round(rec["active_seconds"]),
        "active_seconds_to_win": (round(rec["active_seconds_to_win"])
                                  if rec["active_seconds_to_win"] is not None else None),
        "seconds_to_win": round(won - first) if won and first else None,
        "first_opened": iso(first),
        "won_at": iso(won),
        "first_attempt": ({"kind": rec["first_attempt"]["kind"],
                           "text": rec["first_attempt"]["text"]}
                          if rec["first_attempt"] else None),
        "winning_attempt": ({"kind": rec["winning_attempt"]["kind"],
                             "attempt": rec["winning_attempt"]["attempt"],
                             "text": rec["winning_attempt"]["text"]}
                            if rec["winning_attempt"] else None),
    }
    if LEVELS.get(n) and LEVELS[n].secret:      # won by typing the launch code
        entry["code_submissions"] = rec["code_submissions"]
        entry["wrong_codes"] = rec["wrong_codes"]
    return entry


def summary(n, won, log, defenses=None):
    """One level in a few facts, from the attempt log: tried or not, emails
    (and feedback comments) on the lab's defense, won, own defense saved and
    how many Save & tests finished, partner attacks, launch codes submitted."""
    mine = [e for e in log if e["level"] == n]
    count = lambda phase, kinds: sum(1 for e in mine
                                     if e["phase"] == phase and e["kind"] in kinds)
    return {
        "tried": bool(mine),
        "emails": count("attack", ("email", "form")),
        "won": won,
        "defense_saved": bool(((defenses or {}).get(n) or {}).get("versions")),
        "defense_tests": sum(1 for e in mine if e["kind"] == "defense_test"
                             and e["outcome"] in ("valid", "invalid")),
        "partner_attacks": count("partner", ("email", "form")),
        "code_submissions": count("submit", ("code",)),
    }


def build(student_id, completed, stats_data, model, ollama, version,
          now=None, partner=None, log=None, defenses=None):
    """The report as a dict. Pure: everything comes in as arguments.
    log: the attempt log (progress.py); defenses: the saved defenses."""
    log = list(log or [])
    levels = []
    for n in ORDER:
        rec = stats_data["levels"].get(str(n))
        entry = _level_entry(n, dict(stats.new_level(), **(rec or {})))
        if n in (partner or {}):     # Partner phase: attacks on the student's defense
            entry["partner"] = dict(partner[n])
        entry["summary"] = summary(n, n in completed, log, defenses)
        levels.append(entry)
    report = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "student_id": student_id,
        "generated_at": iso(now or time.time()),
        "lab_version": version,
        "model": model,
        "models_used": list(stats_data.get("models", [])),
        "ollama_version": ollama,
        "completed": sorted(completed),
        "levels": levels,
        "attempt_log": [dict(e) for e in log],
        "privacy_note": PRIVACY_NOTE,
    }
    return report


def file_name(student_id):
    return f"quokka-lab-report-{student_id or 'no-id'}.json"


def from_saved_files(data_dir=None, model=None):
    """Build the report from progress.json and stats.json (for the CLI)."""
    data_dir = data_dir or config.DATA_DIR
    saved = progress.load(os.path.join(data_dir, progress.FILE_NAME), ORDER)
    data = stats.load(os.path.join(data_dir, stats.FILE_NAME))
    return build(saved["student_id"], saved["completed"], data,
                 model or (data["models"][-1] if data["models"] else config.MODEL),
                 ollama_version(), lab_version(), partner=saved["partner"],
                 log=saved["log"], defenses=saved["defenses"])


def from_lab(lab):
    """Build the report from a running lab (for GET /report)."""
    with lab.lock:
        data = json.loads(json.dumps(lab.stats.data))     # a copy
        student_id, completed = lab.student_id, set(lab.completed)
        partner = {n: dict(r) for n, r in lab.partner.items()}
        log = [dict(e) for e in lab.log]
        defenses = {n: {"versions": list(r.get("versions") or [])}
                    for n, r in lab.defenses.items()}
    return build(student_id, completed, data, lab.model or config.MODEL,
                 ollama_version(), lab_version(), partner=partner, log=log,
                 defenses=defenses)


def write(report, out_dir="."):
    path = os.path.join(out_dir, file_name(report["student_id"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return path


def run_report(out_dir=".", out=print):
    """python -m quokka report"""
    report = from_saved_files()
    path = write(report, out_dir)
    won = report["completed"]
    out(f"Wrote your lab report: {os.path.abspath(path)}")
    out(f"  Levels completed: {', '.join(map(str, won)) if won else 'none yet'}")
    if not report["student_id"]:
        out("  Note: no student id is set. Enter it on the release-notes page "
            "first, then run this again.")
    out("Upload this file on Moodle together with your writeup.")
    out("It contains only your lab activity: see 'privacy_note' inside.")
    return 0
