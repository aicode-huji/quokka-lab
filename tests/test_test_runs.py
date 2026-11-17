"""Save & test: the first failing case shows its email (only that one), and
every finished run is kept, with what it tested, for the lab report."""

import unittest

from quokka import defense, report_html
from quokka.state import Lab

from tests.test_defense import NAME, LabCase, process_all

WEAK_LIST = "release\n"  # Level 3: blocks the plain request, not the attacks


class TestOneFailingEmail(unittest.TestCase):
    def test_only_the_first_failing_case_carries_its_email(self):
        out = defense.check(3, WEAK_LIST, lambda k, t: None)
        failed = [r for r in out["results"] if not r["passed"]]
        self.assertGreater(len(failed), 1)  # several fail...
        with_email = [r for r in out["results"] if "email" in r]
        self.assertEqual(len(with_email), 1)  # ...but one is shown
        self.assertIs(with_email[0], failed[0])
        self.assertIn("From: ", with_email[0]["email"])

    def test_a_passing_case_never_carries_its_email(self):
        out = defense.check(3, WEAK_LIST, lambda k, t: None)
        self.assertTrue(all("email" not in r for r in out["results"] if r["passed"]))


class TestRunHistory(LabCase):
    """Through the Lab, on Level 2 (Level 3 has no defend step; the naive
    stand-in model changes the notes whatever the rule says)."""

    WEAK = "RULE: nobody may change anything, ever."

    def test_each_finished_run_is_kept_with_what_it_tested(self):
        lab = self.lab_won(2)
        lab.save_defense(self.WEAK)
        process_all(lab)
        lab.save_defense(self.WEAK + " Not even Ronit.")
        process_all(lab)
        history = lab.defenses[2]["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["text"], defense.clean(self.WEAK))
        self.assertIn("Not even Ronit", history[1]["text"])

    def test_the_history_survives_a_restart(self):
        lab = self.lab_won(2)
        lab.save_defense(self.WEAK)
        process_all(lab)
        again = Lab(name=NAME, progress_file=self.pfile)
        self.assertEqual(len(again.defenses[2]["history"]), 1)

    def test_the_report_lists_every_run_and_counts_the_failed_ones(self):
        lab = self.lab_won(2)
        lab.save_defense(self.WEAK)
        process_all(lab)
        lab.save_defense(self.WEAK + " Not even Ronit.")
        process_all(lab)
        mine = report_html.defense_summaries(lab.defenses)[2]
        html = report_html._defense(2, mine)
        self.assertIn("Tested 2 times; 2 did not pass everything.", html)
