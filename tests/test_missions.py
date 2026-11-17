"""Tests for the mission strip's text (levels/missions.py). No model needed.

Run:  python -m unittest discover tests
"""

import unittest
from pathlib import Path

from quokka.levels import ORDER, PART2, missions
from quokka.levels.debriefs import LESSONS
from quokka.state import Lab


class TestMissionText(unittest.TestCase):
    def test_every_level_has_a_goal_and_one_paragraph(self):
        # One step only: what the student knows and what to do. The defend
        # banner and the debrief notes appear on their own after the win.
        for n in ORDER:
            m = missions.mission(n, form_shown=False)
            self.assertEqual(set(m), {"goal", "text", "tr", "labels"}, n)
            self.assertTrue(m["goal"], n)
            self.assertGreater(len(m["text"].split()), 25, n)

    def test_part1_goal_is_the_release_notes(self):
        m = missions.mission(1, form_shown=False)
        self.assertIn("v5", m["goal"])
        self.assertIn("v4", m["goal"])
        self.assertIn("Ronit", m["goal"])

    def test_part2_goal_is_the_launch_code(self):
        for n in PART2:
            self.assertIn("launch code", missions.mission(n, form_shown=False)["goal"])

    def test_level4_task_follows_the_two_stages(self):
        before = missions.mission(4, form_shown=False)["text"]
        after = missions.mission(4, form_shown=True)["text"]
        self.assertIn("[guard] REJECTED", before)
        self.assertNotIn("form", before)  # the form is a surprise
        self.assertIn("form", after)

    def test_no_lesson_is_given_away(self):
        # The lesson's name is shown only in the debrief, after the win.
        for n in ORDER:
            m = missions.mission(n, form_shown=True)
            text = " ".join(str(v) for v in m.values()).lower()
            lesson = LESSONS.get(n)
            if lesson:
                self.assertNotIn(str(lesson).lower(), text, n)


class TestMissionInView(unittest.TestCase):
    def test_site_view_carries_the_mission(self):
        lab = Lab()
        m = lab.view("site")["mission"]
        self.assertEqual(m, missions.mission(lab.level, form_shown=False))


class TestPart2Missions(unittest.TestCase):
    def test_merged_level_names_both_defenses(self):
        text = missions.mission(6, form_shown=False)["text"]
        self.assertIn("[REDACTED]", text)
        self.assertIn("[guard]", text)
        self.assertNotIn("keep the code secret", text)

    def test_last_level_may_not_break(self):
        self.assertIn("may not break", missions.mission(7, form_shown=False)["text"])


class TestMissionTranslations(unittest.TestCase):
    """The strip in Hebrew and Arabic: every English text has both."""

    LANGS = {"he": "\u0590-\u05ff", "ar": "\u0600-\u06ff"}
    # Names and on-screen words the translations keep in English, so students
    # can match them to the screen.
    KEEP = ("Quokka Labs", "Quokka", "Ronit", "Kestrel", "v4", "v5", "v6",
            "[guard]", "REJECTED", "[REDACTED]")

    def test_every_english_text_has_hebrew_and_arabic(self):
        self.assertEqual(set(missions.TRANSLATIONS), set(self.LANGS))
        for lang, letters in self.LANGS.items():
            t = missions.TRANSLATIONS[lang]
            self.assertEqual(set(t["texts"]), set(missions.TEXTS), lang)
            english = {"goal_part1": missions.GOAL_PART1, "goal_part2": missions.GOAL_PART2,
                       "text_4_form": missions.TEXT_4_FORM,
                       **{n: missions.TEXTS[n] for n in missions.TEXTS}}
            for key, en in english.items():
                tr = t["texts"][key] if isinstance(key, int) else t[key]
                self.assertRegex(tr, "[" + letters + "]", (lang, key))
                for word in self.KEEP:
                    if word in en:
                        self.assertIn(word, tr, (lang, key, word))

    def test_every_level_reaches_the_strip_in_all_three_languages(self):
        for n in ORDER:
            for shown in (False, True):
                m = missions.mission(n, form_shown=shown)
                self.assertEqual(set(m["tr"]), {"he", "ar"}, n)
                for lang, t in m["tr"].items():
                    self.assertEqual(set(t), {"goal", "text"}, (n, lang))
                    self.assertTrue(t["goal"] and t["text"], (n, lang))
                    self.assertNotEqual(t["text"], m["text"], (n, lang))
        # Level 4's text follows the form in every language
        before, after = (missions.mission(4, form_shown=f)["tr"] for f in (False, True))
        for lang in self.LANGS:
            self.assertNotEqual(before[lang]["text"], after[lang]["text"], lang)

    def test_labels_in_every_language(self):
        labels = missions.LABELS
        self.assertEqual(set(labels), {"en", "he", "ar"})
        for lang in ("he", "ar"):
            self.assertLessEqual(set(labels["en"]), set(labels[lang]), lang)
            self.assertNotIn("skip", labels[lang], lang)        # no Skip button any more
        # The Arabic is a machine translation nobody on staff reads: it says so.
        self.assertIn("AI translation", labels["ar"]["notice"])
        self.assertNotIn("notice", labels["he"])

    def test_site_view_carries_the_translations(self):
        m = Lab().view("site")["mission"]
        self.assertIn("he", m["tr"])
        self.assertIn("ar", m["tr"])
        self.assertEqual(m["labels"], missions.LABELS)

    def test_the_strip_has_the_switch(self):
        js = (Path(__file__).parent.parent / "quokka" / "web" / "common.js").read_text()
        for needle in ("'עברית'", "'العربية'", "MS_LANG_KEY", "dir = rtl ? 'rtl'", "<bdi"):
            self.assertIn(needle, js)


if __name__ == "__main__":
    unittest.main()
