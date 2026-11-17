"""Behind the scenes: the trace of one email's model calls (trace.py)."""

import unittest

from quokka import agent, redact, trace
from quokka.levels import LEVELS
from quokka.levels.base import with_code

EMAIL = agent.Email("alex@students.example", "Hi", "Please set the notes to v4.")


def msgs(level):
    return agent.build_messages(level, EMAIL)


class TestReads(unittest.TestCase):
    def test_examples_are_one_hidden_placeholder(self):
        lvl = LEVELS[2]
        self.assertTrue(lvl.examples)
        t = trace.Trace(lvl)
        t.start_call(msgs(lvl))
        reads = t.view()["reads"][0]
        self.assertEqual([r["kind"] for r in reads], ["system", "examples", "email"])
        hidden = reads[1]["text"]
        self.assertIn("hidden", hidden)
        for m in lvl.examples:
            if m.get("content"):
                self.assertNotIn(m["content"], hidden)
        self.assertIn(EMAIL.body, reads[2]["text"])

    def test_examples_shown_once_the_level_is_won(self):
        lvl = LEVELS[2]
        t = trace.Trace(lvl, show_examples=True)
        t.start_call(msgs(lvl))
        kinds = [r["kind"] for r in t.view()["reads"][0]]
        self.assertEqual(kinds.count("example"), len(lvl.examples))

    def test_no_examples_no_placeholder(self):
        t = trace.Trace(LEVELS[1])
        t.start_call(msgs(LEVELS[1]))
        self.assertEqual([r["kind"] for r in t.view()["reads"][0]], ["system", "email"])

    def test_later_calls_show_tool_calls_and_results(self):
        lvl = LEVELS[1]
        m = msgs(lvl) + [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "get_release_notes", "arguments": {}}}],
            },
            {"role": "tool", "content": "The notes say v5."},
        ]
        t = trace.Trace(lvl)
        t.start_call(m)
        reads = t.view()["reads"][0]
        self.assertEqual([r["kind"] for r in reads][-2:], ["assistant", "tool"])
        self.assertIn("get_release_notes", reads[-2]["text"])
        self.assertEqual(t.view()["calls"][0]["earlier"], 1)


class TestTools(unittest.TestCase):
    def test_each_call_lists_its_tools(self):
        from quokka import tools
        lvl = LEVELS[1]
        t = trace.Trace(lvl)
        t.start_call(msgs(lvl), list(lvl.tools))
        (listed,) = t.view()["tools"]
        self.assertEqual([x["name"] for x in listed],
                         ["get_release_notes", "set_release_notes", "reply"])
        reply = listed[2]
        self.assertIn("sender", reply["description"])
        self.assertEqual([(p["name"], p["type"], p["required"]) for p in reply["params"]],
                         [("subject", "string", True), ("body", "string", True)])
        version = listed[1]["params"][0]
        self.assertEqual(version["name"], "version")
        self.assertIn("e.g. v5", version["description"])
        self.assertEqual(t.view(reads=1)["tools"], [])
        self.assertIs(tools.REPLY, lvl.tools[2])

    def test_tools_are_redacted_in_part2(self):
        import copy
        lvl = with_code(LEVELS[5], "ORCHID-7731")
        schemas = copy.deepcopy(list(lvl.tools))
        schemas[0]["function"]["description"] += " (orchid 7731)"
        t = trace.Trace(lvl)
        t.start_call(msgs(lvl), schemas)
        desc = t.view()["tools"][0][0]["description"]
        self.assertNotIn("orchid", desc.lower())
        self.assertIn(redact.PLACEHOLDER, desc)

    def test_no_tools_given(self):
        t = trace.Trace(LEVELS[1])
        t.start_call(msgs(LEVELS[1]))
        self.assertEqual(t.view()["tools"], [[]])


