"""The warm-up: the model reads the next email's prompt ahead of time, in the
background, silently, and never delays real work (llm.warm, Lab._maybe_warm)."""

import contextlib
import http.server
import io
import json
import threading
import time
import unittest
from unittest import mock

from quokka import config, llm
from quokka.state import Lab

NAME = ("Alex", "Cohen")


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


class TestTriggers(unittest.TestCase):
    def setUp(self):
        self.calls = []
        patcher = mock.patch.object(llm, "warm", lambda m, t, model=None: self.calls.append((m, t)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_off_unless_asked(self):
        lab = Lab(name=NAME)
        lab.set_level(2)
        self.assertEqual(self.calls, [])

    def test_lab_start_and_a_level_switch(self):
        lab = Lab(name=NAME, warm=True)
        self.assertEqual(len(self.calls), 1)  # lab start: Level 1
        lab.set_level(2)
        self.assertEqual(len(self.calls), 2)
        self.assertIn("RULE: only Ronit Vale", self.calls[-1][0][0]["content"])

    def test_same_prefix_is_not_warmed_twice(self):
        lab = Lab(name=NAME, warm=True)
        lab.reset()  # same level: same prefix
        lab.set_level(1)
        self.assertEqual(len(self.calls), 1)
        lab.set_level(3)  # Level 3 reads Level 1's prompt
        self.assertEqual(len(self.calls), 1)
        lab.set_level(2)
        lab.set_level(1)  # back: the model read Level 2 since
        self.assertEqual(len(self.calls), 3)

    def test_part2_and_defend_mode(self):
        lab = Lab(name=NAME, warm=True)
        lab.set_level(6)
        self.assertIn(lab.code_for(6), self.calls[-1][0][0]["content"])
        lab.set_level(2)
        lab.defenses[2] = {
            "versions": [{"text": "Only Ronit may approve it.", "saved_at": "t", "hash": "x"}],
            "check": None,
            "tested": True,
        }
        n = len(self.calls)
        self.assertTrue(lab.set_mode("mine"))
        self.assertEqual(len(self.calls), n + 1)
        self.assertIn("Only Ronit may approve it.", self.calls[-1][0][0]["content"])

    def test_not_while_busy(self):
        lab = Lab(name=NAME, warm=True)
        lab.send_email("Hi", "Hello")  # queued, not yet read
        n = len(self.calls)
        lab.set_level(2)  # (the queued email is dropped by the switch, but still queued)
        self.assertEqual(len(self.calls), n)

    def test_the_worker_warms_up_when_idle_again(self):
        lab = Lab(name=NAME, warm=True)
        lab.send_email("Hi", "Hello")
        lab.set_level(2)
        n = len(self.calls)
        real_get = lab.jobs.get

        def get():                  # one job, then stop where the worker would wait
            if lab.jobs.empty():
                raise StopIteration
            return real_get()
        lab.jobs.get = get
        with mock.patch.object(llm, "chat"), self.assertRaises(StopIteration):
            lab.worker()            # drops the stale email; idle again: warms up
        self.assertEqual(len(self.calls), n + 1)

    def test_same_prefix_and_tools_as_the_real_call(self):
        lab = Lab(name=NAME, warm=True)
        lab.set_level(2)
        warm_msgs, warm_tools = self.calls[-1]
        seen = []

        def chat(msgs, schemas, model=None, **kw):
            seen.append((json.loads(json.dumps(msgs)), schemas))
            return {"role": "assistant", "content": "ok"}

        lab.send_email("Release notes", "Please set v4")
        with mock.patch.object(llm, "chat", chat):
            process_one(lab)
        real_msgs, real_tools = seen[0]
        self.assertEqual(warm_msgs[:-1], real_msgs[:-1])
        self.assertEqual(warm_tools, real_tools)
        # the placeholder email shares the start of the real one
        self.assertTrue(
            real_msgs[-1]["content"].startswith(warm_msgs[-1]["content"].split("Subject:")[0])
        )

    def test_nothing_shows(self):
        lab = Lab(name=NAME, warm=True)
        lab.set_level(6)
        self.assertEqual(lab.events, [])
        self.assertIsNone(lab.trace)
        self.assertEqual(lab.log, [])


class Slow(http.server.BaseHTTPRequestHandler):
    """Answers a real request at once; a warm-up (num_predict WARM_TOKENS) hangs."""

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if req["options"].get("num_predict") == config.WARM_TOKENS:
            time.sleep(5)
        body = b'{"message": {"role": "assistant", "content": "ok"}}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class TestLlmWarm(unittest.TestCase):
    def serve(self):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Slow)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    def test_a_real_call_cancels_the_warm_up_and_does_not_wait(self):
        url = self.serve()
        with mock.patch.object(config, "OLLAMA_URL", url):
            t = llm.warm([{"role": "user", "content": "x"}], [])
            time.sleep(0.3)  # the warm-up is in flight
            t0 = time.time()
            msg = llm.chat([{"role": "user", "content": "hi"}], [])
            self.assertLess(time.time() - t0, 1.5)
            self.assertEqual(msg["content"], "ok")
            t.join(2)
            self.assertFalse(t.is_alive())  # cancelled, not left running

    def test_a_newer_warm_up_replaces_an_older_one(self):
        url = self.serve()
        with mock.patch.object(config, "OLLAMA_URL", url):
            t1 = llm.warm([{"role": "user", "content": "x"}], [])
            time.sleep(0.3)
            t2 = llm.warm([{"role": "user", "content": "y"}], [])
            t1.join(2)
            self.assertFalse(t1.is_alive())
            llm.cancel_warm()
            t2.join(2)

    def test_a_failed_warm_up_is_silent(self):
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(config, "OLLAMA_URL", "http://127.0.0.1:9"),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            llm.warm([{"role": "user", "content": "x"}], []).join(5)
        self.assertEqual((out.getvalue(), err.getvalue()), ("", ""))


if __name__ == "__main__":
    unittest.main()
