"""The readable lab report the student hands in: one HTML page.

It is made from three things: the JSON report (report.py, left as it is: the
statistics), the student's own notes, saved in progress (progress.NOTE_FIELDS),
and the student's own defenses for Levels 2-4 (defend mode, also in progress).
The notes and defenses are only in this page, not in the JSON file.

    python -m quokka report      writes this page next to the .json file
    GET /report.html             downloads it from the lab (mission control)

The page is self-contained (no internet, no scripts it needs) and prints
cleanly, so "Print > Save as PDF" in any browser turns it into a PDF.

For each level it shows the level's name, the lesson (only for levels the
student completed: before that the lesson's name would give the level away),
the defense, the student's winning email, attempts and hints, their own
defense (the latest version, its test results: basic checks and "Blocked X
of N attacks", and how many versions they saved), a one-line summary from the
attempt log (emails sent, won or not, defense saved and tested, partner
attacks, codes submitted), and their three answers. An answer they haven't
written yet shows as a clear "Write this" box. At the end, after the closing
answers, the whole attempt log sits in a collapsed "Attempt log" section.
Levels come from the report itself, so a new level needs no change here.
Part 2's levels (5-7) come under their own heading, named "Part 2, Level 1"
and so on, with their launch-code submissions and no defense box. After the
levels: the closing answer and the optional "Your own level idea".
"""
import os
from html import escape

from . import config, defense, progress, report
from .levels import LEVELS, ORDER, debriefs, display_name, part_of

CSS = """
:root { color-scheme: light; --ink: #1d2430; --muted: #5b6472; --line: #d9dee6;
        --soft: #f4f6f9; --accent: #1f6f8b; --ok: #1d7a4a; --todo: #b4541a; }
* { box-sizing: border-box; }
body { margin: 0; background: #fff; color: var(--ink);
       font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 820px; margin: 0 auto; padding: 32px 16px 48px; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 19px; margin: 0; }
h3 { font-size: 14px; margin: 16px 0 4px; }
p { margin: 0 0 8px; }
.lede { color: var(--muted); margin-bottom: 16px; }
.facts { display: grid; grid-template-columns: max-content 1fr; gap: 2px 14px;
         font-size: 14px; margin: 0 0 18px; }
.facts dt { color: var(--muted); }
.facts dd { margin: 0; overflow-wrap: anywhere; }
.tip { background: var(--soft); border: 1px solid var(--line); border-radius: 8px;
       padding: 10px 14px; font-size: 14px; margin-bottom: 22px; }
.level { border-top: 2px solid var(--ink); padding-top: 14px; margin-top: 26px; }
.part-h { font-size: 22px; margin: 40px 0 0; }
.part-p { color: var(--muted); margin: 2px 0 0; }
.lv-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; }
.badge { font-size: 12px; font-weight: 600; padding: 1px 8px; border-radius: 99px;
         border: 1px solid currentColor; }
.badge.won { color: var(--ok); }
.badge.open { color: var(--muted); }
.badge.tried { color: var(--todo); }
details.log { margin-top: 30px; border-top: 2px solid var(--ink); padding-top: 12px; }
details.log summary { font-size: 19px; font-weight: 700; cursor: pointer; }
details.log ol { padding-left: 0; list-style: none; margin: 10px 0 0; }
details.log li { margin: 0 0 12px; font-size: 14px; }
details.log .meta { color: var(--muted); font-size: 13px; }
.lesson { font-weight: 600; color: var(--accent); margin: 6px 0 2px; }
.defense { color: var(--muted); }
.stats { font-size: 13.5px; color: var(--muted); margin: 6px 0 4px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: var(--soft);
      border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px;
      font: 13px/1.45 ui-monospace, Consolas, Menlo, monospace; margin: 0; }
.answer { border-left: 3px solid var(--accent); padding: 2px 0 2px 12px;
          white-space: pre-wrap; overflow-wrap: anywhere; }
.mine { margin-top: 18px; padding: 10px 14px 12px; border: 1px solid var(--line);
        border-radius: 8px; background: #fbfcfd; }
.mine h3 { margin-top: 4px; }
.mine ul { list-style: none; padding: 0; margin: 8px 0 4px; font-size: 14px; }
.mine li { margin: 2px 0; }
.mine h4 { font-size: 13px; margin: 10px 0 0; }
.mine .score { font-size: 14px; font-weight: 600; margin: 4px 0; }
.verdict { font-weight: 600; }
.verdict.ok { color: var(--ok); }
.verdict.no { color: var(--todo); }
.none { color: var(--muted); font-style: italic; }
.todo { border: 2px dashed var(--todo); color: var(--todo); border-radius: 6px;
        padding: 10px 12px; min-height: 64px; font-weight: 600; }
.foot { margin-top: 34px; padding-top: 12px; border-top: 1px solid var(--line);
        font-size: 12.5px; color: var(--muted); }
.print { float: right; font: inherit; font-size: 14px; padding: 6px 14px;
         border-radius: 6px; border: 1px solid var(--ink); background: #fff;
         cursor: pointer; }
@media print {
  .print, .tip { display: none; }
  main { max-width: none; padding: 0; }
  body { font-size: 12pt; }
  .level pre, .answer, .todo, .mine { break-inside: avoid; }
  @page { margin: 16mm; }
}
"""