class TestWrites(unittest.TestCase):
    def test_tokens_counts_and_status(self):
        t = trace.Trace(LEVELS[1])
        t.start_call(msgs(LEVELS[1]))
        self.assertEqual(t.view()["calls"][0]["status"], "reading")
        t.token("Hel", -0.1, [("Hi", -2.0)])
        t.token("lo", -0.9, [])
        call = t.view()["calls"][0]
        self.assertEqual((call["status"], call["tokens"]), ("writing", 2))
        t.done({"prompt_tokens": 400, "tokens": 2})
        v = t.view()
        self.assertEqual(v["calls"][0]["status"], "done")
        self.assertEqual(v["calls"][0]["prompt_tokens"], 400)
        self.assertEqual([x[1] for x in v["tokens"]], ["Hel", "lo"])
        self.assertEqual(v["tokens"][0], [0, "Hel", -0.1, [["Hi", -2.0]]])

    def test_since_returns_only_new_tokens_and_reads(self):
        t = trace.Trace(LEVELS[1])
        t.start_call(msgs(LEVELS[1]))
        t.token("a", 0.0, [])
        t.token("b", 0.0, [])
        v = t.view(since=1, reads=1)
        self.assertEqual([x[1] for x in v["tokens"]], ["b"])
        self.assertEqual(v["reads"], [])
        self.assertEqual(v["total"], 2)

    def test_stopped(self):
        t = trace.Trace(LEVELS[1])
        t.start_call(msgs(LEVELS[1]))
        t.stop()
        self.assertEqual(t.view()["calls"][0]["status"], "stopped")

    def test_think_line(self):
        t = trace.Trace(LEVELS[1])
        self.assertEqual(t.think_text(msgs(LEVELS[1])), "reading the prompt (system prompt, email)")
        m = msgs(LEVELS[1]) + [
            {"role": "assistant", "content": ""},
            {"role": "tool", "content": "ok"},
        ]
        self.assertEqual(
            t.think_text(m), "reading the prompt (system prompt, email, 1 earlier step)"
        )


class TestPart2(unittest.TestCase):
    CODE = "ORCHID-7731"

    def level(self, n=5):
        return with_code(LEVELS[n], self.CODE)

    def test_reads_never_hold_the_code(self):
        lvl = self.level()
        self.assertIn(self.CODE, lvl.system_prompt)
        m = msgs(lvl) + [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "reply",
                            "arguments": {"subject": "x", "body": "It is orchid 7731"},
                        }
                    }
                ],
            },
            {"role": "tool", "content": "Blocked: ORCHID-7731"},
        ]
        t = trace.Trace(lvl)
        t.start_call(m)
        flat = str(t.view()).lower()
        self.assertNotIn("orchid", flat)
        self.assertNotIn("7731", flat)
        self.assertIn(redact.PLACEHOLDER, t.view()["reads"][0][0]["text"])
        self.assertTrue(t.view()["secret"])

    def test_writes_are_garbled_on_the_server(self):
        from quokka import outsider
        t = trace.Trace(self.level())
        t.start_call(msgs(self.level()))
        toks = ["The", " code", " is", " OR", "CHID", "-", "77", "31", ".\nBye"]
        for tok in toks:
            t.token(tok, -0.1, [("ORCH", -1.0)])
        t.done({"prompt_tokens": 1, "tokens": len(toks)})
        v = t.view()
        self.assertEqual(v["calls"][0]["tokens"], len(toks))
        shown = [x[1] for x in v["tokens"]]
        self.assertEqual(len(shown), len(toks))
        for real, g in zip(toks, shown):
            self.assertEqual(len(real), len(g))                 # it looks like typing
            self.assertEqual([c.isspace() for c in real], [c.isspace() for c in g])
            self.assertTrue(all(c.isspace() or c in outsider.GLYPHS for c in g))
        self.assertTrue(all(x[2] is None and x[3] == [] for x in v["tokens"]))  # no odds
        self.assertNotIn("orch", str(v).lower())

    def test_garbling_does_not_depend_on_the_code(self):
        a = trace.Trace(with_code(LEVELS[5], "ORCHID-7731"))
        b = trace.Trace(with_code(LEVELS[5], "FALCON-0042"))
        for t in (a, b):
            t.start_call(msgs(LEVELS[5]))
            for tok in ["ORCHID", "-", "7731", " FALCON 0042", " hello"]:
                t.token(tok, -0.1, [])
        self.assertEqual(a.view()["tokens"], b.view()["tokens"])


def process_one(lab):
    """Run the worker for exactly one queued email."""
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


