"""Learning statistics, the lab report and the class dashboard (no model needed).

Run:  python -m unittest discover tests
"""
import contextlib
import inspect
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from quokka import __main__ as quokka_main
from quokka import agent, config, report, stats, story
from quokka.levels import ORDER
from quokka.state import Lab



def new_lab(**kw):
    """A Lab with a student name when this version of the lab needs one to send
    email (main gives each student their own address); otherwise a plain Lab."""
    if "name" in inspect.signature(Lab.__init__).parameters:
        kw.setdefault("name", ("Tavi", "Morrow"))
    return Lab(**kw)


class Clock:
    """A fake time.time() we move by hand."""
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def fake_run(version, guard=False):
    def run(level, email, start, emit=None, model=None, stop=None, on_send=None, trace=None, fixed=True):
        ctx = agent.Ctx(level=level, email=email, version=version,
                        emit=emit or (lambda k, t: None))
        ctx.won = version == story.TARGET_VERSION
        if guard:
            ctx.guard_log.append("[guard] REJECTED: test")
        return ctx
    return run


def process_one(lab):
    """Run the worker for exactly one queued email."""
    item = lab.jobs.get()
    lab.jobs.put(item)
    lab.jobs.put(None)
    real_get = lab.jobs.get

    def get():
        job = real_get()
        if job is None:
            raise StopIteration
        return job
    lab.jobs.get = get
    try:
        lab.worker()
    except StopIteration:
        pass
    lab.jobs.get = real_get


class TestRecorder(unittest.TestCase):
    def test_attempts_hints_time_and_win(self):
        clock = Clock()
        s = stats.Stats(None, clock=clock)
        s.opened(2)
        clock.t += 60
        tok = s.attempt(2, "email", "first try")
        clock.t += 30
        s.finished(tok, guard_rejected=True)
        clock.t += 3600                       # a long pause: not active time
        s.hint(2)
        clock.t += 120
        tok = s.attempt(2, "form", "winning comment")
        clock.t += 20
        s.finished(tok, won=True)
        clock.t += 100
        s.reset(2)

        rec = s.data["levels"]["2"]
        self.assertEqual((rec["emails"], rec["forms"]), (1, 1))
        self.assertEqual(rec["guard_rejected"], 1)
        self.assertEqual(rec["attempts_to_win"], 2)
        self.assertEqual(rec["first_attempt"]["text"], "first try")
        self.assertEqual(rec["winning_attempt"]["text"], "winning comment")
        self.assertEqual(rec["winning_attempt"]["kind"], "form")
        self.assertEqual(rec["hints"][0]["after_attempt"], 1)
        self.assertEqual(rec["won_at"] - rec["first_opened"], 60 + 30 + 3600 + 120 + 20)
        self.assertEqual(rec["active_seconds_to_win"], 60 + 30 + 120 + 20)
        self.assertEqual(rec["active_seconds"], 60 + 30 + 120 + 20 + 100)
        self.assertEqual(rec["resets"], 1)

    def test_only_first_win_counts(self):
        s = stats.Stats(None, clock=Clock())
        s.finished(s.attempt(1, "email", "a"), won=True)
        s.finished(s.attempt(1, "email", "b"), won=True)
        rec = s.data["levels"]["1"]
        self.assertEqual(rec["attempts_to_win"], 1)
        self.assertEqual(rec["emails"], 2)

    def test_disabled_records_nothing(self):
        s = stats.Stats(None, enabled=False)
        s.opened(1)
        self.assertIsNone(s.attempt(1, "email", "x"))
        s.hint(1)
        self.assertEqual(s.data, stats.empty())