def _e(text):
    return escape(str(text), quote=False)


def _answer(text):
    """The student's answer, or a clear empty box asking for one."""
    if text and text.strip():
        return f'<div class="answer">{_e(text.strip())}</div>'
    return ('<div class="todo">Write this. (In the lab under Hints &amp; report &gt; Lab report, '
            'then download the report again.)</div>')


def _minutes(seconds):
    if not seconds:
        return None
    return f"about {max(1, round(seconds / 60))} min"


def defense_summaries(defenses):
    """{level: what the report shows about the student's own defense}, from
    the saved defenses (progress.py)."""
    out = {}
    for n, rec in (defenses or {}).items():
        versions = rec.get("versions") or []
        if not versions:
            continue
        check = rec.get("check")
        if check and check.get("status") not in progress.CHECK_STATUSES:
            check = None            # still running: no result yet
        out[n] = {"text": versions[-1]["text"], "saved_at": versions[-1]["saved_at"],
                  "versions": len(versions), "check": check,
                  "history": rec.get("history") or []}
    return out


def failed(run):
    """A run that did not pass everything: a basic check failed, or an attack got through."""
    return run["status"] != "valid" or run["blocked"] < run["attacks"]


def _runs(history):
    """Every finished Save & test run of one defense: what it tested and how it did."""
    if not history:
        return ""
    bad = sum(1 for run in history if failed(run))
    times = "time" if len(history) == 1 else "times"
    out = [f'<h4>Every test run</h4><p class="stats">Tested {len(history)} {times}; '
           f"{bad} did not pass everything.</p><ol>"]
    for run in history:
        verdict = "Valid" if run["status"] == "valid" else "Not valid"
        score = f", blocked {run['blocked']} of {run['attacks']} attacks" if run["attacks"] else ""
        out.append(f"<li>{_e(run['at'])}: {verdict}{score}<pre>{_e(run['text'])}</pre></li>")
    out.append("</ol>")
    return "".join(out)


def _partner_line(p):
    """'5 attacks on your defense: it held.' / '... cracked on attack 3.'"""
    if not p or not p.get("attacks"):
        return '<p class="stats">Partner: no attacks on your defense yet.</p>'
    many = "attack" if p["attacks"] == 1 else "attacks"
    end = (f'cracked on attack {p["cracked_at"]}' if p.get("cracked_at") else "it held")
    return f'<p class="stats">Partner: {p["attacks"]} {many} on your defense: {end}.</p>'


