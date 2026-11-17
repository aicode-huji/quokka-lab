"""The phases of a level with a defend step (Part 1, Levels 2-4): Attack, then
Defend (open once the level is won), then Partner (open once the defense is
tested). Attacks on the student's own defense are counted, with the attack
that first cracked it, saved and shown in the report. No model needed.

Run:  python -m unittest discover tests
"""

import os
import tempfile
import unittest
from unittest import mock

from quokka import agent, report, report_html, story
from quokka.state import Lab

NAME = ("Dana", "Levin")


def process_all(lab):
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


def run_to(version):
    def run(level, email, start, emit=None, model=None, stop=None, on_send=None, trace=None, fixed=True):
        ctx = agent.Ctx(level=level, email=email, version=version, emit=emit or (lambda k, t: None))
        ctx.won = version == story.TARGET_VERSION
        return ctx

    return run


def tested_defense(lab, n, passed=(True, True, False)):
    lab.defenses[n] = {
        "versions": [{"text": "RULE: only Ronit", "saved_at": "t", "hash": "0123456789ab"}],
        "check": {
            "hash": "0123456789ab",
            "status": "invalid",
            "error": None,
            "results": [{"id": i, "kind": "attack", "passed": p, "label": f"Attack {i}",
                               "outcome": "unchanged" if p else "changed"} for i, p in enumerate(passed)],
        },
        "tested": True,
        "history": [],
    }


class TestPhases(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.dir.name, "progress.json")
        self.lab = Lab(progress_file=self.file, name=NAME)
        self.lab.set_level(2)

    def tearDown(self):
        self.dir.cleanup()

    def phases(self):
        return self.lab.view("site")["phases"]

    def test_level_1_has_no_phases(self):
        self.lab.set_level(1)
        self.assertIsNone(self.phases())

    def test_level_3_has_no_defend_step(self):
        # a word list of your own only repeats what Level 3 showed
        self.lab.completed.update({2, 3})
        tested_defense(self.lab, 2)
        self.lab.set_level(3)
        self.assertIsNone(self.phases())

    def test_defend_is_open_before_the_win(self):
        p = self.phases()
        self.assertFalse(p["attack"]["won"])
        self.assertTrue(p["defend"]["open"])     # every step is optional, in any order
        self.assertFalse(p["partner"]["open"])   # nothing to attack before a tested defense

    def test_partner_opens_after_a_test_and_shows_the_score(self):
        self.lab.completed.add(2)
        tested_defense(self.lab, 2)
        p = self.phases()
        self.assertTrue(p["partner"]["open"])
        self.assertEqual((p["defend"]["passed"], p["defend"]["status"]), (2, "invalid"))
        self.assertGreater(p["defend"]["total"], 0)

    def test_attacks_on_your_defense_are_counted_and_the_crack_found(self):
        self.lab.completed.add(2)
        tested_defense(self.lab, 2)
        self.assertTrue(self.lab.set_mode("mine"))
        with mock.patch.object(agent, "run", run_to(story.START_VERSION)):
            self.lab.send_email("a", "try 1")
            self.lab.send_email("b", "try 2")
            process_all(self.lab)
        self.assertEqual(self.phases()["partner"]["attacks"], 2)
        self.assertIsNone(self.phases()["partner"]["cracked_at"])
        with mock.patch.object(agent, "run", run_to(story.TARGET_VERSION)):
            self.lab.send_email("c", "try 3")
            self.lab.send_email("d", "try 4")
            process_all(self.lab)
        p = self.phases()["partner"]
        self.assertEqual((p["attacks"], p["cracked_at"]), (4, 3))
        # attacks on your own defense don't count as tries on our defense
        self.assertEqual(self.lab.tries.get(2, 0), 0)
        # saved
        again = Lab(progress_file=self.file, name=NAME)
        self.assertEqual(again.partner[2], {"attacks": 4, "cracked_at": 3})

    def test_levels_say_which_were_tried(self):
        self.lab.send_email("a", "try")
        levels = {lv["number"]: lv for lv in self.lab.view("site")["levels"]}
        self.assertTrue(levels[2]["tried"])
        self.assertFalse(levels[3]["tried"])

    def test_the_report_has_the_partner_line(self):
        self.lab.set_student_id("123456789")
        self.lab.completed.add(2)
        tested_defense(self.lab, 2)
        self.lab.partner[2] = {"attacks": 5, "cracked_at": None}
        rep = report.from_lab(self.lab)
        lv2 = next(lv for lv in rep["levels"] if lv["level"] == 2)
        self.assertEqual(lv2["partner"], {"attacks": 5, "cracked_at": None})
        page = report_html.from_lab(self.lab)[1]
        self.assertIn("5 attacks on your defense", page)
        self.assertIn("it held", page)
        self.assertIn("2 of 3 tests passed", page)


if __name__ == "__main__":
    unittest.main()
