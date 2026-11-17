"""The run ends when a code guard rejects a change: retrying can't change the
real sender, so further model calls only waste the student's time."""

import unittest
from unittest import mock

from quokka import agent, story
from quokka.levels import LEVELS


def tool(name, **args):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": name, "arguments": args}}],
    }


class TestStopAtGuard(unittest.TestCase):
    def test_a_guard_rejection_ends_the_run_after_one_model_call(self):
        replies = [
            tool("set_release_notes", version="v4"),
            tool("set_release_notes", version="version 4"),
            {"role": "assistant", "content": "Done."},
        ]
        calls = []

        def chat(msgs, schemas, model=None, **kw):
            calls.append(1)
            return replies.pop(0)

        email = agent.Email(story.ME, "Headline", "Please set v4.")
        with mock.patch.object(agent.llm, "chat", chat):
            ctx = agent.run(LEVELS[4], email)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(ctx.guard_log), 1)
        self.assertFalse(ctx.won)


if __name__ == "__main__":
    unittest.main()