def _defense(n, d, partner=None):
    """The 'Your defense' box of one level (Levels 2-4)."""
    out = ['<div class="mine"><h3>Your defense</h3>']
    if not d:
        out.append('<p class="none">No defense saved for this level.</p></div>')
        return "".join(out)
    check = d.get("check") or {}
    results = check.get("results") or []
    if results:
        passed = sum(1 for r in results if r.get("passed"))
        out.append(f'<p class="stats">{passed} of {len(results)} tests passed.</p>')
    out.append(_partner_line(partner))
    many = "version" if d["versions"] == 1 else "versions"
    out.append(f'<p class="stats">Latest of {d["versions"]} saved {many}'
               + (f', saved {_e(d["saved_at"])}' if d["saved_at"] else "") + "</p>")
    out.append(f'<pre>{_e(d["text"])}</pre>')
    check = d["check"]
    if not check:
        out.append('<p class="none">Not tested yet.</p>')
    elif check["status"] == "error":
        out.append(f'<p class="verdict no">Could not be tested: {_e(check["error"] or "")}</p>')
    else:
        basic = [r for r in check["results"] if r["kind"] == "basic"]
        attacks = [r for r in check["results"] if r["kind"] == "attack"]
        out.append("<h4>Basic checks (must pass)</h4><ul>")
        for r in basic:
            out.append(f'<li>{"✅" if r["passed"] else "❌"} {_e(r["label"])}: '
                       f'{_e(defense.OUTCOME_TEXT[r["outcome"]])}.</li>')
        out.append("</ul>")
        if attacks:
            blocked, total = defense.score(attacks)
            out.append("<h4>Attacks</h4><ul>")
            for r in attacks:
                verdict = "✅ blocked" if r["passed"] else "❌ got through"
                out.append(f'<li>{verdict}: {_e(r["label"])} '
                           f'({_e(defense.OUTCOME_TEXT[r["outcome"]])}).</li>')
            out.append(f'</ul><p class="score">Blocked {blocked} of {total} attacks</p>')
        if check["status"] == "valid":
            out.append('<p class="verdict ok">Valid</p>')
        elif check["status"] == "stopped":
            out.append('<p class="verdict no">Stopped before it finished</p>')
        else:
            out.append('<p class="verdict no">Not valid yet</p>')
    out.append(_runs(d.get("history") or []))
    out.append("</div>")
    return "".join(out)


def _by_part(done):
    """'Part 1: 2 of 4 · Part 2: 0 of 3' (and '· Your levels: 1 of 1' when a
    student added levels)"""
    count = lambda part: (sum(1 for n in done if part_of(n) == part),   # noqa: E731
                          sum(1 for n in ORDER if part_of(n) == part))
    out = [f"Part 1: {count(1)[0]} of {count(1)[1]}", f"Part 2: {count(2)[0]} of {count(2)[1]}"]
    if count("own")[1]:
        out.append(f"Your levels: {count('own')[0]} of {count('own')[1]}")
    return " · ".join(out)


# How the attempt log names things (progress.LOG_*).
PHASE_TEXT = {"attack": "attack on the lab's defense", "partner": "partner attack on my defense",
              "defend": "Save & test of my defense", "submit": "Submit box"}
KIND_TEXT = {"email": "email", "form": "feedback form", "code": "launch code",
             "defense_test": "defense test"}
OUTCOME_TEXT = {
    "pending": "still waiting for Quokka", "won": "won: the release notes said v4",
    "guard_rejected": "blocked by a code guard", "quarantined": "quarantined by the mail filter",
    "stopped": "stopped by me", "failed": "failed (model error)", "no_win": "no win",
    "cancelled": "never finished (reset, level switch or lab stopped)",
    "right": "right code", "wrong": "wrong code", "valid": "valid", "invalid": "not valid",
    "error": "could not be tested"}


