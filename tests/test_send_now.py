"""An email Quokka sends reaches its inbox the moment the send tool sends it,
not when the whole run ends; one sent before a crash or a Stop still arrives.
A run that crashes is marked "failed", one stopped by the student "stopped".
No model needed.

Run:  python -m unittest discover tests
"""

import unittest
from unittest import mock

from quokka import agent, story, tools
from quokka.state import Lab

NAME = ("Dana", "Levin")


def process_one(lab):
    """Run the worker for exactly the queued emails, then stop."""
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


def sending_run(then):
    """A stand-in run: Quokka emails the student, then `then(lab_inbox)` runs
    (still inside the run) and may raise or stop."""

    def run(level, email, start, emit=None, model=None, stop=None, on_send=None, trace=None, fixed=True):
        ctx = agent.Ctx(
            level=level,
            email=email,
            version=start,
            emit=emit or (lambda k, t: None),
            on_send=on_send,
        )
        tools.run_tool(
            ctx, "reply", {"subject": "Re: hi", "body": "Hello"}
        )
        then(ctx)
        return ctx

    return run


class TestSendNow(unittest.TestCase):
    def setUp(self):
        self.lab = Lab(name=NAME)
        self.lab.send_email("hi", "please")

    def test_delivered_while_the_run_is_still_going(self):
        seen = []

        def then(ctx):
            seen.append([m["subject"] for m in self.lab.student_inbox])

        with mock.patch.object(agent, "run", sending_run(then)):
            process_one(self.lab)
        self.assertEqual(seen, [["Re: hi"]])
        # delivered once, not again when the run ends
        self.assertEqual(len(self.lab.student_inbox), 1)
        self.assertEqual(len(self.lab.quokka_sent), 1)
        self.assertEqual(self.lab.ronit_inbox[0]["status"], "done")

    def test_a_crash_after_a_send_keeps_the_email(self):
        def then(ctx):
            raise RuntimeError("timed out")

        with mock.patch.object(agent, "run", sending_run(then)):
            process_one(self.lab)
        self.assertEqual([m["subject"] for m in self.lab.student_inbox], ["Re: hi"])
        self.assertEqual(self.lab.ronit_inbox[0]["status"], "failed")
        errors = [e["text"] for e in self.lab.events if e["kind"] == "error"]
        self.assertIn("not your email", errors[0])

    def test_a_stopped_email_is_marked_stopped(self):
        def then(ctx):
            ctx.stopped = True

        with mock.patch.object(agent, "run", sending_run(then)):
            process_one(self.lab)
        self.assertEqual(self.lab.ronit_inbox[0]["status"], "stopped")
        lab_lines = [e["text"] for e in self.lab.events if e["kind"] == "lab"]
        self.assertTrue(lab_lines[0].startswith("Stopped by you"))
        self.assertEqual(story.QUOKKA, self.lab.student_inbox[0]["from"])


if __name__ == "__main__":
    unittest.main()
