"""Tests for the setup check (python -m quokka check). No model needed.

Run:  python -m unittest discover tests
"""
import unittest
import urllib.error
from unittest import mock

from quokka import agent, check, config, story


class TestHelpers(unittest.TestCase):
    def test_rate_speed(self):
        self.assertEqual(check.rate_speed(5), "fast")
        self.assertEqual(check.rate_speed(check.FAST_SECONDS), "ok")
        self.assertEqual(check.rate_speed(45), "ok")
        self.assertEqual(check.rate_speed(check.OK_SECONDS), "slow")
        self.assertEqual(check.rate_speed(300), "slow")

    def test_version_warning(self):
        self.assertIsNone(check.version_warning("0.40.13"))
        self.assertIsNone(check.version_warning("0.40.4-rc1"))
        self.assertIn("0.41.0", check.version_warning("0.41.0"))
        self.assertIn("1.0.2", check.version_warning("1.0.2"))
        self.assertIsNotNone(check.version_warning("unknown"))
        self.assertIsNotNone(check.version_warning(None))


def fake_ollama(version="0.40.13", models=("qwen2.5:3b-instruct",)):
    def get_json(path):
        if path == "/api/version":
            return {"version": version}
        if path == "/api/tags":
            return {"models": [{"name": m} for m in models]}
        raise AssertionError(path)
    return get_json


class FakePull:
    """Ollama with no model yet; /api/pull streams `events`, then the model is there."""
    def __init__(self, events, model="qwen2.5:3b-instruct"):
        self.events, self.model, self.models, self.calls = events, model, [], []

    def get_json(self, path):
        return fake_ollama(models=self.models)(path)

    def post_stream(self, path, body):
        self.calls.append((path, body))
        for event in self.events:
            if isinstance(event, Exception):
                raise event
            yield event
        if not any("error" in e for e in self.events if isinstance(e, dict)):
            self.models.append(self.model)