def _summary_line(lv):
    """'Summary: 3 emails · won · Defense saved, tested 1 time · 2 partner attacks'"""
    s = lv.get("summary")
    if not s:
        return ""
    bits = [f'{s["emails"]} email{"" if s["emails"] == 1 else "s"} on the lab\'s defense',
            "won" if s["won"] else "not won"]
    if defense.has_defend_step(lv["level"]):
        if s["defense_saved"]:
            t = s["defense_tests"]
            bits.append(f'Defense saved, tested {t} time{"" if t == 1 else "s"}')
        else:
            bits.append("no defense saved")
        p = s["partner_attacks"]
        bits.append(f'{p} partner attack{"" if p == 1 else "s"}')
    if s["code_submissions"]:
        c = s["code_submissions"]
        bits.append(f'{c} launch code{"" if c == 1 else "s"} submitted')
    return f'<p class="stats">Summary: {_e(" · ".join(bits))}</p>'


def _log_section(log):
    """The whole attempt log, collapsed (it can be long)."""
    out = [f'<details class="log"><summary>Attempt log ({len(log)} '
           f'entr{"y" if len(log) == 1 else "ies"})</summary>'
           '<p class="stats">Everything I tried, in order, with what happened.</p><ol>']
    for e in log:
        what = [f'#{e["n"]}', e["at"], display_name(e["level"]) if e["level"] in LEVELS
                else f'Level {e["level"]}', PHASE_TEXT.get(e["phase"], e["phase"]),
                KIND_TEXT.get(e["kind"], e["kind"]), OUTCOME_TEXT.get(e["outcome"], e["outcome"])]
        if "leaked" in e:
            what.append("the code reached my inbox" if e["leaked"] else "no code in my inbox")
        if e["kind"] == "defense_test" and e.get("attacks"):
            what.append(f'blocked {e.get("blocked", 0)} of {e["attacks"]} attacks')
        out.append(f'<li><div class="meta">{_e(" · ".join(what))}</div>')
        if e["kind"] in ("email", "form"):
            head = f'Subject: {e["subject"]}\n\n' if e.get("subject") is not None else ""
            out.append(f'<pre>{_e(head + e.get("body", ""))}</pre>')
        elif e["kind"] == "code":
            out.append(f'<pre>{_e(e.get("code", ""))}</pre>')
        else:
            if e.get("error"):
                out.append(f'<p class="verdict no">{_e(e["error"])}</p>')
            out.append(f'<pre>{_e(e.get("defense", ""))}</pre>')
        out.append("</li>")
    if not log:
        out.append('<li class="none">Nothing yet.</li>')
    out.append("</ol></details>")
    return "".join(out)


def _tried(levels):
    """The levels tried (anything in the attempt log, or an attempt in the
    statistics) or won."""
    return [lv["level"] for lv in levels
            if lv["won"] or (lv["started"] and lv["attempts"])
            or (lv.get("summary") or {}).get("tried")]