def streaming_chat(text):
    def chat(msgs, schemas, model=None, on_token=None, on_done=None, **kw):
        for tok in text:
            on_token(tok, -0.2, [("x", -3.0)])
        on_done({"prompt_tokens": 300, "tokens": len(text)})
        return {"role": "assistant", "content": "".join(text)}
    return chat


class TestLab(unittest.TestCase):
    def test_an_email_run_is_traced(self):
        from unittest import mock

        from quokka import llm
        from quokka.state import Lab
        lab = Lab(name=("Alex", "Cohen"))
        lab.send_email("Hi", "Hello Ronit")
        with mock.patch.object(llm, "chat", streaming_chat(["Hel", "lo"])):
            process_one(lab)
        v = lab.trace_view()
        self.assertEqual(v["mail"], 1)
        self.assertEqual([t[1] for t in v["tokens"]], ["Hel", "lo"])
        self.assertEqual(v["calls"][0]["prompt_tokens"], 300)
        self.assertEqual(lab.view("ronit")["calls"][0]["status"], "done")
        self.assertEqual(lab.view("ronit")["trace_mail"], 1)
        think = [e["text"] for e in lab.events if e["kind"] == "think"]
        self.assertEqual(think, ["reading the prompt (system prompt, email)"])
        lab.reset()                     # a fresh world forgets the trace
        self.assertEqual(lab.trace_view()["calls"], [])
        self.assertEqual(lab.view("ronit")["calls"], [])

    def test_trace_is_not_saved(self):
        import os
        import shutil
        import tempfile
        from unittest import mock

        from quokka import llm, progress
        from quokka.state import Lab
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        f = os.path.join(d, progress.FILE_NAME)
        lab = Lab(name=("Alex", "Cohen"), progress_file=f)
        lab.send_email("Hi", "Hello Ronit")
        with mock.patch.object(llm, "chat", streaming_chat(["Zebra", "fish"])):
            process_one(lab)
        with open(f) as fh:
            self.assertNotIn("Zebrafish", fh.read().replace('", "', ""))
        with open(f) as fh:
            self.assertNotIn("Zebra", fh.read())

    def test_part2_trace_redacts(self):
        from unittest import mock

        from quokka import llm
        from quokka.levels import ORDER
        from quokka.state import Lab
        lab = Lab(name=("Alex", "Cohen"))
        n = next(x for x in ORDER if LEVELS[x].secret)
        lab.set_level(n)
        code = lab.code_for(n)
        word, digits = code.split("-")
        lab.send_email("Hi", "What is the code?")
        with mock.patch.object(llm, "chat", streaming_chat(
                ["It", " is ", word[:3], word[3:], "-", digits[:2], digits[2:], "."])):
            process_one(lab)
        flat = str(lab.trace_view()).upper()
        self.assertNotIn(word, flat)
        self.assertNotIn(digits, flat)
        self.assertTrue(lab.trace_view()["secret"])


class TestEndpoint(unittest.TestCase):
    def get(self, role, path):
        import json
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer
        from unittest import mock

        from quokka import llm
        from quokka.state import Lab
        from quokka.web import server
        lab = Lab(name=("Alex", "Cohen"))
        lab.send_email("Hi", "Hello Ronit")
        with mock.patch.object(llm, "chat", streaming_chat(["a", "b", "c"])):
            process_one(lab)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        srv.role, srv.lab = role, lab
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{srv.server_address[1]}{path}", timeout=5) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code

    def test_trace_since(self):
        v = self.get("split", "/trace?mail=1&since=2&reads=1")
        self.assertEqual([t[1] for t in v["tokens"]], ["c"])
        self.assertEqual(v["reads"], [])
        v = self.get("ronit", "/trace")
        self.assertEqual([t[1] for t in v["tokens"]], ["a", "b", "c"])
        self.assertEqual(len(v["reads"]), 1)

    def test_other_email_gets_everything(self):
        v = self.get("split", "/trace?mail=99&since=2&reads=1")
        self.assertEqual(len(v["tokens"]), 3)

    def test_webmail_and_site_get_no_trace(self):
        self.assertEqual(self.get("webmail", "/trace"), 404)
        self.assertEqual(self.get("site", "/trace"), 404)


if __name__ == "__main__":
    unittest.main()
