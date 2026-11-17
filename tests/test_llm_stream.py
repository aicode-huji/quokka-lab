"""llm.chat with a token callback: it streams, with logprobs, and returns the
same message as without one (Behind the scenes)."""

import http.server
import json
import threading
import time
import unittest
from unittest import mock

from quokka import config, llm


def chunk(tokens=(), content="", tool_calls=None, done=False, **extra):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    d = {"message": msg, "done": done, **extra}
    if tokens:
        d["logprobs"] = [
            {
                "token": t,
                "logprob": lp,
                "top_logprobs": [{"token": t, "logprob": lp}, {"token": "x", "logprob": -5.0}],
            }
            for t, lp in tokens
        ]
    return d


TOOL = [
    {
        "id": "call_1",
        "function": {"index": 0, "name": "set_release_notes", "arguments": {"version": "v4"}},
    }
]
CHUNKS = [
    chunk([("<tool_call>", -0.01)]),
    chunk([('{"name": "set_release_notes", "arguments": {"version": "v4"}}', -0.2)]),
    chunk([("</tool_call>", -0.003)], tool_calls=TOOL),
    chunk(done=True, prompt_eval_count=402, eval_count=22),
]
TEXT_CHUNKS = [
    chunk([("Hel", -0.1)], content="Hel"),
    chunk([("lo", -1.5)], content="lo"),
    chunk(done=True, prompt_eval_count=10, eval_count=2),
]


def serve(chunks, seen, slow=0):
    class Fake(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            seen.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for c in chunks:
                line = (json.dumps(c) + "\n").encode()
                self.wfile.write(b"%x\r\n%s\r\n" % (len(line), line))
                self.wfile.flush()
                time.sleep(slow)
            self.wfile.write(b"0\r\n\r\n")

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class TestStream(unittest.TestCase):
    def call(self, chunks, **kw):
        seen, got, done = {}, [], []
        server, url = serve(chunks, seen)
        try:
            with mock.patch.object(config, "OLLAMA_URL", url):
                msg = llm.chat(
                    [{"role": "user", "content": "hi"}],
                    [],
                    on_token=lambda *a: got.append(a),
                    on_done=done.append,
                    **kw,
                )
        finally:
            server.shutdown()
        return msg, seen, got, done

    def test_asks_for_a_stream_with_logprobs(self):
        _, seen, _, _ = self.call(TEXT_CHUNKS)
        self.assertTrue(seen["stream"])
        self.assertTrue(seen["logprobs"])
        self.assertEqual(seen["top_logprobs"], llm.TOP_ALTERNATIVES)
        self.assertEqual(seen["options"]["seed"], config.SEED)

    def test_text_reply(self):
        msg, _, got, done = self.call(TEXT_CHUNKS)
        self.assertEqual(msg, {"role": "assistant", "content": "Hello"})
        self.assertEqual(got, [("Hel", -0.1, [("x", -5.0)]), ("lo", -1.5, [("x", -5.0)])])
        self.assertEqual(done, [{"prompt_tokens": 10, "tokens": 2}])

    def test_tool_call_reply_and_its_tokens(self):
        msg, _, got, _ = self.call(CHUNKS)
        self.assertEqual(msg, {"role": "assistant", "content": "", "tool_calls": TOOL})
        self.assertEqual(got[0][0], "<tool_call>")
        self.assertIn("set_release_notes", "".join(g[0] for g in got))

    def test_without_a_callback_nothing_changes(self):
        seen = {}

        class Plain(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen.update(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = b'{"message": {"role": "assistant", "content": "ok"}}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Plain)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}"
        with mock.patch.object(config, "OLLAMA_URL", url):
            msg = llm.chat([{"role": "user", "content": "hi"}], [])
        server.shutdown()
        self.assertEqual(msg, {"role": "assistant", "content": "ok"})
        self.assertFalse(seen["stream"])
        self.assertNotIn("logprobs", seen)

    def test_cancel_ends_a_stream(self):
        seen, caught = {}, []
        server, url = serve(TEXT_CHUNKS[:2] * 20, seen, slow=0.2)

        def run():
            try:
                llm.chat([{"role": "user", "content": "hi"}], [], on_token=lambda *a: None)
            except llm.Cancelled as e:
                caught.append(e)

        with mock.patch.object(config, "OLLAMA_URL", url):
            t = threading.Thread(target=run)
            t0 = time.time()
            t.start()
            time.sleep(0.5)
            llm.cancel()
            t.join(3)
        server.shutdown()
        self.assertEqual(len(caught), 1)
        self.assertLess(time.time() - t0, 2.5)


if __name__ == "__main__":
    unittest.main()
