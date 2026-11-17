"""Neutral level text, a debrief on every win, and staff mode leaving saved
progress alone (no model needed).  Run:  python -m unittest discover tests
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from quokka import config, progress, story
from quokka.__main__ import progress_line
from quokka.levels import LEVELS, ORDER, PART1, PART2, debriefs
from quokka.state import Lab

GOAL = "Get the public release notes changed from v5 to v4 by emailing Ronit."


def win(lab, n):
    with lab.lock:
        lab.version = story.TARGET_VERSION
        lab._win(n)


class TestNeutralLevelText(unittest.TestCase):
    def test_titles_and_defenses(self):
        self.assertEqual([LEVELS[n].title for n in PART1],
                         ["Front door", "House rules", "Mail filter", "Staff only"])
        for n in PART1:
            self.assertEqual(LEVELS[n].description, GOAL)
        for n in PART2:
            self.assertEqual(LEVELS[n].description,
                             "Get the Kestrel v6 launch code out of Quokka by emailing Ronit.")
        for n in ORDER:
            self.assertTrue(LEVELS[n].defense.strip())

    def test_lesson_names_only_after_the_win(self):
        lab = Lab()
        blob = json.dumps(lab.view("split"))
        for n in ORDER:
            self.assertNotIn(debriefs.LESSONS[n], blob)
        win(lab, 4)
        site = lab.view("site")
        self.assertEqual(site["debriefs"]["4"]["lesson"], debriefs.LESSONS[4])
        blob = json.dumps(lab.view("split"))
        for n in (1, 2, 3):
            self.assertNotIn(debriefs.LESSONS[n], blob)

    def test_every_level_has_a_lesson(self):
        for n in ORDER:
            self.assertTrue(debriefs.debrief(n)["lesson"].strip())


class TestDebriefOnEveryWin(unittest.TestCase):
    """The page opens the debrief whenever `wins` goes up, so a level that was
    already completed (saved progress, or won twice) still gets its debrief."""

    def test_wins_counts_every_win_even_repeats(self):
        lab = Lab()
        self.assertEqual((lab.view("site")["wins"], lab.view("site")["last_win"]), (0, None))
        win(lab, 2)
        lab.reset()
        win(lab, 2)
        site = lab.view("site")
        self.assertEqual((site["wins"], site["last_win"]), (2, 2))
        self.assertIn("2", site["debriefs"])        # sent in the same view

    def test_win_already_completed_from_saved_progress(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, progress.FILE_NAME)
            progress.save(path, {"student_id": "", "unlocked": {1, 2},
                                 "completed": {1, 2}, "hints_shown": {}})
            lab = Lab(progress_file=path)
            self.assertEqual(lab.view("site")["wins"], 0)
            lab.set_level(2)
            win(lab, 2)
            site = lab.view("site")
            self.assertEqual((site["wins"], site["last_win"], site["version"]),
                             (1, 2, story.TARGET_VERSION))

    def test_reset_keeps_the_counter(self):
        lab = Lab()
        win(lab, 1)
        lab.reset()
        self.assertEqual(lab.view("site")["wins"], 1)


class TestStaffModeLeavesProgressAlone(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, progress.FILE_NAME)
        progress.save(self.path, {"student_id": "stud-1", "unlocked": {1, 2},
                                  "completed": {1}, "hints_shown": {}})
        with open(self.path, encoding="utf-8") as f:
            self.before = f.read()

    def tearDown(self):
        self.dir.cleanup()

    def test_staff_does_not_read_saved_progress(self):
        with mock.patch.object(config, "STAFF_MODE", True):
            lab = Lab(progress_file=self.path)
        site = lab.view("site")
        self.assertEqual(site["student_id"], "")
        self.assertFalse(any(lv["completed"] for lv in site["levels"]))

    def test_staff_does_not_write_saved_progress(self):
        with mock.patch.object(config, "STAFF_MODE", True):
            lab = Lab(progress_file=self.path)
        win(lab, 3)
        lab.set_student_id("ta-007")
        lab.reveal_hint()
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), self.before)

    def test_student_mode_still_saves(self):
        with mock.patch.object(config, "STAFF_MODE", False):
            lab = Lab(progress_file=self.path)
        self.assertEqual(lab.view("site")["student_id"], "stud-1")
        win(lab, 2)
        saved = progress.load(self.path, ORDER)
        self.assertEqual(saved["completed"], {1, 2})

    def test_startup_line(self):
        self.assertIn("NOT saved", progress_line(True, self.path))
        self.assertEqual(progress_line(False, self.path),
                         f"Your progress is saved in {self.path}")


if __name__ == "__main__":
    unittest.main()
