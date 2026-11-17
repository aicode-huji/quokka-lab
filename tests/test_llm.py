"""The Ollama client: a request in flight can be cancelled (Save & test's Stop)."""
import http.server
import threading
import time
import unittest
from unittest import mock

from quokka import config, llm


class SlowOllama(http.server.BaseHTTPRequestHandler):
    def do_POST(self):          # never answers in time: like a model still reading
        self.rfile.read(int(self.headers["Content-Length"]))
        time.sleep(5)

    def log_message(self, *a):
        pass


class TestCancel(unittest.TestCase):
    def test_cancel_ends_the_request_in_flight(self):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SlowOllama)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}"
        caught = []

        def call():
            try:
                llm.chat([{"role": "user", "content": "hi"}], [])
            except llm.Cancelled as e:
                caught.append(e)
        with mock.patch.object(config, "OLLAMA_URL", url):
            t = threading.Thread(target=call)
            t0 = time.time()
            t.start()
            time.sleep(0.3)
            llm.cancel()
            t.join(3)
        server.shutdown()
        self.assertEqual(len(caught), 1)
        self.assertLess(time.time() - t0, 2)

    def test_cancel_with_nothing_in_flight_is_harmless(self):
        llm.cancel()


class TestReplyCap(unittest.TestCase):
    def test_every_request_caps_the_reply_length(self):
        seen = {}

        class Capture(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                import json as _json
                seen.update(_json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = b'{"message": {"role": "assistant", "content": "ok"}}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Capture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}"
        with mock.patch.object(config, "OLLAMA_URL", url):
            llm.chat([{"role": "user", "content": "hi"}], [])
        server.shutdown()
        self.assertEqual(seen["options"]["num_predict"], config.MAX_REPLY_TOKENS)
