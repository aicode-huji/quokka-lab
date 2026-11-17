"""Part 2: the launch code never shows in what the console says the model read
(redact.py). Only whole matches are masked, and every mask is the same."""

import unittest

from quokka import redact

CODE = "ORCHID-7731"
M = redact.PLACEHOLDER


class TestReads(unittest.TestCase):
    def test_every_form_of_the_code_is_replaced(self):
        for text in ("ORCHID-7731", "orchid-7731", "Orchid 7731", "ORCHID7731",
                     "orchid_7731", "ORCHID - 7731"):
            with self.subTest(text=text):
                self.assertEqual(redact.text(f"The code is {text}.", CODE), f"The code is {M}.")

    def test_the_parts_alone_are_replaced(self):
        out = redact.text("word: orchid, digits: 7731", CODE)
        self.assertEqual(out, f"word: {M}, digits: {M}")

    def test_masks_look_the_same(self):
        out = redact.text("a ORCHID b 7731 c orchid-7731", CODE)
        self.assertEqual(out, f"a {M} b {M} c {M}")

    def test_no_code_no_change(self):
        self.assertEqual(redact.text("ORCHID-7731", ""), "ORCHID-7731")
        self.assertEqual(redact.text("ORCHID-7731", None), "ORCHID-7731")

    def test_derived_from_the_code_not_hard_coded(self):
        out = redact.text("falcon 0042 and orchid", "FALCON-0042")
        self.assertEqual(out, f"{M} and orchid")

    def test_a_part_inside_a_longer_word_or_number_is_left_alone(self):
        self.assertEqual(redact.text("I remember the embers of 12345 and 01234", "EMBER-1234"),
                         "I remember the embers of 12345 and 01234")

    def test_the_marker_is_not_a_word_the_model_might_write(self):
        # Level 6's own instructions say "[REDACTED]": the page must tell them apart.
        self.assertNotIn(M, "[REDACTED] REDACTED launch code")
        self.assertEqual(len(M), 1)

    def test_ordinary_text_with_every_letter_and_digit_of_the_code_is_unmarked(self):
        # Regression: an "s" in ordinary words was shown as hidden, which told
        # the student the code had an "s" in it.
        for code in ("SAFFRON-1234", "ORCHID-7731", "EMBER-0042"):
            chars = sorted(set(code.replace("-", "")))
            words = " ".join(f"x{c.lower()}y {c}a{c}{c} {c}" for c in chars)
            text = f"Hi, this is {words} and some more text, sir. 12 34 7 731 00 42 0."
            with self.subTest(code=code):
                self.assertEqual(redact.text(text, code), text)


if __name__ == "__main__":
    unittest.main()