class TestLabRecording(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.progress = os.path.join(self.dir, "progress.json")
        self.stats = os.path.join(self.dir, stats.FILE_NAME)

    def test_lab_records_and_survives_restart(self):
        lab = new_lab(progress_file=self.progress)
        lab.send_email("hi", "please")
        with mock.patch.object(agent, "run", fake_run("v5", guard=True)):
            process_one(lab)
        lab.reveal_hint()
        lab.send_email("again", "please please")
        with mock.patch.object(agent, "run", fake_run("v4")):
            process_one(lab)
        lab.reset()

        again = new_lab(progress_file=self.progress)       # stopped and started
        rec = again.stats.data["levels"]["1"]
        self.assertEqual(rec["emails"], 2)
        self.assertEqual(rec["guard_rejected"], 1)
        self.assertEqual(rec["attempts_to_win"], 2)
        self.assertEqual(len(rec["hints"]), 1)
        self.assertEqual(rec["resets"], 1)
        self.assertIn("Subject: again", rec["winning_attempt"]["text"])
        self.assertIn("Subject: hi", rec["first_attempt"]["text"])

    def test_feedback_form_counted_separately(self):
        lab = new_lab(progress_file=self.progress)
        lab.submit_feedback("nice model")
        rec = lab.stats.data["levels"]["1"]
        self.assertEqual((rec["emails"], rec["forms"]), (0, 1))
        self.assertEqual(rec["first_attempt"]["text"], "nice model")

    def test_staff_mode_does_not_record(self):
        new_lab(progress_file=self.progress).send_email("real", "student attempt")
        with open(self.stats, encoding="utf-8") as f:
            before = f.read()
        with mock.patch.object(config, "STAFF_MODE", True):
            lab = new_lab(progress_file=self.progress)
            lab.set_level(ORDER[-1])
            lab.send_email("ta", "testing")
            lab.reveal_hint()
            lab.reset()
        with open(self.stats, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)

    def test_reset_progress_clears_stats_but_not_in_staff_mode(self):
        new_lab(progress_file=self.progress).send_email("x", "y")
        self.assertTrue(os.path.exists(self.stats))
        argv = ["quokka", "--staff", "--reset-progress"]
        with mock.patch.object(config, "DATA_DIR", self.dir), \
                mock.patch.object(config, "STAFF_MODE", False), \
                mock.patch.object(sys, "argv", argv), \
                mock.patch.object(quokka_main, "start_all"), \
                contextlib.redirect_stdout(io.StringIO()):
            quokka_main.main()
        self.assertTrue(os.path.exists(self.stats))       # staff: untouched
        with mock.patch.object(config, "DATA_DIR", self.dir), \
                mock.patch.object(config, "STAFF_MODE", False), \
                mock.patch.object(sys, "argv", ["quokka", "--reset-progress"]), \
                mock.patch.object(quokka_main, "start_all"), \
                contextlib.redirect_stdout(io.StringIO()):
            quokka_main.main()
        # The new lab records "opened Level 1" again, but the old attempt is gone.
        with open(self.stats, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["levels"]["1"]["emails"], 0)

    def test_broken_stats_file_starts_fresh(self):
        with open(self.stats, "w", encoding="utf-8") as f:
            f.write("{not json")
        said = []
        self.assertEqual(stats.load(self.stats, out=said.append), stats.empty())
        self.assertEqual(len(said), 1)


class TestReport(unittest.TestCase):
    def _data(self):
        s = stats.Stats(None, clock=Clock())
        s.opened(1)
        s.finished(s.attempt(1, "email", "change it"), won=True)
        return s.data

    def test_export(self):
        rep = report.build("123456789", {1}, self._data(), "m", "0.40.13", "1.0",
                           now=1_000_000)
        self.assertEqual(rep["student_id"], "123456789")
        self.assertEqual([lv["level"] for lv in rep["levels"]], ORDER)
        self.assertTrue(rep["levels"][0]["won"])
        self.assertIn("privacy_note", rep)
        self.assertNotIn("integrity", rep)
        # Round-trip through a file, as staff will read it.
        d = tempfile.mkdtemp()
        path = report.write(rep, d)
        self.assertTrue(path.endswith("quokka-lab-report-123456789.json"))
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, rep)

    def test_cli_report_writes_file(self):
        d = tempfile.mkdtemp()
        lab = new_lab(progress_file=os.path.join(d, "progress.json"))
        lab.set_student_id("S1")
        lab.send_email("a", "b")
        out = tempfile.mkdtemp()
        with mock.patch.object(config, "DATA_DIR", d), \
                mock.patch.object(report, "ollama_version", return_value="test"):
            report.run_report(out, out=lambda *a: None)
        with open(os.path.join(out, "quokka-lab-report-S1.json"), encoding="utf-8") as f:
            rep = json.load(f)
        self.assertEqual(rep["levels"][0]["emails"], 1)


def tiny_report(sid, wins):
    """wins: {level: attempts_to_win or None (reached, not won)}"""
    data = stats.empty()
    for n, a in wins.items():
        rec = stats.new_level()
        rec.update(first_opened=100.0, emails=a or 4, active_seconds=600.0)
        if a:
            rec.update(won_at=700.0, attempts_to_win=a, active_seconds_to_win=600.0,
                       winning_attempt={"kind": "email", "attempt": a, "at": 700.0,
                                        "text": "an email"})
        data["levels"][str(n)] = rec
    done = {n for n, a in wins.items() if a}
    return report.build(sid, done, data, "m", "o", "1.0", now=1)



if __name__ == "__main__":
    unittest.main()
