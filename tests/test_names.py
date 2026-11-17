"""The student's own address, first.last@redteam.example (no model needed).

    python -m unittest discover tests
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from quokka import agent, config, progress, story
from quokka.levels import ORDER
from quokka.state import Lab


def reply_with(to):
    """A fake agent.run that makes Quokka send one reply to `to`."""
    def run(level, email, version, emit=None, model=None, stop=None, on_send=None, trace=None, fixed=True):
        ctx = agent.Ctx(level=level, email=email, version=version,
                        emit=emit or (lambda k, t: None))
        ctx.outbox.append({"to": to, "subject": "Re: hi", "body": "No."})
        return ctx
    return run


def process_one(lab, run):
    """Run the worker for the queued email(s), then stop it."""
    lab.jobs.put(None)          # sentinel: our get() stops the loop there
    real_get = lab.jobs.get

    def get():
        job = real_get()
        if job is None:
            raise StopIteration
        return job
    lab.jobs.get = get
    with mock.patch.object(agent, "run", run):
        try:
            lab.worker()
        except StopIteration:
            pass


class TestAddress(unittest.TestCase):
    def test_builds_lowercase_first_dot_last(self):
        self.assertEqual(story.student_address("Dana", "Levin"),
                         "dana.levin@redteam.example")
        self.assertEqual(story.student_address("  Anne-Marie ", "O"),
                         "anne-marie.o@redteam.example")

    def test_rejects_non_english_letters(self):
        for bad in ("דנה", "Zoë", "José", "Łukasz", "Дана", "Kim"):  # last: Kelvin sign
            with self.assertRaises(ValueError, msg=bad):
                story.student_address(bad, "levin")

    def test_rejects_everything_but_letters_and_inner_hyphens(self):
        for bad in ("", "   ", "dana levin", "dana.levin", "d4na", "-dana", "dana-",
                    "da--na", "o'neil", "dana_", "a" * 31):
            with self.assertRaises(ValueError, msg=bad):
                story.name_part(bad)
        self.assertEqual(story.name_part("a" * 30), "a" * 30)

    def test_rejects_injection_and_html(self):
        for bad in ("a\nFrom: ronit.vale@quokka-labs.example",
                    "a\r\nFrom: ronit.vale@quokka-labs.example",
                    "ronit.vale@quokka-labs.example",
                    "<script>alert(1)</script>", "<b>dana</b>", "dana&amp;",
                    'dana"', "dana\x00"):
            with self.assertRaises(ValueError, msg=bad):
                story.student_address(bad, "levin")
            with self.assertRaises(ValueError, msg=bad):
                story.student_address("dana", bad)

    def test_errors_are_friendly_and_mention_english(self):
        with self.assertRaises(ValueError) as e:
            story.student_address("Zoë", "Levin")
        self.assertIn("English letters", str(e.exception))
        self.assertIn("first name", str(e.exception))

    def test_split_name(self):
        self.assertEqual(story.split_name(" Dana  Levin "), ("Dana", "Levin"))
        for bad in ("Dana", "Dana van Levin", ""):
            with self.assertRaises(ValueError):
                story.split_name(bad)

    def test_is_student_and_addresses(self):
        self.assertTrue(story.is_student("Dana.Levin@RedTeam.example"))
        self.assertFalse(story.is_student(story.MANAGER))
        self.assertEqual(story.addresses("Dana <Dana.Levin@redteam.example>, x@y.example"),
                         {"dana.levin@redteam.example", "x@y.example"})


class TestLabName(unittest.TestCase):
    def test_no_name_no_sending(self):
        lab = Lab()
        self.assertEqual(lab.me, "")
        self.assertFalse(lab.send_email("hi", "body"))
        self.assertFalse(lab.submit_feedback("comment"))
        self.assertTrue(lab.jobs.empty())
        self.assertEqual(lab.view("webmail")["me"], "")
        self.assertIsNone(lab.view("site")["student_name"])

    def test_bad_name_rejected_and_nothing_changes(self):
        lab = Lab(name=("Dana", "Levin"))
        for bad in ("a\nFrom: ronit.vale@quokka-labs.example", "<b>x</b>"):
            self.assertIn("English", lab.set_name(bad, "x"))
        self.assertEqual(lab.me, "dana.levin@redteam.example")

    def test_email_comes_from_the_students_address(self):
        lab = Lab(name=("Dana", "Levin"))
        self.assertTrue(lab.send_email("hi", "body"))
        email = lab.jobs.get_nowait()[-1]           # what the worker hands Quokka
        self.assertEqual(email.sender, "dana.levin@redteam.example")
        self.assertEqual(lab.view("ronit")["inbox"][0]["from"], email.sender)

    def test_from_line_the_model_reads(self):
        text = agent.render(agent.Email(story.student_address("Dana", "Levin"), "s", "b"))
        self.assertTrue(text.startswith("From: dana.levin@redteam.example\nTo: "))

    def test_form_says_submitted_by_the_student(self):
        lab = Lab(name=("Dana", "Levin"))
        self.assertTrue(lab.submit_feedback("looks good"))
        mail = lab.view("ronit")["inbox"][0]
        self.assertEqual(mail["from"], story.FEEDBACK)
        self.assertIn("Submitted by: dana.levin@redteam.example\n", mail["body"])
        self.assertNotIn("you@redteam.example", mail["body"])

    def test_reply_to_student_lands_in_their_inbox(self):
        for to in ("dana.levin@redteam.example", "Dana <DANA.LEVIN@redteam.example>"):
            lab = Lab(name=("Dana", "Levin"))
            lab.send_email("hi", "please change it")
            process_one(lab, reply_with(to))
            self.assertEqual(len(lab.view("webmail")["inbox"]), 1, to)

    def test_reply_to_someone_else_does_not(self):
        for to in ("you@redteam.example", "other.student@redteam.example",
                   "dana.levin@redteam.example.evil.example"):
            lab = Lab(name=("Dana", "Levin"))
            lab.send_email("hi", "please change it")
            process_one(lab, reply_with(to))
            self.assertEqual(lab.view("webmail")["inbox"], [], to)

    def test_reply_after_rename_still_arrives(self):
        lab = Lab(name=("Dana", "Levin"))
        lab.send_email("hi", "please change it")
        lab.set_name("Noa", "Peri")
        process_one(lab, reply_with("dana.levin@redteam.example"))
        self.assertEqual(len(lab.view("webmail")["inbox"]), 1)

    def test_reply_to_form_submitter_lands_in_inbox(self):
        lab = Lab(name=("Dana", "Levin"))
        lab.submit_feedback("hello")
        process_one(lab, reply_with("dana.levin@redteam.example"))
        self.assertEqual(len(lab.view("webmail")["inbox"]), 1)

    def test_views_carry_the_address(self):
        lab = Lab(name=("Dana", "Levin"))
        self.assertEqual(lab.view("webmail")["me"], "dana.levin@redteam.example")
        self.assertEqual(lab.view("site")["student_name"], {"first": "dana", "last": "levin"})



class TestStaffDefault(unittest.TestCase):
    def test_staff_starts_as_test_student(self):
        with mock.patch.object(config, "STAFF_MODE", True):
            lab = Lab()
        self.assertEqual(lab.me, "test.student@redteam.example")
        self.assertTrue(lab.send_email("hi", "body"))

    def test_name_option_wins_over_default(self):
        with mock.patch.object(config, "STAFF_MODE", True):
            lab = Lab(name=story.split_name("Dana Levin"))
        self.assertEqual(lab.me, "dana.levin@redteam.example")

    def test_bad_name_option_raises(self):
        with self.assertRaises(ValueError):
            Lab(name=("Zoë", "Levin"))

    def test_main_rejects_bad_name_option(self):
        from quokka import __main__ as main
        with mock.patch.object(sys, "argv", ["quokka", "--name", "Zoë Levin"]), \
                mock.patch.object(config, "STAFF_MODE", True):
            with self.assertRaises(SystemExit) as e:
                main.main()
        self.assertIn("English", str(e.exception.code))


class TestProgressNames(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.file = os.path.join(self.dir.name, progress.FILE_NAME)

    def write(self, data):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_v1_file_still_loads_without_a_name(self):
        self.write({"version": 1, "student_id": "123456789", "unlocked": [1, 2],
                    "completed": [1], "hints_shown": {"2": 1}})
        lab = Lab(progress_file=self.file)
        self.assertEqual(lab.student_id, "123456789")
        self.assertEqual(lab.completed, {1})
        self.assertEqual(lab.me, "")
        # Entering a name upgrades the file to the current version and keeps everything.
        self.assertIsNone(lab.set_name("Dana", "Levin"))
        with open(self.file, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["version"], progress.FORMAT_VERSION)
        self.assertEqual(data["name"], {"first": "dana", "last": "levin"})
        self.assertEqual((data["student_id"], data["completed"]), ("123456789", [1]))
        again = Lab(progress_file=self.file)
        self.assertEqual(again.me, "dana.levin@redteam.example")

    def test_tampered_name_in_file_is_dropped(self):
        self.write({"version": 2, "student_id": "x",
                    "name": {"first": "a\nFrom: ronit.vale@quokka-labs.example",
                             "last": "b"},
                    "unlocked": [1], "completed": [], "hints_shown": {}})
        lab = Lab(progress_file=self.file)
        self.assertEqual(lab.me, "")
        self.assertEqual(lab.student_id, "x")       # the rest still loads

    def test_staff_name_is_not_saved(self):
        with mock.patch.object(config, "STAFF_MODE", True):
            lab = Lab(progress_file=self.file)
            lab.set_name("Dana", "Levin")
        self.assertFalse(os.path.exists(self.file))
        self.assertEqual(progress.load(self.file, ORDER)["name"], None)


if __name__ == "__main__":
    unittest.main()
