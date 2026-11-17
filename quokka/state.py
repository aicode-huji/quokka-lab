"""The lab's state: the release notes, the mailboxes, the live log, and progress.

Emails go into a queue and a single worker hands them to Quokka ONE at a time,
so every action can be traced to exactly one verified email. Switching level
or pressing Reset starts a fresh "world" (notes back to v5, empty mailboxes);
progress (levels won, the student's own defenses, the attempt log) is kept,
and saved to a file (see progress.py) so it survives stopping the lab.
Learning statistics for staff (attempts, timings, hints) are recorded through
stats.py, which this file only calls.

Every level is open from the start: the student moves freely between them,
and no step is required. Instead of gates, the attempt log (self.log, see
progress.py) records everything the student tried, in order, with its
outcome; the lab report carries it.

Defend mode (Levels 2 and 4, see defense.py): the student writes their own
defense in the browser and presses Save & test (before or after cracking
ours). The worker runs its test emails against it, and from then on the
level runs with THEIR defense ("mine": the Partner phase) until they switch
level.

Part 2 (Levels 5-7, see levels/__init__.py): Quokka knows a launch code, one
random code per student and level (launch_codes.py, kept in progress). The
student wins by typing it into the Submit box (submit_code). No defend step.
"""
import dataclasses
import json
import os
import queue
import re
import secrets
import threading
import time

from . import agent, config, defense, launch_codes, llm, outsider, progress, stats, story, trace
from .levels import LEVELS, ORDER, PART1, debriefs, display_name, missions, part_of, short_number
from .levels.base import with_code

