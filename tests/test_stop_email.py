"""The Stop this email button: Quokka abandons the email it is reading; what it
already did stands, and the next email goes ahead. No model needed.

Run:  python -m unittest discover tests
"""

import unittest
from unittest import mock

from quokka import agent, llm
from quokka.levels import LEVELS
from quokka.state import Lab


def tool(name, **args):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": name, "arguments": args}}],
    }


def email():
    return agent.Email("x@redteam.example", "Hi", "Please reply.")


class TestAgentStop(unittest.TestCase):
    def test_stop_before_any_call(self):
        notes = []
        chat = mock.Mock()
        with mock.patch.object(agent.llm, "chat", chat):
            ctx = agent.run(
                LEVELS[1], email(), emit=lambda k, t: notes.append(k), stop=lambda: True
            )
        self.assertTrue(ctx.stopped)
        chat.assert_not_called()
        self.assertNotIn("note", notes)  # the caller says why it stopped

    def test_cancel_mid_call_keeps_what_was_done(self):
        replies = [tool("reply", subject="Re: Hi", body="Hello.")]

        def chat(msgs, schemas, model=None, **kw):
            if replies:
                return replies.pop(0)
            raise llm.Cancelled()  # Stop pressed during the second call

        notes = []
        with mock.patch.object(agent.llm, "chat", chat):
            ctx = agent.run(LEVELS[1], email(), emit=lambda k, t: notes.append(k))
        self.assertTrue(ctx.stopped)
        self.assertEqual(len(ctx.outbox), 1)  # the email it already sent stands
        self.assertNotIn("note", notes)


class TestLabStopEmail(unittest.TestCase):
    def test_nothing_to_stop(self):
        lab = Lab()
        with mock.patch.object(llm, "cancel") as cancel:
            self.assertFalse(lab.stop_email())
        cancel.assert_not_called()

    def test_stops_the_email_being_read(self):
        lab = Lab()
        lab.ronit_inbox.append(
            {
                "id": 7,
                "from": "x@redteam.example",
                "subject": "Hi",
                "body": "...",
                "status": "reading",
            }
        )
        with mock.patch.object(llm, "cancel") as cancel:
            self.assertTrue(lab.stop_email())
        cancel.assert_called_once()
        self.assertEqual(lab.stop_mail, 7)


if __name__ == "__main__":
    unittest.main()
