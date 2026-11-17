"""The lab's id: saved with the progress, so it survives restarts. A fresh
progress file (a deleted Docker volume) gets a new one, and the pages then clear
what this browser remembers (open boxes, Got it, welcome cards). No model needed.

Run:  python -m unittest discover tests
"""

import json
import os
import tempfile
import unittest

from quokka import progress
from quokka.state import Lab


class TestLabId(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.dir.name, "progress.json")

    def tearDown(self):
        self.dir.cleanup()

    def test_every_view_carries_it(self):
        lab = Lab(progress_file=self.file)
        self.assertTrue(lab.lab_id)
        for role in ("webmail", "ronit", "site", "split"):
            self.assertEqual(lab.view(role)["lab"], lab.lab_id, role)

    def test_same_id_after_a_restart(self):
        first = Lab(progress_file=self.file).lab_id
        self.assertEqual(Lab(progress_file=self.file).lab_id, first)

    def test_progress_is_kept_across_a_restart(self):
        lab = Lab(progress_file=self.file)
        lab.set_student_id("314159265")
        self.assertEqual(Lab(progress_file=self.file).student_id, "314159265")

    def test_a_fresh_progress_file_gets_a_new_id(self):
        first = Lab(progress_file=self.file).lab_id
        os.remove(self.file)
        self.assertNotEqual(Lab(progress_file=self.file).lab_id, first)

    def test_an_older_file_gets_an_id_once(self):
        # a file saved before lab ids existed keeps its progress and gets one id
        data = {
            "version": 5,
            "student_id": "271828182",
            "unlocked": [1, 2],
            "completed": [1],
        }
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        lab = Lab(progress_file=self.file)
        self.assertEqual(lab.student_id, "271828182")
        self.assertIn(1, lab.completed)
        self.assertEqual(Lab(progress_file=self.file).lab_id, lab.lab_id)

    def test_round_trip(self):
        p = progress.empty()
        p["lab_id"] = "abc123"
        progress.save(self.file, p)
        self.assertEqual(progress.load(self.file, [1, 2])["lab_id"], "abc123")


if __name__ == "__main__":
    unittest.main()
