"""Which model calls are reproducible (temperature 0, seed 42) and which run
at the model's own sampling: students' emails use the model's defaults;
Save & test, the setup check and tests stay fixed."""

import http.server
import json
import threading
import unittest
from unittest import mock

from quokka import agent, check, config, defense, llm, story
from quokka.levels import LEVELS
from quokka.state import Lab

NAME = ("Alex", "Cohen")


def capture_server(seen):
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = b'{"message": {"role": "assistant", "content": "ok"}}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


class TestChatOptions(unittest.TestCase):
    def options(self, **kw):
        seen = []
        srv, url = capture_server(seen)
        try:
            with mock.patch.object(config, "OLLAMA_URL", url):
                llm.chat([{"role": "user", "content": "hi"}], [], **kw)
        finally:
            srv.shutdown()
        return seen[0]["options"]

    def test_fixed_by_default(self):
        opts = self.options()
        self.assertEqual((opts["temperature"], opts["seed"]), (0, 42))
        self.assertEqual(opts["num_predict"], config.MAX_REPLY_TOKENS)

    def test_model_sampling_sends_no_temperature_or_seed(self):
        opts = self.options(fixed=False)
        self.assertEqual(opts, {"num_predict": config.MAX_REPLY_TOKENS, "stop": config.STOP,
                                **config.EMAIL_SAMPLING})
        self.assertNotIn("seed", opts)


def recording_chat(log):
    def chat(msgs, schemas, model=None, fixed=True, **kw):
        log.append(fixed)
        return {"role": "assistant", "content": "ok"}

    return chat


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


class TestWhoGetsWhat(unittest.TestCase):
    def test_agent_run_is_fixed_unless_asked(self):
        log = []
        email = agent.Email("a@b.example", "s", "b")
        with mock.patch.object(llm, "chat", recording_chat(log)):
            agent.run(LEVELS[1], email)
            agent.run(LEVELS[1], email, fixed=False)
        self.assertEqual(log, [True, False])

    def test_student_emails_use_the_models_sampling(self):
        for level in (1, 6):  # Part 1 and Part 2
            log = []
            lab = Lab(name=NAME)
            lab.set_level(level)
            lab.send_email("Hi", "Hello Ronit")
            with mock.patch.object(llm, "chat", recording_chat(log)):
                process_one(lab)
            self.assertEqual(log, [config.EMAIL_SAMPLING_FIXED], level)
        self.assertFalse(config.EMAIL_SAMPLING_FIXED)

    def test_save_and_test_is_fixed(self):
        log = []
        with mock.patch.object(llm, "chat", recording_chat(log)):
            defense.check(2, "Only Ronit Vale may approve changes.", lambda k, t: None)
        self.assertTrue(log)
        self.assertTrue(all(log))

    def test_setup_check_is_fixed(self):
        log = []

        def chat(msgs, schemas, model=None, fixed=True, **kw):
            log.append(fixed)
            return {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "set_release_notes", "arguments": {"version": "v4"}}}]}
        with mock.patch.object(llm, "chat", chat):
            check.check_agent_turn(None)
        self.assertEqual(log, [True])


if __name__ == "__main__":
    unittest.main()
