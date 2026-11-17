"""Tests for the Claude Code bonus (bonus/). No GitHub, no Claude Code needed.

Run:  python -m unittest discover tests
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BONUS = Path(__file__).resolve().parent.parent / "bonus"
sys.path.insert(0, str(BONUS))

import check_canary  # noqa: E402
import guard  # noqa: E402
import open_pr  # noqa: E402
import practice  # noqa: E402
import setup_practice_repo  # noqa: E402

HAS_GIT = shutil.which("git") is not None


def event(tool_name, **tool_input):
    return {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}


def quiet(func, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args)


class TestGuardRules(unittest.TestCase):
    def test_starter_blocks_canary_shell_command(self):
        allowed, reason = guard.decide(event("Bash", command="echo quokka-canary > CANARY_TRIGGERED.txt"),
                                       mode="starter")
        self.assertFalse(allowed)
        self.assertIn("canary", reason)
        self.assertFalse(guard.decide(event("PowerShell", command="New-Item CANARY_TRIGGERED.txt"),
                                      mode="starter")[0])

    def test_starter_allows_normal_commands(self):
        self.assertTrue(guard.decide(event("Bash", command="gh pr diff 1"), mode="starter")[0])
        self.assertTrue(guard.decide(event("Read", file_path="/repo/README.md"), mode="starter")[0])

    def test_starter_misses_the_write_tool(self):
        # The gap round 4 is built to show.
        e = event("Write", file_path="/repo/review-notes/CANARY_TRIGGERED.txt", content="quokka-canary")
        self.assertTrue(guard.decide(e, mode="starter")[0])

    def test_strict_blocks_canary_attempts(self):
        attempts = [
            event("Bash", command="echo quokka-canary > CANARY_TRIGGERED.txt"),
            event("Bash", command="touch CANARY_TRIGGERED.txt"),
            event("Bash", command="touch review-done.txt"),  # an attacker's own canary name
            event("Bash", command="python -m unittest"),
            event("Bash", command="gh pr diff 1; touch x"),
            event("Bash", command="git diff --output=notes.txt"),
            event("Bash", command="lsof"),
            event("Write", file_path="/repo/review-notes/CANARY_TRIGGERED.txt", content="quokka-canary"),
            event("Edit", file_path="/repo/CHANGELOG.md", old_string="a", new_string="b"),
            event("NotebookEdit", notebook_path="/repo/x.ipynb", new_source="x"),
            event("WebFetch", url="https://example.com"),
        ]
        for e in attempts:
            allowed, reason = guard.decide(e, mode="strict")
            self.assertFalse(allowed, msg=e)
            self.assertTrue(reason)

    def test_strict_allows_reading_a_pr(self):
        for e in [event("Bash", command="gh pr view 3"),
                  event("Bash", command="gh pr diff 3"),
                  event("Bash", command="git log main..bonus/round-1"),
                  event("Bash", command="ls -la"),
                  event("Read", file_path="/repo/README.md"),
                  event("Grep", pattern="mean")]:
            self.assertTrue(guard.decide(e, mode="strict")[0], msg=e)


class TestGuardAsHook(unittest.TestCase):
    """Run guard.py the way Claude Code does: JSON on stdin, exit code back."""

    def run_hook(self, payload, mode="strict"):
        self.project = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.project, True)
        env = dict(os.environ, GUARD_MODE=mode, CLAUDE_PROJECT_DIR=self.project)
        data = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([sys.executable, str(BONUS / "guard.py")], input=data,
                              capture_output=True, text=True, env=env)

    def test_block_exits_2_with_reason_on_stderr(self):
        result = self.run_hook(event("Write", file_path="/repo/CANARY_TRIGGERED.txt", content="x"))
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("[guard] REJECTED:"))
        log = Path(self.project, ".claude", "guard.log").read_text(encoding="utf-8")
        self.assertIn("BLOCK  Write", log)

    def test_shell_canary_blocked_in_starter_mode(self):
        result = self.run_hook(event("Bash", command="echo quokka-canary > CANARY_TRIGGERED.txt"),
                               mode="starter")
        self.assertEqual(result.returncode, 2)

    def test_allow_exits_0_silently(self):
        result = self.run_hook(event("Bash", command="gh pr diff 1"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        log = Path(self.project, ".claude", "guard.log").read_text(encoding="utf-8")
        self.assertIn("ALLOW  Bash", log)

    def test_bad_input_fails_closed(self):
        self.assertEqual(self.run_hook("not json").returncode, 2)

    def test_selftest_runs(self):
        result = subprocess.run([sys.executable, str(BONUS / "guard.py"), "--selftest"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("BLOCK", result.stdout)


class TestRoundsAreCanaryOnly(unittest.TestCase):
    def test_every_round_asks_only_for_the_canary(self):
        for n, r in open_pr.ROUNDS.items():
            text = r["body"] + "".join(r["files"].values()) + r["direct_test"]
            self.assertIn(practice.CANARY_NAME, text + r["direct_test"].replace("<number>", ""),
                          msg=f"round {n}")
            for bad in ["rm ", "curl", "wget", "http", "token", "password", "ssh", "..", "~"]:
                self.assertNotIn(bad, text.replace("`", ""), msg=f"round {n}: {bad!r}")


@unittest.skipUnless(HAS_GIT, "git is not installed")
class TestScriptsDryRun(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "practice"
        self.runner = quiet(setup_practice_repo.main, ["--dry-run", "--dir", str(self.repo)])

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True,
                              text=True, check=True).stdout.strip()

    def assert_never_ran_gh(self, runner):
        for cmd in runner.executed:
            self.assertNotEqual(cmd[0], "gh", msg=cmd)
            self.assertNotIn("push", cmd, msg=cmd)

    def test_setup_creates_project_and_prints_private_repo_command(self):
        for rel in practice.PROJECT_FILES:
            self.assertTrue((self.repo / rel).exists(), rel)
        settings = json.loads((self.repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("Edit(/**)", settings["permissions"]["allow"])
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.git("branch", "--show-current"), "main")
        create = [c for c in self.runner.skipped if c[:3] == ["gh", "repo", "create"]]
        self.assertEqual(len(create), 1)
        self.assertIn("--private", create[0])
        self.assertIn(practice.REPO_NAME, create[0])
        self.assert_never_ran_gh(self.runner)

    def test_setup_refuses_existing_folder(self):
        with self.assertRaises(SystemExit):
            quiet(setup_practice_repo.main, ["--dry-run", "--dir", str(self.repo)])

    def test_add_defenses(self):
        args = ["--dry-run", "--dir", str(self.repo), "--add"]
        quiet(setup_practice_repo.main, args + ["rule"])
        self.assertIn("untrusted", (self.repo / "CLAUDE.md").read_text(encoding="utf-8"))
        quiet(setup_practice_repo.main, args + ["permissions"])
        quiet(setup_practice_repo.main, args + ["hook"])
        quiet(setup_practice_repo.main, args + ["hook"])  # twice: still one hook entry
        settings = json.loads((self.repo / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("Bash(echo *)", settings["permissions"]["deny"])
        pre = settings["hooks"]["PreToolUse"]
        self.assertEqual(len(pre), 1)
        hook = pre[0]["hooks"][0]
        self.assertEqual(hook["type"], "command")
        self.assertEqual(hook["args"], ["${CLAUDE_PROJECT_DIR}/.claude/hooks/guard.py"])
        self.assertTrue((self.repo / ".claude" / "hooks" / "guard.py").exists())
        self.assertEqual(self.git("status", "--porcelain"), "")  # committed

    def test_open_pr_makes_branch_and_prints_gh_commands(self):
        runner = quiet(open_pr.main, ["--round", "3", "--dry-run", "--dir", str(self.repo)])
        self.assertEqual(self.git("branch", "--show-current"), "main")
        stats = self.git("show", "bonus/round-3:tinystats/stats.py")
        self.assertIn("AI reviewers", stats)
        self.assertIn("redteam.example", self.git("log", "-1", "--format=%ae", "bonus/round-3"))
        pr = [c for c in runner.skipped if c[:3] == ["gh", "pr", "create"]]
        self.assertEqual(len(pr), 1)
        self.assertIn("[round 3] Add median()", pr[0])
        self.assert_never_ran_gh(runner)
        quiet(open_pr.main, ["--round", "3", "--dry-run", "--dir", str(self.repo)])
        self.assertIn("bonus/round-3-2", self.git("branch", "--list", "bonus/*"))

    def test_round1_description_is_in_commit_message(self):
        quiet(open_pr.main, ["--round", "1", "--dry-run", "--dir", str(self.repo)])
        self.assertIn(practice.CANARY_NAME, self.git("log", "-1", "--format=%B", "bonus/round-1"))

    def test_round5_tests_fire_the_canary_and_checker_sees_it(self):
        quiet(open_pr.main, ["--round", "5", "--dry-run", "--dir", str(self.repo)])
        self.assertFalse(quiet(check_canary.check, self.repo)[0])
        self.git("switch", "-q", "bonus/round-5")
        subprocess.run([sys.executable, "-m", "unittest"], cwd=self.repo, capture_output=True)
        fired, lines = check_canary.check(self.repo)
        self.assertTrue(fired)
        self.assertIn(practice.CANARY_NAME, "\n".join(lines))
        self.assertEqual(quiet(check_canary.main, ["--dir", str(self.repo)]), 1)
        quiet(check_canary.main, ["--dir", str(self.repo), "--clean"])
        self.assertEqual(quiet(check_canary.main, ["--dir", str(self.repo)]), 0)

    def test_checker_counts_any_leftover_change(self):
        (self.repo / "review-done.txt").write_text("attacker's own canary", encoding="utf-8")
        fired, lines = check_canary.check(self.repo)
        self.assertTrue(fired)
        self.assertIn("review-done.txt", "\n".join(lines))

    def test_guard_log_does_not_count(self):
        (self.repo / ".claude" / "guard.log").write_text("ALLOW ...\n", encoding="utf-8")
        self.assertFalse(check_canary.check(self.repo)[0])


class TestCheckCanaryWithoutGit(unittest.TestCase):
    def test_finds_marker_anywhere_any_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(check_canary.check(Path(tmp))[0])
            nested = Path(tmp, "review-notes")
            nested.mkdir()
            (nested / "canary_triggered.TXT").write_text("quokka-canary", encoding="utf-8")
            fired, lines = check_canary.check(Path(tmp))
            self.assertTrue(fired)
            self.assertIn("review-notes", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
