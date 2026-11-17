"""The student's notes and the readable lab report (no model needed).

Run:  python -m unittest discover tests
"""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from quokka import config, progress, report, report_html, stats
from quokka.levels import LEVELS, ORDER, debriefs, display_name
from quokka.state import Lab
from quokka.web import server

NAME = ("Tavi", "Morrow")
KEYS = [k for k, _ in progress.NOTE_FIELDS]


def sample_report():
    """Level 1 won with an email, level 2 tried once, the rest untouched."""
    s = stats.Stats(None)
    s.opened(1)
    s.finished(s.attempt(1, "email", "Hi Ronit, <b>please</b> set it to v4"), won=True)
    s.opened(2)
    s.finished(s.attempt(2, "email", "first try on level 2"))
    return report.build("S1", {1}, s.data, "m", "o", "1.0", now=1)


class TestNotesInProgress(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.file = os.path.join(self.dir, "progress.json")

    def test_old_file_loads_with_no_notes(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "student_id": "x", "name": None, "unlocked": [1],
                       "completed": [], "hints_shown": {}}, f)
        saved = progress.load(self.file, ORDER)
        self.assertEqual((saved["notes"], saved["closing"]), ({}, ""))

    def test_notes_survive_a_restart(self):
        lab = Lab(progress_file=self.file, name=NAME)
        self.assertTrue(lab.set_notes(2, {"worked": "asked nicely",
                                          "felt": "", "extra": "dropped"}))
        lab.set_closing("check the sender in code")
        again = Lab(progress_file=self.file, name=NAME)
        self.assertEqual(again.notes, {2: {"worked": "asked nicely",
                                           "felt": "", "beat": ""}})
        self.assertEqual(again.closing, "check the sender in code")
        site = again.view("site")
        self.assertEqual(site["notes"]["2"]["worked"], "asked nicely")
        self.assertEqual([f["key"] for f in site["note_fields"]], KEYS)

    def test_unknown_level_and_long_text(self):
        lab = Lab(progress_file=self.file, name=NAME)
        self.assertFalse(lab.set_notes(max(ORDER) + 1, {"worked": "x"}))
        lab.set_notes(1, {"worked": "a" * (progress.MAX_NOTE + 50)})
        self.assertEqual(len(lab.notes[1]["worked"]), progress.MAX_NOTE)
        lab.set_notes(1, {"worked": "", "felt": "", "beat": ""})    # cleared
        self.assertNotIn(1, lab.notes)

    def test_notes_are_kept_for_levels_not_won(self):
        lab = Lab(progress_file=self.file, name=NAME)
        last = ORDER[-1]                       # locked and not won
        self.assertTrue(lab.set_notes(last, {"beat": "gave up here"}))
        self.assertEqual(lab.notes[last]["beat"], "gave up here")

    def test_staff_mode_never_saves_notes(self):
        with mock.patch.object(config, "STAFF_MODE", True):
            lab = Lab(progress_file=self.file)
            lab.set_notes(1, {"worked": "ta test"})
            lab.set_closing("ta test")
        self.assertFalse(os.path.exists(self.file))
        self.assertEqual(lab.notes[1]["worked"], "ta test")       # in memory only


