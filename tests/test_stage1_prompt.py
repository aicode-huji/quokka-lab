"""Level 4, stage 1: until the form appears, Quokka runs with Level 1's prompt,
so it tries every change it is asked for and the code guard is what says no."""

import unittest

from quokka import agent
from quokka.levels import LEVELS

from tests.test_defense import LabCase, process_all


def recording_run(seen):
    def run(level, email, start, emit=None, model=None, stop=None, on_send=None, trace=None, fixed=True):
        seen.append(level)
        return agent.Ctx(level=level, email=email, version=start, emit=emit or (lambda k, t: None))

    return run


class TestStage1Prompt(LabCase):
    def lab_on_4(self):
        lab = self.lab_won(3)
        lab.defenses[3] = {
            "versions": [{"text": "x", "saved_at": "t", "hash": "0123456789ab"}],
            "check": None,
            "tested": True,
        }
        self.assertTrue(lab.set_level(4))
        return lab

    def test_before_the_form_quokka_gets_level_1s_prompt_and_level_4s_guard(self):
        lab = self.lab_on_4()
        seen = []
        lab.send_email("Headline", "Please change the release notes to v4.")
        process_all(lab, run=recording_run(seen))
        level = seen[0]
        self.assertEqual(level.system_prompt, LEVELS[1].system_prompt)
        self.assertEqual(level.examples, LEVELS[1].examples)
        self.assertEqual(level.guards, LEVELS[4].guards)
        self.assertEqual(level.number, 4)

    def test_once_the_form_is_shown_quokka_gets_level_4s_own_prompt(self):
        lab = self.lab_on_4()
        lab.form_shown = True
        seen = []
        lab.send_email("Headline", "Please change the release notes to v4.")
        process_all(lab, run=recording_run(seen))
        self.assertEqual(seen[0].system_prompt, LEVELS[4].system_prompt)


if __name__ == "__main__":
    unittest.main()
