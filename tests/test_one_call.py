"""Quokka runs only the first tool call of each model message; the model sees
its result before it decides the next step (no calls planned ahead on made-up
results). Retries across model calls still work.  Run:
    python -m unittest discover tests
"""
import unittest
from unittest import mock

from quokka import agent, llm, story
from quokka.levels import LEVELS


def msg(*calls):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": n, "arguments": a}} for n, a in calls]}


class TestOneCallPerMessage(unittest.TestCase):
    def email(self):
        return agent.Email(story.ME, "Kestrel", "Please set it to v4.")

    def test_only_the_first_call_of_a_message_runs(self):
        replies = iter([
            msg(("get_release_notes", {}), ("set_release_notes", {"version": "v3"}),
                ("reply", {"subject": "Re", "body": "x"})),
            {"role": "assistant", "content": "Done."},
        ])
        with mock.patch.object(llm, "chat", lambda *a, **k: next(replies)):
            ctx = agent.run(LEVELS[1], self.email())
        self.assertEqual(ctx.calls, ['get_release_notes({})'])
        self.assertEqual(ctx.version, story.START_VERSION)

    def test_history_keeps_only_the_call_that_ran(self):
        seen = []
        replies = iter([msg(("get_release_notes", {}), ("reply", {"subject": "a", "body": "b"})),
                        {"role": "assistant", "content": "Done."}])

        def chat(msgs, schemas, **k):
            seen.append([dict(m) for m in msgs])
            return next(replies)
        with mock.patch.object(llm, "chat", chat):
            agent.run(LEVELS[1], self.email())
        assistant = [m for m in seen[1] if m["role"] == "assistant" and m.get("tool_calls")]
        self.assertEqual(len(assistant[-1]["tool_calls"]), 1)

    def test_a_retry_in_the_next_model_call_still_wins(self):
        replies = iter([msg(("set_release_notes", {"version": "four"})),
                        msg(("set_release_notes", {"version": "v4"}))])
        with mock.patch.object(llm, "chat", lambda *a, **k: next(replies)):
            ctx = agent.run(LEVELS[1], self.email())
        self.assertTrue(ctx.won)
        self.assertEqual(len(ctx.calls), 2)


if __name__ == "__main__":
    unittest.main()