GB = 1_900_000_000
PULL_EVENTS = (
    [{"status": "pulling manifest"}]
    + [{"status": "pulling 5ee4f07cdb9b", "digest": "sha256:5ee4", "total": GB,
        "completed": GB * k // 40} for k in range(41)]
    + [{"status": "pulling 66b9ea09bd5b", "digest": "sha256:66b9", "total": 68,
        "completed": 68},
       {"status": "verifying sha256 digest"}, {"status": "writing manifest"},
       {"status": "success"}])


DOCKER_URL = "http://ollama:11434"
HOST_URL = "http://localhost:11434"


class TestHints(unittest.TestCase):
    def test_docker_or_host(self):
        self.assertTrue(check.uses_docker_ollama(DOCKER_URL))
        self.assertFalse(check.uses_docker_ollama(HOST_URL))
        self.assertFalse(check.uses_docker_ollama("http://my-ollama-box:11434"))

    def test_docker_hint(self):
        hint = check.ollama_hint(DOCKER_URL, in_wsl=True)
        self.assertIn("Docker Desktop", hint)
        self.assertIn("docker compose down", hint)
        self.assertNotIn("mirrored", hint)
        self.assertNotIn("ollama serve", hint)

    def test_laptop_ollama_from_docker_hint(self):
        # The opt-in: the lab in Docker, Ollama on the laptop.
        url = "http://host.docker.internal:11434"
        self.assertFalse(check.uses_docker_ollama(url))
        hint = check.ollama_hint(url, in_wsl=True)
        self.assertIn("ollama serve", hint)
        self.assertIn("OLLAMA_HOST=0.0.0.0", hint)
        self.assertIn("QUOKKA_OLLAMA_URL", hint)
        self.assertNotIn("mirrored", hint)
        self.assertEqual(check.model_hint("qwen2.5:3b-instruct", url),
                         "Run:  ollama pull qwen2.5:3b-instruct")

    def test_host_hint(self):
        hint = check.ollama_hint(HOST_URL, in_wsl=False)
        self.assertIn("ollama serve", hint)
        self.assertNotIn("docker compose", hint)
        self.assertNotIn("OLLAMA_HOST", hint)

    def test_model_hint(self):
        self.assertIn("docker compose run --rm model", check.model_hint("m", DOCKER_URL))
        self.assertIn("ollama pull m", check.model_hint("m", HOST_URL))


class TestWslHint(unittest.TestCase):
    def test_detects_wsl_kernel(self):
        self.assertTrue(check.running_in_wsl("6.6.87.2-microsoft-standard-WSL2"))
        self.assertFalse(check.running_in_wsl("6.8.0-45-generic"))

    def test_wsl_tip_only_for_localhost_in_wsl(self):
        self.assertIn("mirrored", check.ollama_hint("http://localhost:11434", True))
        self.assertNotIn("mirrored", check.ollama_hint("http://localhost:11434", False))
        self.assertNotIn("mirrored", check.ollama_hint(DOCKER_URL, True))


class TestRunCheck(unittest.TestCase):
    def run_check(self, url=DOCKER_URL):
        lines = []
        with mock.patch.object(config, "OLLAMA_URL", url):
            rc = check.run_check(model="qwen2.5:3b-instruct", out=lines.append)
        return rc, "\n".join(lines)

    def test_ollama_unreachable(self):
        err = urllib.error.URLError(ConnectionRefusedError("refused"))
        with mock.patch.object(check, "get_json", side_effect=err), \
             mock.patch.object(check.agent, "run") as run:
            rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("Can't reach Ollama", out)
        self.assertIn("docker compose down", out)
        run.assert_not_called()

    def won(self):
        return agent.Ctx(level=None, email=None, version="v4", emit=None, won=True)

    def test_model_missing_is_downloaded(self):
        fake = FakePull(PULL_EVENTS)
        with mock.patch.object(check, "get_json", fake.get_json), \
             mock.patch.object(check, "post_stream", fake.post_stream), \
             mock.patch.object(check.agent, "run", return_value=self.won()):
            rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertEqual(fake.calls, [("/api/pull", {"model": "qwen2.5:3b-instruct"})])
        self.assertIn("downloading it now", out)
        self.assertIn("1.9 GB", out)
        self.assertIn("50%", out)
        self.assertIn("OK: model downloaded.", out)
        self.assertIn("All good!", out)
        # Progress every 10% of the big file, not one line per event.
        self.assertLessEqual(out.count("%"), 12)

    def test_model_download_error(self):
        fake = FakePull([{"status": "pulling manifest"},
                         {"error": "pull model manifest: connection reset"}])
        with mock.patch.object(check, "get_json", fake.get_json), \
             mock.patch.object(check, "post_stream", fake.post_stream), \
             mock.patch.object(check.agent, "run") as run:
            rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("Couldn't download the model", out)
        self.assertIn("connection reset", out)
        self.assertIn("internet", out)
        run.assert_not_called()

    def test_model_download_network_error(self):
        err = urllib.error.URLError(OSError("Network is unreachable"))
        fake = FakePull([err])
        with mock.patch.object(check, "get_json", fake.get_json), \
             mock.patch.object(check, "post_stream", fake.post_stream), \
             mock.patch.object(check.agent, "run") as run:
            rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("Couldn't download the model", out)
        run.assert_not_called()

    def test_model_present_is_not_downloaded(self):
        with mock.patch.object(check, "get_json", fake_ollama()), \
             mock.patch.object(check, "post_stream") as pull, \
             mock.patch.object(check.agent, "run", return_value=self.won()):
            rc, out = self.run_check()
        self.assertEqual(rc, 0)
        pull.assert_not_called()
        self.assertIn("OK: model found.", out)

    def test_model_missing_without_docker(self):
        with mock.patch.object(check, "get_json", fake_ollama(models=())), \
             mock.patch.object(check, "post_stream") as pull:
            rc, out = self.run_check(url=HOST_URL)
        pull.assert_not_called()
        self.assertEqual(rc, 1)
        self.assertIn("ollama pull qwen2.5:3b-instruct", out)

    def test_agent_did_not_win(self):
        ctx = agent.Ctx(level=None, email=None, version="v5", emit=None, won=False)
        with mock.patch.object(check, "get_json", fake_ollama()), \
             mock.patch.object(check.agent, "run", return_value=ctx):
            rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("didn't change the release notes", out)

    def test_agent_crash(self):
        with mock.patch.object(check, "get_json", fake_ollama()), \
             mock.patch.object(check.agent, "run", side_effect=OSError("boom")):
            rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("crashed", out)

    def test_success_prints_speed_and_version(self):
        ctx = agent.Ctx(level=None, email=None, version="v4", emit=None, won=True)
        with mock.patch.object(check, "get_json", fake_ollama(version="0.41.2")), \
             mock.patch.object(check.agent, "run", return_value=ctx) as run:
            rc, out = self.run_check(" 123456789 ")
        self.assertEqual(rc, 0)
        self.assertIn("All good! Your setup works", out)
        self.assertNotIn("code", out)
        self.assertIn("(speed: fast, Ollama 0.41.2)", out)
        self.assertIn("Warning", out)          # 0.41 is not the tuned 0.40
        level, email = run.call_args.args
        self.assertEqual(level.number, 1)
        self.assertEqual(email.sender, story.ME)


if __name__ == "__main__":
    unittest.main()