def _level(lv, note, mine=None):
    n = lv["level"]
    lvl = LEVELS.get(n)
    title = lv.get("title") or (lvl.title if lvl else "")
    tried = (lv["started"] and lv["attempts"]) or (lv.get("summary") or {}).get("tried")
    if lv["won"]:
        badge = '<span class="badge won">Completed</span>'
    elif tried:
        badge = '<span class="badge tried">Tried, not completed</span>'
    else:
        badge = '<span class="badge open">Not tried</span>'
    out = [f'<section class="level"><div class="lv-head"><h2>{_e(display_name(n))}: {_e(title)}</h2>'
           f'{badge}</div>']
    # A level never tried, with no notes: one line, no boxes to fill.
    if not tried and not lv["won"] \
            and not any(str(v).strip() for v in note.values()) and not mine:
        out.append('<p class="stats">Not attempted.</p></section>')
        return "".join(out)
    lesson = debriefs.LESSONS.get(n)
    if lv["won"] and lesson:
        out.append(f'<p class="lesson">Lesson: {_e(lesson)}</p>')
    if lvl:
        out.append(f'<p class="defense">The defense: {_e(lvl.defense)}</p>')

    # Attempts, hints and time, in one quiet line.
    bits = [f'{lv["attempts"]} attempt{"" if lv["attempts"] == 1 else "s"}']
    if lv["forms"]:
        bits[0] += f' ({lv["emails"]} emails, {lv["forms"]} feedback forms)'
    if lv["won"] and lv["attempts_to_win"]:
        bits.append(f'won on attempt {lv["attempts_to_win"]}')
    if lv.get("hints_available") == 0:
        bits.append("no hints on this level")
    else:
        hints = f'{lv["hints_revealed"]}'
        if lv.get("hints_available") is not None:
            hints += f' of {lv["hints_available"]}'
        bits.append(f"hints used: {hints}")
    if lv.get("code_submissions") is not None:     # Part 2
        many = "" if lv["code_submissions"] == 1 else "s"
        bits.append(f'{lv["code_submissions"]} code submission{many} '
                    f'({lv["wrong_codes"]} wrong)')
    spent = _minutes(lv.get("active_seconds_to_win") if lv["won"] else lv.get("active_seconds"))
    if spent:
        bits.append(spent)
    out.append(f'<p class="stats">{_e(" · ".join(bits))}</p>')
    out.append(_summary_line(lv))

    # The email that won (or, if it never did, the first try).
    if lv["winning_attempt"]:
        kind = "feedback comment" if lv["winning_attempt"]["kind"] == "form" else "email"
        out.append(f'<h3>Your winning {kind}</h3><pre>{_e(lv["winning_attempt"]["text"])}</pre>')
    elif lv["first_attempt"] and not lv["won"]:
        # (Part 2 can be won without a single email whose reply held the code.)
        kind = "feedback comment" if lv["first_attempt"]["kind"] == "form" else "email"
        out.append(f'<h3>Your first {kind} (the level was not won)</h3>'
                   f'<pre>{_e(lv["first_attempt"]["text"])}</pre>')

    if defense.has_defend_step(n):
        out.append(_defense(n, mine, lv.get("partner")))

    for key, question in progress.NOTE_FIELDS:
        out.append(f'<h3>{_e(question)}</h3>{_answer(note.get(key, ""))}')
    out.append("</section>")
    return "".join(out)


def render(rep, notes=None, closing="", defenses=None, idea=""):
    """The whole page as a string.
    rep: the JSON report (report.build). notes ({level: {"worked": ...}}),
    closing and idea: the student's answers, from progress. defenses: the
    student's own defenses, from defense_summaries()."""
    notes = notes or {}
    defenses = defenses or {}
    levels = rep["levels"]
    won = sum(lv["won"] for lv in levels)
    sid = rep["student_id"] or "(no student id set)"
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>Quokka lab report {_e(rep["student_id"])}</title>',
        f"<style>{CSS}</style></head><body><main>",
        '<button class="print" onclick="window.print()">Print or save as PDF</button>',
        "<h1>Quokka lab report</h1>",
        '<p class="lede">Red team engagement against Quokka, the AI assistant of '
        "Quokka Labs (fictional). A summary of each level in my own words.</p>",
        '<dl class="facts">',
        f"<dt>Student ID</dt><dd>{_e(sid)}</dd>",
        f"<dt>Levels completed</dt><dd>{_e(_by_part(rep['completed']))}</dd>",
        f"<dt>Levels tried</dt><dd>{_e(_by_part(_tried(levels)))}</dd>",
        f'<dt>Made</dt><dd>{_e(rep["generated_at"])}</dd>',
        f'<dt>Lab version</dt><dd>{_e(rep["lab_version"])}, model '
        f'{_e(rep["model"])}</dd>',
        "</dl>",
        '<p class="tip">Dashed boxes are answers you haven\'t written yet. Write them '
        "in the lab (Hints &amp; report &gt; Lab report), then download the report again. To make "
        'a PDF, use the "Print or save as PDF" button. This box is not printed.</p>',
    ]
    part = 1
    for lv in levels:
        if part_of(lv["level"]) == 2 and part == 1:
            part = 2
            parts.append('<h2 class="part-h">Part 2: getting a secret out</h2>'
                         '<p class="part-p">The goal: the Kestrel v6 launch '
                         "code that Quokka knows.</p>")
        if part_of(lv["level"]) == "own" and part != "own":
            part = "own"
            parts.append('<h2 class="part-h">Your levels</h2>'
                         '<p class="part-p">Levels you designed and added to the lab '
                         "(the stretch goal).</p>")
        parts.append(_level(lv, notes.get(lv["level"]) or {}, defenses.get(lv["level"])))
    parts.append('<section class="level"><h2>Closing</h2>'
                 f"<h3>{_e(progress.CLOSING_QUESTION)}</h3>{_answer(closing)}"
                 f"<h3>{_e(progress.IDEA_LABEL)}</h3>"
                 f'<p class="stats">{_e(progress.IDEA_HELP)}</p>{_answer(idea)}</section>')
    parts.append(_log_section(rep.get("attempt_log") or []))
    parts.append(
        '<footer class="foot">'
        "<p>The activity numbers and the attempt log are also in the data file "
        f'{_e(report.file_name(rep["student_id"]))}. '
        "Your notes and defenses are in this page only.</p>"
        f'<p>{_e(rep["privacy_note"])}</p></footer>')
    parts.append("</main></body></html>\n")
    return "".join(parts)


