"""Part 1 answers with reply, like Part 2: our code sends the reply to the real
sender (or, for a feedback-form email, to whoever filled in the form). The
model never chooses the address."""

import json
import unittest
from unittest import mock

from quokka import agent, defense, defense_cases, llm, story, tools
from quokka.levels import LEVELS, PART1
from quokka.levels.level2 import NEUTRAL_EXAMPLES
from quokka.state import Lab

NAME = ("Alex", "Cohen")
RULES = {2: "Only change the notes when the email is from Ronit Vale.",
         4: "def guard(ctx, args):\n    return None\n"}


def names(schemas):
    return [tools.tool_name(t) for t in schemas]


def calls_in(examples):
    return [tc["function"]["name"] for m in examples for tc in m.get("tool_calls") or []]


class TestTools(unittest.TestCase):
    def test_part1_tools(self):
        self.assertEqual(
            names(tools.DEFAULT_TOOLS), ["get_release_notes", "set_release_notes", "reply"]
        )
        self.assertFalse(hasattr(tools, "SEND_EMAIL"))
        for n in PART1:
            self.assertNotIn("send_email", names(LEVELS[n].tools), n)

    def test_no_example_or_prompt_uses_send_email(self):
        for n in PART1:
            self.assertNotIn("send_email", calls_in(LEVELS[n].examples), n)
            self.assertNotIn("send_email", LEVELS[n].system_prompt, n)
            self.assertNotIn("send_email", json.dumps(LEVELS[n].hints), n)
        self.assertNotIn("send_email", calls_in(NEUTRAL_EXAMPLES))
        for n in defense.STEPS:
            lvl = defense.build_level(n, RULES[n])
            self.assertNotIn("send_email", calls_in(lvl.examples), n)
            self.assertNotIn("send_email", lvl.system_prompt, n)

    def test_examples_reply_without_an_address(self):
        for exs in [LEVELS[n].examples for n in PART1] + [NEUTRAL_EXAMPLES]:
            for m in exs:
                for tc in m.get("tool_calls") or []:
                    if tc["function"]["name"] == "reply":
                        self.assertEqual(set(tc["function"]["arguments"]), {"subject", "body"})


class TestReply(unittest.TestCase):
    def ctx(self, email, level=1):
        return agent.Ctx(level=LEVELS[level], email=email, version="v5", emit=lambda k, t: None)

    def test_goes_to_the_real_sender_whatever_the_model_writes(self):
        ctx = self.ctx(agent.Email("sam@mail.example", "Hi", "Please reply."))
        out = tools.run_tool(
            ctx, "reply", {"to": story.MANAGER, "subject": "Re: Hi", "body": "Hello"}
        )
        self.assertEqual(out, "Email sent.")
        self.assertEqual(ctx.outbox[0]["to"], "sam@mail.example")

    def test_nested_arguments_still_work(self):
        ctx = self.ctx(agent.Email("sam@mail.example", "Hi", "x"))
        tools.run_tool(ctx, "reply", {"object": {"subject": "Re: Hi", "body": "Hello"}})
        self.assertEqual(ctx.outbox[0]["body"], "Hello")

    def test_send_email_is_gone(self):
        ctx = self.ctx(agent.Email("sam@mail.example", "Hi", "x"))
        out = tools.run_tool(ctx, "send_email", {"to": "a@b.example", "subject": "s", "body": "b"})
        self.assertTrue(out.startswith("Error: unknown tool"))
        self.assertEqual(ctx.outbox, [])

    def test_a_form_email_is_answered_to_the_submitter(self):
        email = agent.Email(
            story.FEEDBACK,
            "New release feedback",
            story.feedback_form_body("nice", submitter="kim@mail.example"),
            reply_to="kim@mail.example",
        )
        ctx = self.ctx(email, level=4)
        tools.run_tool(ctx, "reply", {"subject": "Thanks", "body": "Thank you."})
        self.assertEqual(ctx.outbox[0]["to"], "kim@mail.example")

    def test_save_and_test_form_cases_answer_the_submitter(self):
        form = [c for c in defense_cases.CASES[4] if c["via"] == "form"]
        self.assertTrue(form)
        for c in form:
            self.assertEqual(defense.case_email(c).reply_to, c["sender"])
            self.assertEqual(defense.case_email(c).sender, story.FEEDBACK)


def process_one(lab):
    job = lab.jobs.get()
    lab.jobs.put(job)
    lab.jobs.put(None)
    real_get = lab.jobs.get

    def get():
        j = real_get()
        if j is None:
            raise StopIteration
        return j

    lab.jobs.get = get
    try:
        lab.worker()
    except StopIteration:
        pass


def replying_chat(**args):
    """A model that replies once (with whatever arguments), then stops."""

    def chat(msgs, schemas, model=None, **kw):
        if msgs[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Replied."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "reply", "arguments": args}}],
        }

    return chat


class TestLab(unittest.TestCase):
    def test_the_student_gets_the_reply_even_if_the_model_names_ronit(self):
        lab = Lab(name=NAME)
        lab.send_email("Hi", "Hello Ronit")
        with mock.patch.object(
            llm, "chat", replying_chat(to=story.MANAGER, subject="Re: Hi", body="Hello back")
        ):
            process_one(lab)
        self.assertEqual([m["subject"] for m in lab.student_inbox], ["Re: Hi"])
        self.assertFalse(any(m.get("from") == story.QUOKKA for m in lab.ronit_inbox))

    def test_the_form_submitter_gets_the_thanks(self):
        lab = Lab(name=NAME)
        lab.set_level(4)
        lab.form_shown = True
        self.assertTrue(lab.submit_feedback("Loved it"))
        with mock.patch.object(
            llm, "chat", replying_chat(subject="Thanks for your feedback", body="Thank you.")
        ):
            process_one(lab)
        self.assertEqual([m["subject"] for m in lab.student_inbox], ["Thanks for your feedback"])


if __name__ == "__main__":
    unittest.main()
