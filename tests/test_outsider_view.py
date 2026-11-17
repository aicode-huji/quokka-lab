"""Part 2: the student is an outside attacker. Ronit's computer and the shell show
every step Quokka takes, but what Quokka writes is garbled; only replies that
reach the student's own inbox are readable. No model needed.

Run:  python -m unittest discover tests
"""

import json
import unittest

from quokka import outsider, story
from quokka.state import Lab

ME = "test.student@redteam.example"


def lab_with_run(level, code_in_text):
    """A lab on `level` after one run in which Quokka wrote `code_in_text`
    to Ronit and to the student, and in its closing note."""
    lab = Lab()
    lab.level = level
    lab.me = ME
    to_ronit = {
        "to": story.MANAGER,
        "subject": "Launch " + code_in_text,
        "body": "The code is " + code_in_text,
    }
    to_me = {"to": ME, "subject": "Re: hi", "body": "Here: " + code_in_text}
    for mail in (to_ronit, to_me):
        # reply (the Part 2 tool), and a tool the model made up (send_email)
        lab.events.append({"kind": "tool", "text": "reply(" + json.dumps(mail) + ")"})
        lab.events.append({"kind": "tool", "text": "send_email(" + json.dumps(mail) + ")"})
        lab.events.append({"kind": "result", "text": "Email sent."})
        lab.quokka_sent.append(dict(mail, **{"from": story.QUOKKA, "id": 1}))
    lab.events.append(
        {"kind": "guard", "text": "[guard] BLOCKED: the email contains the launch code"}
    )
    lab.events.append({"kind": "note", "text": "I told Ronit " + code_in_text})
    lab.events.append({"kind": "note", "text": "Stopped: the code check blocked the email."})
    lab.ronit_inbox.append(dict(to_ronit, **{"from": story.QUOKKA, "id": 2, "status": "done"}))
    lab.student_inbox.append(dict(to_me, **{"from": story.QUOKKA}))
    return lab


class TestGarble(unittest.TestCase):
    def test_keeps_shape_not_letters(self):
        g = outsider.garble("ORCHID-7731 now")
        self.assertEqual(len(g), len("ORCHID-7731 now"))
        self.assertEqual(g[11], " ")
        self.assertNotIn("ORCHID", g)
        self.assertNotIn("7731", g)
        # the same position gives the same glyph whatever the letter was
        self.assertEqual(outsider.garble("abc"), outsider.garble("xyz"))


class TestPart2View(unittest.TestCase):
    def test_ronit_and_shell_hide_what_quokka_writes(self):
        lab = lab_with_run(6, "ORCHID-7731")
        ronit = lab.view("split")["ronit"]
        text = json.dumps(ronit)
        self.assertNotIn("ORCHID", text)
        self.assertNotIn("7731", text)
        kinds = [e["kind"] for e in ronit["events"]]
        lines = [e["text"] for e in ronit["events"]]
        # every step is still there, with who each email went to
        self.assertEqual(lines.count(outsider.NOTICE_REPLY), 2)
        self.assertIn('"to": "' + story.MANAGER + '"', text)     # Ronit's inbox
        self.assertEqual(kinds.count("tool"), 4)
        self.assertTrue(any(t.startswith("send_email(") for t in lines))   # garbled
        self.assertIn("[guard] BLOCKED: the email contains the launch code", lines)
        self.assertIn("Stopped: the code check blocked the email.", lines)

    def test_a_reply_is_garbled_too(self):
        lab = lab_with_run(6, "ORCHID-7731")
        lab.events = [
            {"kind": "tool", "text": "reply(" + json.dumps({"subject": "Re: ORCHID",
                                                            "body": "It is ORCHID-7731"}) + ")"},
            {"kind": "result", "text": "Email sent."},
            {"kind": "tool", "text": "reply(not json ORCHID)"},
            {"kind": "tool", "text": "reply(" + json.dumps({"object": {"subject": "s",
                                                                       "body": "ORCHID"}}) + ")"},
        ]
        events = lab.view("split")["ronit"]["events"]
        text = json.dumps(events)
        self.assertNotIn("ORCHID", text)
        self.assertNotIn("7731", text)
        lines = [e["text"] for e in events]
        self.assertIn("Quokka is writing a reply to the sender (you can't read it here).", lines)
        self.assertEqual(sum(t.startswith("reply(") for t in lines), 3)
        self.assertIn('reply({"subject": "' + outsider.garble("s") + '", "body": "'
                      + outsider.garble("ORCHID") + '"})', lines)

    def test_stopped_by_you_stays_readable(self):
        lab = lab_with_run(6, "ORCHID-7731")
        line = "Stopped by you: Quokka didn't finish this email."
        lab.events.append({"kind": "note", "text": line})
        self.assertIn(line, [e["text"] for e in lab.view("split")["ronit"]["events"]])

    def test_the_send_line_hides_the_subject(self):
        lab = lab_with_run(6, "ORCHID-7731")
        lab.events.append(
            {
                "kind": "mail",
                "text": "Quokka sends an email to " + story.MANAGER + ": Launch ORCHID-7731",
            }
        )
        lines = [e["text"] for e in lab.view("split")["ronit"]["events"]]
        sent = [t for t in lines if t.startswith("Quokka sends an email to " + story.MANAGER)]
        self.assertEqual(len(sent), 1)
        self.assertNotIn("ORCHID", sent[0])

    def test_the_students_own_inbox_stays_readable(self):
        lab = lab_with_run(6, "ORCHID-7731")
        inbox = lab.view("split")["webmail"]["inbox"]
        self.assertIn("Here: ORCHID-7731", [m["body"] for m in inbox])

    def test_part1_shows_everything(self):
        lab = lab_with_run(2, "v4 please")
        text = json.dumps(lab.view("split")["ronit"])
        self.assertIn("The code is v4 please", text)
        self.assertNotIn("you can't read it", text)


if __name__ == "__main__":
    unittest.main()
