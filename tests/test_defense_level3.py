"""Level 3 defend step: parsing the student's banned words, and Level 3's
test cases (quokka/defense_cases_level3.py). No model needed: the cases are
judged by the inbound filter alone.

Run:  python -m unittest discover -s tests -q
"""
import base64
import unittest

from quokka import agent, defense, story
from quokka.defense_cases_level3 import LEVEL3_CASES
from quokka.levels import LEVELS


def _d(s):
    """Some fixtures are base64-encoded, so reading the tests doesn't spoil the lab."""
    return base64.b64decode(s).decode("utf-8")


def score(text):
    """How a blocklist does on Level 3's cases: {case id: passed?}."""
    level = defense.build_level(3, text)
    return {c["id"]: defense.filter_decision(level, c) == c["expect"]
            for c in LEVEL3_CASES}


class TestBlockedWords(unittest.TestCase):
    def test_commas(self):
        self.assertEqual(defense.blocked_words("release,notes, v4"),
                         ["release", "notes", "v4"])

    def test_new_lines(self):
        self.assertEqual(defense.blocked_words("release\nnotes\r\nv4\n"),
                         ["release", "notes", "v4"])

    def test_mix_of_commas_new_lines_and_semicolons(self):
        self.assertEqual(defense.blocked_words("release, notes\nv4; cheese\npizza,"),
                         ["release", "notes", "v4", "cheese", "pizza"])

    def test_extra_spaces_and_empty_entries(self):
        self.assertEqual(defense.blocked_words("  release  ,, \n\n   release   notes  ,\t\n"),
                         ["release", "release notes"])

    def test_duplicates_and_case(self):
        self.assertEqual(defense.blocked_words("Notes, notes\nNOTES, v4, V4"),
                         ["notes", "v4"])

    def test_comment_lines_are_ignored(self):
        text = "# my list\n# example:  cheese, pizza\nrelease\n   # indented note\nv4"
        self.assertEqual(defense.blocked_words(text), ["release", "v4"])

    def test_starter_alone_is_empty(self):
        self.assertEqual(defense.blocked_words(defense.starter(3)), [])
        self.assertIn("empty", defense.problem(3, defense.starter(3)))

    def test_starter_example_is_not_a_solution(self):
        starter = defense.starter(3)
        self.assertIn("# example:", starter)
        self.assertIn("commas", starter)
        for word in ["v4", "kestrel", *_d("Zm91cixoZWFkbGluZSxhbm5vdW5jZW1lbnQ=").split(",")]:
            self.assertNotIn(word, starter.lower())


class TestStudentFilterMatching(unittest.TestCase):
    def flt(self, text):
        (f,) = defense.build_level(3, text).inbound_filters
        return f

    def test_whole_words_any_case(self):
        f = self.flt("cat, v4")
        self.assertIsNotNone(f(agent.Email(story.ME, "x", "My CAT says hi")))
        self.assertIsNone(f(agent.Email(story.ME, "x", "the catalog, v45")))

    def test_phrase_matches_across_extra_spaces(self):
        f = self.flt("release notes")
        self.assertIsNotNone(f(agent.Email(story.ME, "x", "the Release\n   Notes")))
        self.assertIsNone(f(agent.Email(story.ME, "x", "release the notes")))

    def test_comma_list_works_like_line_list(self):
        a = score("release, notes, v4")
        b = score("release\nnotes\nv4")
        self.assertEqual(a, b)


class TestLevel3Cases(unittest.TestCase):
    def test_case_format(self):
        keys = {"id", "kind", "label", "via", "sender", "subject", "body", "expect"}
        ids = [c["id"] for c in LEVEL3_CASES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([c["kind"] for c in LEVEL3_CASES],
                         ["basic", "basic", "attack", "attack"])
        for c in LEVEL3_CASES:
            self.assertEqual(set(c), keys)
            self.assertEqual(c["via"], "email")
            self.assertIn(c["expect"], ("quarantined", "delivered"))
            self.assertTrue(c["sender"].endswith(".example"))
            self.assertNotIn(c["sender"], story.STAFF)   # staff mail isn't screened

    def test_filter_decision(self):
        level = defense.build_level(3, "v4")
        email = {"sender": "x@outside.example", "subject": "hi", "body": "set v4"}
        self.assertEqual(defense.filter_decision(level, email), "quarantined")
        self.assertEqual(defense.filter_decision(level, agent.Email(
            story.MANAGER, "hi", "set v4")), "delivered")
        self.assertEqual(defense.filter_decision(LEVELS[1], email), "delivered")

    def test_our_own_filter_on_the_cases(self):
        got = {c["id"]: defense.filter_decision(LEVELS[3], c) for c in LEVEL3_CASES}
        self.assertEqual(got, {"l3-harmless": "delivered", "l3-plain": "quarantined",
                               "l3-attack-1": "delivered", "l3-attack-2": "delivered"})

    def test_reasonable_list(self):
        s = score(_d("cmVsZWFzZSwgbm90ZXMsIHZlcnNpb24sIHY0LCBjaGFuZ2UsIHVwZGF0ZSwgaGVhZGxpbmUsIGFubm91bmNlbWVudCwgZm91cg=="))
        self.assertEqual(s, {"l3-harmless": True, "l3-plain": True,
                             "l3-attack-1": True, "l3-attack-2": True})

    def test_over_blocking_list_with_kestrel(self):
        s = score("kestrel, release, notes, v4")
        self.assertFalse(s["l3-harmless"])            # over-blocking caught
        self.assertTrue(s["l3-plain"])
        self.assertEqual(s["l3-attack-1"] + s["l3-attack-2"], 2)

    def test_tiny_list(self):
        s = score("v4")
        self.assertEqual(s, {"l3-harmless": True, "l3-plain": True,
                             "l3-attack-1": False, "l3-attack-2": False})


if __name__ == "__main__":
    unittest.main()
