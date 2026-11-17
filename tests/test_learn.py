"""Debriefs, challenges and what students may see (no model needed).
Run:  python -m unittest discover tests
"""
import json
import unittest
from unittest import mock

from quokka import agent, filters, guards, llm, story, tools
from quokka.levels import LEVELS, ORDER, PART1, debriefs
from quokka.state import Lab


def win(lab, n):
    with lab.lock:
        lab._win(n)


class TestDebriefsOnlyAfterWinning(unittest.TestCase):
    def test_nothing_before_any_win(self):
        site = Lab().view("site")
        self.assertEqual(site["debriefs"], {})
        self.assertIsNone(site["final_challenge"])
        # Not hidden somewhere else in the payload either.
        blob = json.dumps(Lab().view("split"))
        for n in ORDER:
            self.assertNotIn(debriefs.TEXT[n]["fix"], blob)
            self.assertNotIn(debriefs.PARTNER_PROMPT, blob)

    def test_only_completed_levels_are_sent(self):
        lab = Lab()
        win(lab, 1)
        win(lab, 2)
        site = lab.view("site")
        self.assertEqual(sorted(site["debriefs"]), ["1", "2"])
        blob = json.dumps(lab.view("split"))
        for n in (3, 4):
            self.assertNotIn(debriefs.TEXT[n]["happened"], blob)
        self.assertNotIn(debriefs.CHALLENGES[3], blob)
        self.assertIsNone(site["final_challenge"])

    def test_final_challenge_after_last_level(self):
        """(the last level of Part 1: the challenge is about Part 1's code)"""
        lab = Lab()
        win(lab, PART1[-1])
        self.assertEqual(lab.view("site")["final_challenge"], debriefs.FINAL_CHALLENGE)



class TestDebriefContent(unittest.TestCase):
    def test_every_level_has_a_full_debrief(self):
        for n in ORDER:
            d = debriefs.debrief(n)
            for key in ("happened", "real_world", "fix", "partner_prompt"):
                self.assertTrue(d[key].strip(), (n, key))
            self.assertTrue(d["under_the_hood"], n)
            for snip in d["under_the_hood"]:
                self.assertTrue(snip["code"].strip(), n)

    def test_under_the_hood_comes_from_the_real_code(self):
        def code(n):
            return "\n".join(s["code"] for s in debriefs.debrief(n)["under_the_hood"])
        rule2 = LEVELS[2].system_prompt.split(". ")[0]       # "RULE: you may call ..."
        self.assertIn(" ".join(rule2.split()), " ".join(code(2).split()))
        self.assertIn("def keyword_filter(email):", code(3))
        for word in filters.BLOCKED_WORDS:
            self.assertIn(f'"{word}"', code(3))
        self.assertIn("def sender_must_be_staff", code(4))
        self.assertNotIn('"""', code(4))                     # docstrings trimmed

    def test_challenges_only_for_levels_2_to_4(self):
        self.assertIsNone(debriefs.debrief(1)["challenge"])
        for n in (2, 3, 4):
            self.assertTrue(debriefs.debrief(n)["challenge"])


class TestLevelText(unittest.TestCase):
    def test_every_level_has_a_defense_line(self):
        for n in ORDER:
            self.assertTrue(LEVELS[n].defense.strip())

    def test_level1_says_email_ronit(self):
        self.assertNotIn("Email Quokka", LEVELS[1].description)
        self.assertIn("emailing Ronit", LEVELS[1].description)

    def test_level4_hints_follow_the_two_stages(self):
        self.assertIn("[guard]", LEVELS[4].hints[0])           # stage 1: meet the code
        self.assertNotIn("form", LEVELS[4].hints[0])           # the form comes later
        self.assertIn("Read exactly what Ronit receives", LEVELS[4].hints[1])
        self.assertIn("looked like part of the form", LEVELS[4].hints[1])


class TestGuardWording(unittest.TestCase):
    def test_plain_string_guards_unchanged(self):
        """Level 4's guard returns a plain string: same text for both."""
        events = []
        ctx = agent.Ctx(level=LEVELS[4], email=agent.Email(story.ME, "s", "b"),
                        version="v5", emit=lambda k, t: events.append((k, t)))
        out = tools.run_tool(ctx, "set_release_notes", {"version": "v4"})
        self.assertEqual(out, "Error: [guard] REJECTED: real sender is "
                              "you@redteam.example, not staff")
        self.assertEqual(ctx.shown_results.get(out, out), out)
        self.assertIn(("guard", out[len("Error: "):]), events)


if __name__ == "__main__":
    unittest.main()