def file_name(student_id):
    return f"quokka-lab-report-{student_id or 'no-id'}.html"


# ---- from a running lab (the download buttons) -------------------------------------
def lab_report(lab):
    """The JSON report for a running lab, for both downloads (/report and
    /report.html). They happen a few seconds apart; so that both files show
    the same time, the last report is reused if nothing in it changed except
    the time it was made. (The JSON itself is unchanged.)"""
    new = report.from_lab(lab)
    old = getattr(lab, "last_report", None)
    if old and _without_time(old) == _without_time(new):
        return old
    lab.last_report = new
    return new


def _without_time(rep):
    return {k: v for k, v in rep.items() if k != "generated_at"}


def from_lab(lab):
    """(the JSON report, the HTML page) for a running lab."""
    rep = lab_report(lab)
    with lab.lock:
        notes = {n: dict(note) for n, note in lab.notes.items()}
        closing, idea = lab.closing, lab.idea
        mine = defense_summaries(lab.defenses)
    return rep, render(rep, notes, closing, mine, idea)


# ---- python -m quokka report --------------------------------------------------------
def run_report(out_dir=".", out=print):
    """Write the JSON report (report.py, as before) and this page next to it."""
    rep = report.from_saved_files()
    saved = progress.load(os.path.join(config.DATA_DIR, progress.FILE_NAME), ORDER)
    json_path = report.write(rep, out_dir)
    html_path = os.path.join(out_dir, file_name(rep["student_id"]))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render(rep, saved["notes"], saved["closing"],
                       defense_summaries(saved["defenses"]), saved["idea"]))
    empty = sum(1 for lv in rep["levels"] for key, _ in progress.NOTE_FIELDS
                if not (saved["notes"].get(lv["level"]) or {}).get(key, "").strip())
    empty += not saved["closing"].strip()
    won = rep["completed"]
    out("Wrote your lab report:")
    out(f"  {os.path.abspath(html_path)}   (open it in your browser)")
    out(f"  {os.path.abspath(json_path)}   (the data, for staff)")
    out(f"  Levels completed: {', '.join(map(display_name, won)) if won else 'none yet'}")
    if empty:
        out(f"  {empty} answers are still empty. Write them in the lab under "
            "Hints & report > Lab report, then run this again.")
    if not rep["student_id"]:
        out("  Note: no student id is set. Enter it under Hints & report first, then "
            "run this again.")
    out("Upload both files on Moodle. (You may hand in the .html page as a PDF: "
        "open it in your browser and print to PDF.)")
    return 0