POSTMASTER = "postmaster@quokka-labs.example"


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Lab:
    def __init__(self, model=None, progress_file=None, name=None, warm=False):
        """progress_file: where to save progress (None = keep it in memory only).
        name: (first, last) to start with, e.g. from --name.
        warm: warm the model up ahead of each email (see _maybe_warm); the
        running lab turns it on, tests leave it off."""
        self.model = model
        self.warm = warm
        self.lock = threading.Lock()
        self.jobs = queue.Queue()
        self.gen = 0                    # bumps on every reset; stale jobs are dropped
        # Staff mode opens every level for this run only. It never reads or
        # writes the student's progress file: staff progress lives in memory and
        # is gone when the lab stops, so a TA's test wins never leak into it.
        self.staff = config.STAFF_MODE
        self.progress_file = None if self.staff else progress_file
        progress_file = self.progress_file
        # Counts every win in this run (never reset). The pages open the debrief
        # whenever it goes up, so a level won again still shows its debrief.
        self.wins = 0
        self.last_win = None
        saved = (progress.load(progress_file, ORDER) if progress_file
                 else progress.empty())
        self.student_id = saved["student_id"]
        self.completed = saved["completed"]              # level numbers won
        self.hints_shown = saved["hints_shown"]          # level -> hints revealed
        # Level 4 shows its feedback form only after the code guard has stopped
        # one of the student's own attempts (see _reveal_form).
        self.form_shown = saved["form_shown"]
        # The student's own notes for the lab report (see progress.NOTE_FIELDS).
        self.notes = saved["notes"]                      # level -> {"worked": ...}
        self.closing = saved["closing"]                  # "What would you do...?"
        self.idea = saved["idea"]                        # "Your own level idea"
        # Part 2: level -> this student's launch code, made when first needed.
        self.codes = saved["codes"]
        # Emails sent per level on our defense.
        self.tries = saved["tries"]
        # The attempt log: everything the student tried, in order (progress.py).
        self.log = saved["log"]
        self.log_of = {}            # email id -> its log entry (this world only)
        self.check_log = {}         # level -> the log entry of its running Save & test
        # Partner phase: attacks on the student's own defense, per level, and
        # the attack that first cracked it (None: it held).
        self.partner = saved["partner"]
        # Names this lab's progress. It is saved, so it stays the same across
        # restarts; a fresh progress file (or staff mode) gets a new one, and the
        # pages then forget what the browser remembered (open boxes, Got it).
        self.lab_id = saved["lab_id"] or secrets.token_hex(8)
        self.last_report = None     # the last lab report downloaded (report_html.lab_report)
        # Defend mode: whose defense the current level runs, "ours" (the normal
        # game) or "mine" (the student's own, after Save & test).
        self.mode = "ours"
        # Numbers each Save & test run. Its events carry "test": <run>, so the
        # defend view can show them in its own small shell ("Quokka, live").
        self.test_run = 0
        # level -> {"versions": [{"text", "saved_at", "hash"}], "check": {...},
        #           "tested": bool}   (see progress.py)
        self.defenses = saved["defenses"]
        # The student's name makes their email address (see story.student_address).
        # Staff mode starts with a test name so TAs can play right away.
        self.name, self.me = None, ""
        if saved["name"]:
            self.name, self.me = saved["name"], story.student_address(*saved["name"])
        name = name or (story.STAFF_DEFAULT_NAME if self.staff else None)
        if name and (error := self.set_name(*name)):
            raise ValueError(error)
        # Learning statistics, saved next to the progress. Never in staff mode.
        stats_file = (os.path.join(os.path.dirname(progress_file), stats.FILE_NAME)
                      if progress_file else None)
        self.stats = stats.Stats(stats_file, enabled=not self.staff)
        self.stats.note_model(model)
        self._warm_key = None       # the prompt prefix the model last read (see _maybe_warm)
        with self.lock:
            self._fresh_world(ORDER[0])
            self.stats.opened(ORDER[0])
            if not saved["lab_id"]:
                self._save()
        self._maybe_warm()

    # ---- world ---------------------------------------------------------------
    def _fresh_world(self, level):
        """Call with the lock held."""
        self.gen += 1
        self.level = level
        self.version = story.START_VERSION
        self.next_id = 1
        self.student_inbox = []
        self.student_sent = []
        self.ronit_inbox = []
        self.quokka_sent = []           # every email Quokka sent, with its full body
        self.events = []
        self.attempts = {}              # email id -> stats token (see stats.py)
        self.stop_mail = None           # the email whose Stop was pressed (its id)
        self.attack_no = {}             # email id -> its number among attacks on your defense
        # Behind the scenes: what Quokka reads and writes for the latest email
        # (trace.py). In memory only, never saved.
        self.trace = None
        # Emails of the old world Quokka never finished: their log says so.
        pending = [e for e in self.log_of.values() if e["outcome"] == "pending"]
        for entry in pending:
            entry["outcome"] = "cancelled"
        self.log_of = {}
        if pending:
            self._save()

    def _log(self, **entry):
        """Add one entry to the attempt log (see progress.py) and return it.
        Call with the lock held; the caller saves."""
        n = self.log[-1]["n"] + 1 if self.log else 1
        entry = progress.log_entry(dict(entry, n=n, at=_now()))
        self.log.append(entry)
        return entry

    def _finish(self, mail_id, outcome, **more):
        """The outcome of a logged email. Call with the lock held, for the
        current world only."""
        entry = self.log_of.pop(mail_id, None)
        if entry and entry["outcome"] == "pending":
            entry["outcome"] = outcome
            entry.update(more)
            self._save()

    def _save(self):
        """Call with the lock held, after any change to progress."""
        if not self.progress_file:
            return
        try:
            progress.save(self.progress_file, {
                "student_id": self.student_id, "name": self.name,
                "completed": self.completed, "hints_shown": self.hints_shown,
                "notes": self.notes, "closing": self.closing, "idea": self.idea,
                "defenses": self.defenses, "form_shown": self.form_shown,
                "codes": self.codes, "lab_id": self.lab_id,
                "tries": self.tries, "partner": self.partner, "log": self.log})
        except OSError as e:   # e.g. a read-only folder: keep the lab running
            print(f"Could not save your progress ({e}).")

    def _code(self, level):
        """Part 2: this student's launch code for a level (None for Part 1).
        Made the first time it's needed, then saved. Call with the lock held."""
        if not LEVELS[level].secret:
            return None
        if level not in self.codes:
            self.codes[level] = launch_codes.new_code(taken=set(self.codes.values()))
            self._save()
        return self.codes[level]

    def code_for(self, level):
        with self.lock:
            return self._code(level)

    def _new_id(self):
        mid = self.next_id
        self.next_id += 1
        return mid

    def _event(self, gen, kind, text, test=None):
        """test: the Save & test run this event belongs to (None: a normal email)."""
        with self.lock:
            if gen == self.gen:
                event = {"kind": kind, "text": text}
                if test:
                    event["test"] = test
                self.events.append(event)

    # ---- actions from the windows ----------------------------------------------
    def send_email(self, subject, body):
        """The student emails Ronit from their webmail. Returns False until the
        student has entered their name (it makes their address)."""
        with self.lock:
            me = self.me
            if not me:
                return False
            self.student_sent.append({"to": story.MANAGER, "subject": subject,
                                      "body": body})
        self._deliver(agent.Email(me, subject, body), "email",
                      f"Subject: {subject}\n\n{body}")
        return True

    def submit_feedback(self, comment):
        """The release feedback form emails Ronit from a real staff address."""
        me = self.me
        if not me:
            return False
        if LEVELS[self.level].feedback_form and not self.form_visible(self.level):
            return False        # Level 4: not revealed yet
        self._deliver(agent.Email(story.FEEDBACK, "New release feedback",
                                  story.feedback_form_body(comment, submitter=me),
                                  reply_to=me),
                      "form", comment)
        return True

    def _deliver(self, email, kind, text):
        """kind and text are only for the statistics: "email" or "form", and
        what the student wrote."""
        with self.lock:
            mail = {"id": self._new_id(), "from": email.sender,
                    "subject": email.subject, "body": email.body, "status": "waiting"}
            self.ronit_inbox.append(mail)
            # Statistics are about attacking OUR defenses; defend mode is practice.
            self.attempts[mail["id"]] = (self.stats.attempt(self.level, kind, text)
                                         if self.mode == "ours" else None)
            entry = {"level": self.level, "phase": "attack" if self.mode == "ours" else "partner",
                     "kind": kind, "outcome": "pending",
                     "subject": email.subject if kind == "email" else None,
                     "body": email.body if kind == "email" else text}
            self.log_of[mail["id"]] = self._log(**entry)
            if self.mode == "ours":
                self.tries[self.level] = self.tries.get(self.level, 0) + 1
            else:   # the Partner phase: an attack on the student's own defense
                rec = self.partner.setdefault(self.level, {"attacks": 0, "cracked_at": None})
                rec["attacks"] += 1
                self.attack_no[mail["id"]] = rec["attacks"]
            self._save()
            self.jobs.put(("email", self.gen, mail["id"], self.level, self.mode, email))

    def set_level(self, level):
        with self.lock:
            if level not in LEVELS:     # every level is open, always
                return False
            self._fresh_world(level)
            self.mode = "ours"          # a level starts with our defense
            self.stats.opened(level)
        self._maybe_warm()
        return True

    # ---- defend mode ---------------------------------------------------------------
    def _can_defend(self, level):
        """Levels with a defend step. Open from the start: cracking ours first
        is the usual way, but no step is required."""
        return defense.has_defend_step(level)

    def save_defense(self, text):
        """Save & test: save the student's defense for the current level (a new
        version), then run its test emails (in the worker). Returns an
        error message for the student, or None.

        A defense that can't be used (a Python syntax error, a forbidden
        import, an empty rule) is still saved, so nothing typed is lost, but
        it isn't tested and the level keeps running with ours."""
        if not isinstance(text, str):
            return "Something went wrong. Reload the page and try again."
        text = defense.clean(text)
        if len(text) > defense.MAX_CHARS:
            return f"Your defense is too long (max {defense.MAX_CHARS:,} characters)."
        with self.lock:
            n = self.level
            if not self._can_defend(n):
                return "This level has no defend step."
            rec = self.defenses.setdefault(n, {"versions": [], "check": None,
                                               "tested": False})
            digest = defense.digest(n, text)
            rec["versions"].append({"text": text, "saved_at": _now(), "hash": digest})
            del rec["versions"][:-progress.MAX_VERSIONS]
            error = defense.problem(n, text)
            if error:
                rec["check"] = {"hash": digest, "status": "error", "results": [],
                                "error": error}
                self._log(level=n, phase="defend", kind="defense_test", outcome="error",
                          defense=text, error=error)
                self._save()
                return error
            # From now on this level runs with the student's defense.
            self._fresh_world(n)
            self.mode = "mine"
            rec["check"] = {"hash": digest, "status": "running", "results": [],
                            "error": None}
            old = self.check_log.get(n)
            if old and old["outcome"] == "pending":
                old["outcome"] = "cancelled"    # a newer version replaces it untested
            self.check_log[n] = self._log(level=n, phase="defend", kind="defense_test",
                                          outcome="pending", defense=text)
            self._save()
            self.jobs.put(("check", self.gen, n, digest))
            return None

    def set_mode(self, mode):
        """Switch the current level between our defense ("ours") and the
        student's saved one ("mine"). Starts a fresh world."""
        with self.lock:
            if mode not in ("ours", "mine"):
                return False
            if mode == "mine":
                rec = self.defenses.get(self.level) or {}
                if not (self._can_defend(self.level) and rec.get("tested")):
                    return False
            self._fresh_world(self.level)
            self.mode = mode
        self._maybe_warm()
        return True

    def stop_check(self):
        """Save & test's Stop button: end the current level's running test
        before Quokka's next model call. Returns False if nothing was running."""
        with self.lock:
            check = (self.defenses.get(self.level) or {}).get("check") or {}
            if check.get("status") != "running":
                return False
            check["stop"] = True
        llm.cancel()            # the model call in flight is the test's own: end it now
        return True

    def stop_email(self):
        """Stop this email: Quokka abandons the email it is reading. What it
        already did stands; the next email goes ahead. False if none is read."""
        with self.lock:
            reading = [m for m in self.ronit_inbox if m.get("status") == "reading"]
            if not reading:
                return False
            self.stop_mail = reading[0]["id"]
        llm.cancel()            # the model call in flight is this email's: end it now
        return True

    def _run_check(self, gen, level_no, digest):
        """The worker runs the test emails (see defense.check). Only the
        latest saved version is tested: an older one waiting here is skipped."""
        with self.lock:
            rec = self.defenses.get(level_no) or {}
            check = rec.get("check") or {}
            if check.get("hash") != digest or check.get("status") != "running":
                return
            text = rec["versions"][-1]["text"]
            self._warm_key = None       # the test emails replace the model's prefix
            self.test_run += 1
            run = self.test_run
        emit = lambda k, t: self._event(gen, k, t, test=run)

        def on_result(result):          # show each result while the rest run
            with self.lock:
                if (rec.get("check") or {}).get("hash") == digest:
                    rec["check"]["results"] = rec["check"]["results"] + [result]

        def stop():                     # Stop pressed, or a newer version saved
            check = rec.get("check") or {}
            return check.get("hash") != digest or bool(check.get("stop"))

        try:
            out = defense.check(level_no, text, emit, model=self.model,
                                on_result=on_result, stop=stop)
        except Exception as e:   # e.g. Ollama not running: no verdict either way
            if stop():               # Stop cancelled the model call: not an error
                with self.lock:
                    done = list((rec.get("check") or {}).get("results") or [])
                out = {"valid": False, "results": done, "error": None, "stopped": True}
                emit("check", "Stopped. Edit your defense and press Save & test again.")
            else:
                out = {"valid": False, "results": [],
                       "error": f"The test could not run: {e}. Is Ollama running?"}
                emit("error", out["error"])
        with self.lock:
            if (rec.get("check") or {}).get("hash") != digest:
                return                  # a newer version was saved meanwhile
            if out.get("stopped"):
                status = "stopped"      # no verdict
            else:
                status = "valid" if out["valid"] else ("error" if out["error"] else "invalid")
            rec["check"] = {"hash": digest, "status": status,
                            "results": out["results"], "error": out["error"]}
            if status in ("valid", "invalid"):      # a finished run: kept for the report
                blocked, attacks = defense.score(out["results"])
                rec.setdefault("history", []).append(
                    {"at": _now(), "status": status, "blocked": blocked, "attacks": attacks,
                     "text": text})
                del rec["history"][:-progress.MAX_VERSIONS]
            if status not in ("error", "stopped"):
                rec["tested"] = True    # saved and tested: the Partner phase opens
            entry = self.check_log.pop(level_no, None)
            if entry and entry["outcome"] == "pending":
                blocked, attacks = defense.score(out["results"])
                entry.update(outcome=status, blocked=blocked, attacks=attacks)
                if out.get("error"):
                    entry["error"] = out["error"]
            self._save()
            if gen != self.gen:
                return
            blocked, attacks = defense.score(out["results"])
            stopped = f" It blocked {blocked} of {attacks} attacks." if attacks else ""
            if status == "valid":
                text = (f"Your defense for Level {level_no} is valid.{stopped} Now "
                        f"attack it, or swap laptops with your partner.")
            elif status == "invalid":
                text = (f"Not valid yet: a basic check failed.{stopped} You can "
                        f"still attack it, or edit it and test again.")
            elif status == "stopped":
                text = "Test stopped. Edit your defense and press Save & test again."
            else:
                text = None
            if text:
                self.events.append({"kind": "check", "text": text, "test": run})

    def reset(self):
        with self.lock:
            self._fresh_world(self.level)
            self.stats.reset(self.level)
        self._maybe_warm()

    def set_student_id(self, student_id):
        sid = student_id.strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{1,20}", sid):
            return False
        with self.lock:
            self.student_id = sid
            self._save()
        return True

    def set_name(self, first, last):
        """Set the student's name. Returns an error message for the student, or
        None if it worked. Only English letters (and inner hyphens) pass, so the
        name can't smuggle anything into the From line or the pages."""
        try:
            me = story.student_address(first, last)
        except ValueError as e:
            return str(e)
        with self.lock:
            self.name = (story.name_part(first), story.name_part(last))
            self.me = me
            self._save()
        return None

    def set_notes(self, level, answers):
        """Save the student's notes on one level (answers: {"worked": ..., ...}).
        Only the known questions are kept. Works for any level, won or not, so a
        student who gave up can still write about it. Returns False for a level
        that doesn't exist."""
        if level not in LEVELS:
            return False
        note = {key: progress.clean_note(answers.get(key, ""))
                for key, _ in progress.NOTE_FIELDS}
        with self.lock:
            if any(note.values()):
                self.notes[level] = note
            else:
                self.notes.pop(level, None)     # all empty: nothing to keep
            self._save()
        return True

    def set_closing(self, text):
        """Save the answer to the report's closing question."""
        with self.lock:
            self.closing = progress.clean_note(text)
            self._save()

    def set_idea(self, text):
        """Save the report's optional "Your own level idea"."""
        with self.lock:
            self.idea = progress.clean_note(text)
            self._save()

    def submit_code(self, text):
        """Part 2's Submit box: the student types the launch code. True if it's
        right (ignoring case, spaces and dashes): the level is won. False if
        wrong; None if the current level has no launch code. Outcome-based like
        Part 1: our code compares, the model's words never count."""
        with self.lock:
            n = self.level
            if not LEVELS[n].secret:
                return None
            right = launch_codes.matches(text, self._code(n))
            self.stats.code_submitted(n, right)
            self._log(level=n, phase="submit", kind="code", code=text,
                      outcome="right" if right else "wrong")
            if right:
                self._win(n)
            else:
                self._save()
            return right

    def reveal_hint(self):
        with self.lock:
            total = len(LEVELS[self.level].hints)
            shown = self.hints_shown.get(self.level, 0)
            self.hints_shown[self.level] = min(total, shown + 1)
            if shown < total:
                self.stats.hint(self.level)
            self._save()

    # ---- the worker: one email per run -----------------------------------------
    def worker(self):
        while True:
            if self.jobs.empty():
                # Idle: warm the model up for the next email (a level switch or
                # a Save & test may have changed what it reads; see _maybe_warm).
                self._maybe_warm()
            job = self.jobs.get()
            if job[0] == "check":       # the test emails of Save & test
                _, gen, level_no, digest = job
                self._run_check(gen, level_no, digest)
                continue
            _, gen, mail_id, level_no, mode, email = job
            with self.lock:
                if gen != self.gen:
                    continue        # the lab was reset while this email waited
                mail = next(m for m in self.ronit_inbox if m["id"] == mail_id)
                mail["status"] = "reading"
                self.stop_mail = None
                version = self.version
                versions = (self.defenses.get(level_no) or {}).get("versions") or []
                mine = versions[-1]["text"] if versions else None
                code = self._code(level_no)         # Part 2 only, else None
            self._event(gen, "received", f"Email #{mail_id} received. Real sender "
                                         f"(checked by code): {email.sender}")
            try:
                level = self._email_level(level_no, mode, mine, code)
            except defense.DefenseError as e:   # fail closed: nothing changes
                self._event(gen, "error", str(e))
                with self.lock:
                    if gen == self.gen:
                        mail["status"] = "done"
                        self._finish(mail_id, "failed")
                continue

            # Inbound filters run before Quokka sees anything (Level 3).
            reason = None
            for inbound_filter in level.inbound_filters:
                reason = inbound_filter(email)
                if reason:
                    break
            if reason:
                self._event(gen, "guard", f"[filter] QUARANTINED: {reason}")
                with self.lock:
                    if gen == self.gen:
                        mail["status"] = "quarantined"
                        self.stats.finished(self.attempts.pop(mail_id, None),
                                            quarantined=True)
                        self._finish(mail_id, "quarantined")
                        if story.is_student(email.sender):
                            self.student_inbox.append({
                                "from": POSTMASTER,
                                "subject": "Message quarantined: " + email.subject,
                                "body": "Your message was not delivered. It was "
                                        "stopped by the Quokka Labs mail filter: "
                                        f"{reason}."})
                continue

            sent = []           # emails already delivered by on_send
            reached = []        # ... of them, the ones that landed in the student's inbox

            def deliver(out, gen=gen, sender=email.sender, sent=sent, reached=reached):
                """An email Quokka just sent: to the student's inbox, Ronit's, or
                only the sent list. Right away, not when the run ends."""
                with self.lock:
                    if gen != self.gen:
                        return
                    sent.append(out)
                    # Replies to the student land in their inbox: their address now,
                    # or the one this email came from (if they renamed meanwhile).
                    mine_addr = {a.lower() for a in (self.me, sender) if story.is_student(a)}
                    m = dict(out, **{"from": story.QUOKKA})
                    self.quokka_sent.append(dict(m, id=self._new_id()))
                    if mine_addr & story.addresses(out["to"]):
                        self.student_inbox.append(m)
                        reached.append(m)
                    elif story.MANAGER in out["to"]:
                        self.ronit_inbox.append(dict(m, id=self._new_id(), status="done"))

            # Behind the scenes: this email's model calls, for the console. The
            # hidden examples show once the level is won (they no longer spoil it).
            tr = trace.Trace(level, show_examples=level_no in self.completed, mail=mail_id)
            with self.lock:
                if gen == self.gen:
                    self.trace = tr
            # The model's prompt cache will hold this level's prefix (see _maybe_warm).
            self._warm_key = self._prefix_key(level)
            try:
                ctx = agent.run(level, email, version,
                                emit=lambda k, t: self._event(gen, k, t),
                                model=self.model,
                                stop=lambda: self.stop_mail == mail_id,
                                on_send=deliver, trace=tr,
                                # the model's normal sampling (config.py)
                                fixed=config.EMAIL_SAMPLING_FIXED)
            except Exception as e:   # e.g. Ollama not running
                self._event(gen, "error", f"Quokka could not finish this email ({e}). "
                            "That was the model, not your email: send it again.")
                with self.lock:
                    if gen == self.gen:
                        mail["status"] = "failed"
                        self.stats.finished(self.attempts.pop(mail_id, None),
                                            error=True)
                        self._finish(mail_id, "failed")
                continue

            if ctx.stopped:     # Stop this email: what Quokka already did still stands
                self._event(gen, "lab", "Stopped by you: Quokka didn't finish this email.")
            with self.lock:
                if gen != self.gen:
                    continue
                self.version = ctx.version
                stopped = ctx.stopped
            # (anything a run put in its outbox without on_send, delivered now)
            for out in ctx.outbox:
                if not any(out is x for x in sent):
                    deliver(out)
            with self.lock:
                if gen != self.gen:
                    continue
                mail["status"] = "stopped" if stopped else "done"
                won = self.version == story.TARGET_VERSION
                if ctx.guard_log and mode == "ours" and level.feedback_form:
                    self._reveal_form()
                # Part 2: did a reply carry the code (in a form we can read)?
                leaked = bool(code) and any(
                    launch_codes.leaked(f"{out['subject']}\n{out['body']}", code)
                    for out in ctx.outbox)
                self.stats.finished(self.attempts.pop(mail_id, None),
                                    guard_rejected=bool(ctx.guard_log), won=won,
                                    leaked=leaked)
                outcome = ("won" if won else "stopped" if stopped
                           else "guard_rejected" if ctx.guard_log else "no_win")
                more = {}
                if code:    # Part 2: did the code reach the student's own inbox?
                    more["leaked"] = any(
                        launch_codes.leaked(f"{m['subject']}\n{m['body']}", code)
                        for m in reached)
                self._finish(mail_id, outcome, **more)
                if won and mode == "ours":
                    self._win(level_no)
                elif won:
                    rec = self.partner.get(level_no)
                    if rec and rec["cracked_at"] is None and mail_id in self.attack_no:
                        rec["cracked_at"] = self.attack_no[mail_id]
                        self._save()
                    # (the notes count it; stats and wins do not)
                    self.events.append({"kind": "cracked", "text":
                        f"Your defense was cracked: the release notes say "
                        f"{story.TARGET_VERSION}. (Practice: nothing is recorded.)"})

    def _email_level(self, level_no, mode, mine, code):
        """The level Quokka runs an email with, as it reads it. mine: the
        student's latest defense (defend mode); code: Part 2's launch code.
        Raises defense.DefenseError for a defense that can't be built."""
        if mode == "ours":
            level = LEVELS[level_no]
            if level.feedback_form and not self.form_visible(level_no):
                # Level 4, stage 1 (no form yet): Quokka gets Level 1's prompt,
                # so it tries any change it is asked for and the code guard
                # is what stops it. The level's own prompt is about the form.
                level = dataclasses.replace(level,
                                            system_prompt=LEVELS[1].system_prompt,
                                            examples=LEVELS[1].examples)
        else:
            # Defend mode: the student's latest defense, built again for THIS email.
            level = defense.build_level(level_no, mine or "")
        if code:    # Part 2: this student's launch code goes into the prompt
            level = with_code(level, code)
        return level

    # ---- warm-up: the model reads the next email's prompt ahead of time -----------
    # Ollama keeps the prompt it last read (its prefix: instructions, hidden
    # examples, tools) and reuses it, so an email on the same level starts at
    # once. A new prefix (lab start, a level switch, defend mode, a Save & test)
    # means reading ~1,400 tokens first, about half a minute on a laptop CPU.
    # So when the prefix changes and the worker is idle, a background request
    # makes the model read it now (llm.warm). Nothing shows anywhere, and any
    # real model call cancels it at once.
    def _warm_messages(self, level):
        """The exact prefix and tools the next email will send, with a
        placeholder email (only the shared prefix is cached)."""
        return agent.request(level, agent.Email(self.me or story.ME, "", ""))

    def _prefix_key(self, level):
        msgs, tools = self._warm_messages(level)
        return hash(json.dumps([msgs[:-1], tools, self.model], sort_keys=True, default=str))

    def _maybe_warm(self):
        if not self.warm:
            return
        try:
            with self.lock:
                if not self.jobs.empty() or any(m.get("status") == "reading"
                                                for m in self.ronit_inbox):
                    return          # busy: the worker warms up when it is done
                n, mode = self.level, self.mode
                versions = (self.defenses.get(n) or {}).get("versions") or []
                mine = versions[-1]["text"] if versions else None
                code = self._code(n)
            level = self._email_level(n, mode, mine, code)
            msgs, tools = self._warm_messages(level)
            key = self._prefix_key(level)
            if key == self._warm_key:
                return              # the model has read this prefix already
            self._warm_key = key
            llm.warm(msgs, tools, model=self.model)
        except Exception:           # a warm-up is only ever a nicety  # noqa: BLE001
            return

    def _reveal_form(self):
        """Level 4, stage 2: the code guard just stopped the student, so the
        feedback form appears. Call with the lock held."""
        if self.form_shown:
            return
        self.form_shown = True
        self.events.append({"kind": "check",
                            "text": "Quokka Labs also has a public feedback form."})
        self._save()

    def form_visible(self, level_no):
        """Is the feedback form on the page? Staff and anyone who has won the
        level see it at once; defend mode needs it for the partner's attacks."""
        if not LEVELS[level_no].feedback_form:
            return False
        return (self.form_shown or self.staff or level_no in self.completed
                or self.mode == "mine")

    def _win(self, level_no):
        """Call with the lock held."""
        self.completed.add(level_no)
        self.wins += 1
        self.last_win = level_no
        self._save()
        if LEVELS[level_no].secret:
            text = f"{display_name(level_no)} complete: you found the launch code."
        else:
            text = f"Level {level_no} complete: the release notes say {story.TARGET_VERSION}."
        self.events.append({"kind": "win", "text": text})

    # ---- what each window may see ------------------------------------------------
    def trace_view(self, since=0, reads=0, mail=None):
        """Behind the scenes (GET /trace): the latest email's model calls. `since`
        and `reads` say what the page already has (tokens, and calls' inputs),
        for the email `mail`; for any other email it gets everything."""
        with self.lock:
            tr = self.trace
        if tr is None:
            return {"mail": None, "secret": bool(LEVELS[self.level].secret), "calls": [],
                    "reads": [], "tools": [], "tokens": [], "total": 0}
        if mail != tr.mail:
            since, reads = 0, 0
        return tr.view(since, reads)

    def view(self, role):
        with self.lock:
            return dict(self._view(role), lab=self.lab_id)

    def _trace_summary(self):
        """Call with the lock held. The latest email's model calls, status and
        token counts only (the console's "model call N" lines use them)."""
        tr = self.trace
        return {"trace_mail": tr and tr.mail, "calls": tr.summary() if tr else []}

    def _phases(self):
        """Call with the lock held. The three phases of a level with a defend
        step: Attack (our defense), Defend (your own), Partner (attacks on your
        defense, once one is tested). All optional, in any order."""
        n = self.level
        if not defense.has_defend_step(n):
            return None
        rec = self.defenses.get(n) or {}
        check = rec.get("check") or {}
        results = check.get("results") or []
        tested = bool(rec.get("tested"))
        p = self.partner.get(n) or {}
        return {
            "attack": {"won": n in self.completed, "tried": self.tries.get(n, 0) > 0},
            "defend": {"open": self._can_defend(n), "saved": bool(rec.get("versions")),
                       "tested": tested, "status": check.get("status"),
                       "passed": sum(1 for r in results if r.get("passed")),
                       "total": len(defense.cases(n))},
            "partner": {"open": self._can_defend(n) and tested,
                        "attacks": p.get("attacks", 0), "cracked_at": p.get("cracked_at")},
        }

    def _defend_view(self):
        """Call with the lock held. What the defend view and banner show."""
        n = self.level
        if not defense.has_defend_step(n):      # Level 1, the warm-up
            return {"step": False}
        rec = self.defenses.get(n) or {}
        versions = rec.get("versions") or []
        check = rec.get("check")
        later = [x for x in ORDER if x > n]
        return {
            "step": True,
            "available": self._can_defend(n),
            "kind": defense.KINDS[n],
            # What the editor shows: the latest saved version, or the starter.
            "text": versions[-1]["text"] if versions else defense.starter(n),
            "saved": bool(versions),
            "versions": len(versions),
            "saved_at": versions[-1]["saved_at"] if versions else None,
            "tested": bool(rec.get("tested")),
            # The test emails of Save & test (what the results area lists).
            "cases": [{k: c[k] for k in ("id", "kind", "label", "expect")}
                      for c in defense.cases(n)],
            "check": check and {"status": check["status"], "results": check["results"],
                                "error": check["error"],
                                "total": len(defense.cases(n)),
                                "blocked": defense.score(check["results"])[0],
                                "attacks": defense.score(check["results"])[1]},
            "next": later[0] if later else None,       # a shortcut, never a gate
            # Quokka's events for the latest Save & test run (the small shell).
            "test_log": [e for e in self.events if e.get("test") == self.test_run],
        }

    def _view(self, role):
        """Call with the lock held."""
        if role == "webmail":
            return {"inbox": self.student_inbox, "sent": self.student_sent,
                    "me": self.me}      # "" until the student enters their name
        if role == "ronit":
            if LEVELS[self.level].secret:
                # Part 2: the student is an outsider. Every step shows, but what
                # Quokka writes is garbled (outsider.py); their inbox has the rest.
                return {"inbox": outsider.ronit_inbox(self.ronit_inbox),
                        "events": outsider.events(self.events, self.me),
                        "sent": outsider.mails(self.quokka_sent), "level": self.level,
                        "level_name": display_name(self.level),
                        "world": self.gen, **self._trace_summary()}
            return {"inbox": self.ronit_inbox, "events": self.events,
                    "sent": self.quokka_sent, "level": self.level,
                    "level_name": display_name(self.level),
                    "world": self.gen,   # changes on every reset or level switch
                    **self._trace_summary()}
        if role == "site":
            lvl = LEVELS[self.level]
            shown = self.hints_shown.get(self.level, 0)
            # tried: anything in the attempt log (or, from older files, an email)
            tried = ({e["level"] for e in self.log}
                     | {n for n, c in self.tries.items() if c})
            return {
                "level": self.level, "title": lvl.title,
                "name": display_name(self.level),
                "description": lvl.description,
                # Part 2: the level is won with the launch code, not the notes.
                "secret": lvl.secret,
                # The strip at the top of mission control (levels/missions.py).
                "mission": missions.mission(self.level, self.form_visible(self.level)),
                "feedback_form": self.form_visible(self.level),
                "version": self.version, "target": story.TARGET_VERSION,
                "start": story.START_VERSION,
                # every level is open: the list only says what was won or tried
                # part: 1, 2 or "own" (a student's own level); short: its button's number
                "levels": [{"number": n, "title": LEVELS[n].title,
                            "name": display_name(n), "part": part_of(n),
                            "short": short_number(n), "secret": LEVELS[n].secret,
                            "completed": n in self.completed,
                            "tried": n in tried}
                           for n in ORDER],
                "student_id": self.student_id,
                "student_name": ({"first": self.name[0], "last": self.name[1]}
                                 if self.name else None),
                "me": self.me,
                "hints": list(lvl.hints[:shown]),
                "hints_left": len(lvl.hints) - shown,
                "defense": (lvl.defense if self.mode == "ours"
                            else "Defend mode: Quokka is using YOUR defense."),
                "mode": self.mode,
                # Levels 2 and 4: Attack, Defend, Partner (None on other levels)
                "phases": self._phases(),
                "tries": self.tries.get(self.level, 0),
                "defend": self._defend_view(),
                "defend_levels": list(defense.STEPS),       # levels with a defend step
                # The student's own notes for the lab report, and the questions.
                "notes": {str(n): note for n, note in sorted(self.notes.items())},
                "note_fields": [{"key": k, "question": q}
                                for k, q in progress.NOTE_FIELDS],
                "closing": self.closing,
                "closing_question": progress.CLOSING_QUESTION,
                "idea": self.idea,
                "idea_label": progress.IDEA_LABEL, "idea_help": progress.IDEA_HELP,
                # Debriefs and challenges explain how a level is beaten, so only
                # levels the student has already completed are ever sent.
                "debriefs": {str(n): debriefs.debrief(n) for n in sorted(self.completed)},
                # (about Part 1's code: shown once Part 1 is complete)
                "final_challenge": (debriefs.FINAL_CHALLENGE
                                    if PART1[-1] in self.completed else None),
                # Goes up on EVERY win (first or not): the page opens the
                # debrief of `last_win` whenever `wins` grows.
                "wins": self.wins, "last_win": self.last_win,
            }
        if role == "split":
            # Mission control (port 9080) shows all three windows at once. Students
            # can open Ronit's computer anyway, so nothing new is revealed here.
            return {r: self._view(r) for r in ("webmail", "ronit", "site")}
        return {}