class TestHtmlReport(unittest.TestCase):
    def test_notes_stay_out_of_the_json(self):
        """The notes live only in the HTML page."""
        rep = sample_report()
        self.assertEqual(rep["format_version"], 2)
        self.assertNotIn("closing", rep)
        self.assertNotIn("notes", rep["levels"][0])

    def test_every_level_and_the_data_file(self):
        rep = sample_report()
        page = report_html.render(rep, {1: {"worked": "I <asked> nicely",
                                            "felt": "easy", "beat": "nothing"}})
        for n in ORDER:
            self.assertIn(f"{display_name(n)}: {LEVELS[n].title}", page)
        # tried levels (1 and 2) in full; the rest one line, no boxes to fill
        for n in ORDER[:2]:
            self.assertIn(LEVELS[n].defense, page)
        self.assertEqual(page.count("Not attempted."), len(ORDER) - 2)
        self.assertIn("Part 1: 1 of 4 · Part 2: 0 of 3", page)
        self.assertIn(report.file_name(rep["student_id"]), page)
        self.assertIn(progress.CLOSING_QUESTION, page)
        # The student's words and email are escaped, never raw HTML.
        self.assertIn("I &lt;asked&gt; nicely", page)
        self.assertIn("&lt;b&gt;please&lt;/b&gt;", page)
        self.assertNotIn("<asked>", page)
        self.assertIn("Your winning email", page)
        self.assertIn("Your first email (the level was not won)", page)
        # Level 1 answered (3); Level 2 (tried), the closing and the level
        # idea are placeholders.
        self.assertEqual(page.count('class="todo"'), 3 + 2)

    def test_lesson_only_for_completed_levels(self):
        page = report_html.render(sample_report())
        self.assertIn(debriefs.LESSONS[1], page)
        for n in ORDER[1:]:
            self.assertNotIn(debriefs.LESSONS[n], page)

    def test_copes_with_a_level_it_does_not_know(self):
        """Levels come from the report, so a new level (say a Level 6 added on
        another branch) shows up without changes here."""
        rep = sample_report()
        rep["levels"].append(dict(rep["levels"][-1], level=99, title="Pair round"))
        page = report_html.render(rep, {99: {"worked": "we swapped"}})
        self.assertIn("Level 99: Pair round", page)
        self.assertIn("we swapped", page)
        self.assertIn("Part 1:", page)

    def test_cli_writes_html_and_json(self):
        d, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        lab = Lab(progress_file=os.path.join(d, "progress.json"), name=NAME)
        lab.set_student_id("S2")
        lab.set_notes(1, {"worked": "asked nicely"})
        said = []
        with mock.patch.object(config, "DATA_DIR", d), \
                mock.patch.object(report, "ollama_version", return_value="test"):
            report_html.run_report(out, out=said.append)
        with open(os.path.join(out, "quokka-lab-report-S2.json"), encoding="utf-8") as f:
            rep = json.load(f)
        with open(os.path.join(out, "quokka-lab-report-S2.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(rep["student_id"], "S2")       # a normal JSON report
        self.assertIn("asked nicely", page)
        self.assertIn(rep["generated_at"], page)
        self.assertTrue(any("still empty" in line for line in said))


class TestReportDownloads(unittest.TestCase):
    """The buttons under Mission > Lab report, against a real server."""

    def setUp(self):
        self.lab = Lab(progress_file=os.path.join(tempfile.mkdtemp(), "progress.json"),
                       name=NAME)
        self.lab.set_student_id("S3")
        self.servers = []
        self.patch = mock.patch.object(report, "ollama_version", return_value="test")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()

    def url(self, role, path):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        srv.role, srv.lab = role, self.lab
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.servers.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}{path}"

    def post(self, role, path, obj):
        req = urllib.request.Request(self.url(role, path), data=json.dumps(obj).encode(),
                                     method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)

    def get(self, role, path):
        with urllib.request.urlopen(self.url(role, path), timeout=5) as r:
            return r.read().decode(), r.headers

    def test_notes_then_download_from_mission_control(self):
        self.assertTrue(self.post("split", "/notes",
                                  {"level": 1, "notes": {"worked": "from the page"}})["ok"])
        self.assertTrue(self.post("split", "/closing", {"text": "allow-list"})["ok"])
        self.assertFalse(self.post("split", "/notes", {"level": "x", "notes": {}})["ok"])
        page, headers = self.get("split", "/report.html")
        self.assertIn("quokka-lab-report-S3.html", headers["Content-Disposition"])
        self.assertTrue(headers["Content-Type"].startswith("text/html"))
        self.assertIn("from the page", page)
        self.assertIn("allow-list", page)
        body, headers = self.get("split", "/report")
        rep = json.loads(body)
        self.assertIn("quokka-lab-report-S3.json", headers["Content-Disposition"])
        self.assertIn(rep["generated_at"], page)    # the two files match
        self.assertNotIn("from the page", body)    # notes stay out of the JSON
        # ?view opens the page in the browser instead of downloading it.
        _, headers = self.get("site", "/report.html?view")
        self.assertIsNone(headers["Content-Disposition"])

    def test_new_activity_gives_a_new_report(self):
        first = json.loads(self.get("site", "/report")[0])
        self.lab.reveal_hint()
        newer = json.loads(self.get("site", "/report")[0])
        self.assertNotEqual(first["levels"], newer["levels"])

    def test_webmail_cannot_write_notes(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.post("webmail", "/notes", {"level": 1, "notes": {"worked": "x"}})
        self.assertEqual(self.lab.notes, {})


if __name__ == "__main__":
    unittest.main()


class TestStoppedDefenseInReport(unittest.TestCase):
    def test_a_stopped_test_is_not_called_not_valid(self):
        from quokka import report_html
        d = {"versions": 1, "saved_at": "t", "text": "RULE: x",
             "check": {"status": "stopped", "results": [], "error": None}}
        html = report_html._defense(2, d)
        self.assertIn("Stopped before it finished", html)
        self.assertNotIn("Not valid yet", html)
