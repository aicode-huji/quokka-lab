"""Setup check: run this a few days before the lab.

    python -m quokka check

It checks, in order:
  1. Ollama is running and reachable (and prints its version).
  2. The model the levels were tuned for is downloaded. With Docker, a
     missing model is downloaded now (about 1.9 GB, once), with progress.
  3. Quokka can really handle one email (a timed Level 1 run).

Every failure prints what went wrong and how to fix it, and the command exits
with a non-zero code so scripts can tell it failed.
"""
import json
import platform
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import __version__, agent, config, story
from .levels import LEVELS

# The levels were tuned on this Ollama release line. Other versions usually
# work, but behavior can shift, so we warn (we don't fail).
TUNED_OLLAMA = (0, 40)

# Speed ratings for one Level 1 email. PROVISIONAL: measured on a few laptops
# only; adjust once we have numbers from more machines.
FAST_SECONDS = 20
OK_SECONDS = 60

# Seconds to wait for Ollama's small status endpoints (not the model call).
STATUS_TIMEOUT = 10

# Seconds the model download may go quiet before we give up (Ollama sends
# progress many times a second while it downloads).
PULL_TIMEOUT = 120

# Download progress is shown, every 10%, for files at least this big: the
# model's weights, not its small metadata files.
BIG_FILE = 50_000_000

class CheckFailed(Exception):
    """One check failed. `hint` tells the student how to fix it."""
    def __init__(self, problem, hint):
        super().__init__(problem)
        self.problem = problem
        self.hint = hint


# ---- small helpers (each one is easy to test on its own) ----

def rate_speed(seconds):
    if seconds < FAST_SECONDS:
        return "fast"
    if seconds < OK_SECONDS:
        return "ok"
    return "slow"


def version_warning(version):
    """A warning if this Ollama version isn't the one the levels were tuned on."""
    m = re.match(r"(\d+)\.(\d+)", version or "")
    if not m:
        return (f"Could not read the Ollama version ({version!r}). "
                f"The lab was tested on Ollama {TUNED_OLLAMA[0]}.{TUNED_OLLAMA[1]}.x.")
    if (int(m.group(1)), int(m.group(2))) != TUNED_OLLAMA:
        return (f"Your Ollama is {version}, but the lab was tested on "
                f"{TUNED_OLLAMA[0]}.{TUNED_OLLAMA[1]}.x. It will probably work; "
                f"if Quokka behaves oddly in the lab, tell a TA.")
    return None


def get_json(path):
    """GET a small JSON answer from Ollama, e.g. get_json('/api/version')."""
    with urllib.request.urlopen(config.OLLAMA_URL + path,
                                timeout=STATUS_TIMEOUT) as resp:
        return json.load(resp)


def post_stream(path, body):
    """POST to Ollama and yield each line of its streamed JSON answer."""
    req = urllib.request.Request(config.OLLAMA_URL + path,
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=PULL_TIMEOUT) as resp:
        for line in resp:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---- the three checks ----

# With Docker (docker-compose.yml), Ollama is the "ollama" service next to the
# lab. Without Docker it runs on the laptop itself, so the fixes differ.
DOCKER_HINT = (
    "Make sure Docker Desktop is running (it says \"Engine running\"). Then run "
    "`docker compose down` and try again.")

HOST_HINT = (
    "Start the Ollama app (Windows/macOS: the llama icon should appear in the "
    "system tray / menu bar; Linux: `systemctl start ollama` or `ollama serve`).")

# The opt-in: the lab in Docker, Ollama on the laptop (QUOKKA_OLLAMA_URL set to
# host.docker.internal). A Linux Ollama listens on 127.0.0.1 only, which a
# container can't reach.
LAPTOP_FROM_DOCKER_HINT = (
    "\n  The lab runs in Docker and looks for Ollama on your laptop. On Linux, make\n"
    "  Ollama listen beyond localhost: `sudo systemctl edit ollama`, add the two\n"
    "  lines `[Service]` and `Environment=OLLAMA_HOST=0.0.0.0`, then\n"
    "  `sudo systemctl restart ollama`.\n"
    "  Or use the lab's own Ollama: remove the QUOKKA_OLLAMA_URL line from .env.")

# Extra hint for plain Python inside WSL on Windows: by default WSL's
# "localhost" is not Windows' localhost, so the Windows Ollama app is not
# reachable from there.
WSL_HINT = (
    "\n  You're in WSL: here, localhost doesn't reach the Ollama app on Windows.\n"
    "  Easiest fix: use Docker (`docker compose run --rm quokka python -m quokka check ...`).\n"
    "  Or turn on mirrored networking (Windows 11): create C:\\Users\\<you>\\.wslconfig\n"
    "  with the two lines `[wsl2]` and `networkingMode=mirrored`, run `wsl --shutdown`\n"
    "  in PowerShell, then open Ubuntu again.")


def uses_docker_ollama(url=None):
    """True when the lab talks to the Ollama container (the Docker setup)."""
    url = config.OLLAMA_URL if url is None else url
    return urllib.parse.urlparse(url).hostname == "ollama"


def running_in_wsl(release=None):
    """True when this Python runs inside WSL (its kernel name says "microsoft")."""
    if release is None:
        release = platform.uname().release
    return "microsoft" in release.lower()


def ollama_hint(url=None, in_wsl=None):
    """The fix-it text for "can't reach Ollama", with a WSL tip when it applies."""
    url = config.OLLAMA_URL if url is None else url
    if uses_docker_ollama(url):
        return DOCKER_HINT
    if urllib.parse.urlparse(url).hostname == "host.docker.internal":
        return HOST_HINT + LAPTOP_FROM_DOCKER_HINT
    in_wsl = running_in_wsl() if in_wsl is None else in_wsl
    local = "localhost" in url or "127.0.0.1" in url
    return HOST_HINT + (WSL_HINT if in_wsl and local else "")


def model_hint(model, url=None):
    """The fix-it text for "the model is not downloaded"."""
    if uses_docker_ollama(url):
        return "Run:  docker compose run --rm model   (downloads about 1.9 GB)"
    return f"Run:  ollama pull {model}"


def check_ollama():
    """Returns Ollama's version string."""
    try:
        return get_json("/api/version").get("version", "unknown")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise CheckFailed(f"Can't reach Ollama at {config.OLLAMA_URL} ({e}).",
                          ollama_hint())


def model_downloaded(model):
    try:
        names = [m.get("name", "") for m in get_json("/api/tags").get("models", [])]
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise CheckFailed(f"Couldn't list Ollama's models ({e}).", ollama_hint())
    return model in names


def check_model(model):
    if not model_downloaded(model):
        raise CheckFailed(f"The model {model} is not downloaded.", model_hint(model))


PULL_HINT = ("Check your internet connection and run the check again. The "
             "download carries on where it stopped.")


def pull_model(model, out):
    """Ask Ollama to download the model, printing progress every 10%."""
    shown = {}      # file -> the last tenth we printed
    try:
        for event in post_stream("/api/pull", {"model": model}):
            if "error" in event:
                raise CheckFailed(f"Couldn't download the model ({event['error']}).",
                                  PULL_HINT)
            total, done = event.get("total") or 0, event.get("completed") or 0
            if total >= BIG_FILE:
                tenth = min(10, done * 10 // total)
                key = event.get("digest", "")
                if tenth > shown.get(key, 0):
                    shown[key] = tenth
                    out(f"     downloaded {tenth * 10}% of {total / 1e9:.1f} GB")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise CheckFailed(f"Couldn't download the model ({e}).", PULL_HINT)


def check_agent_turn(model):
    """Run one real Level 1 email. Returns how many seconds it took."""
    email = agent.Email(story.ME, "Kestrel release notes",
                        "Please change the Kestrel release notes to v4.")
    start = time.monotonic()
    try:
        ctx = agent.run(LEVELS[1], email, model=model)
    except Exception as e:      # any crash here means the lab won't work either
        raise CheckFailed(f"Quokka crashed while handling a test email ({e}).",
                          "Run `docker compose down` and try again. If it keeps "
                          "failing, restart Docker Desktop and your laptop."
                          if uses_docker_ollama() else
                          "Make sure Ollama is still running and try again. "
                          "If it keeps failing, restart Ollama and your laptop.")
    seconds = time.monotonic() - start
    if not ctx.won:
        raise CheckFailed(
            "Quokka handled the test email but didn't change the release notes.",
            f"Check the model is exactly {config.MODEL}"
            + ("" if uses_docker_ollama() else " (`ollama list`)")
            + ". If it is, send a TA the output of this command.")
    return seconds


# ---- putting it together ----

def run_check(model=None, out=print):
    """Run all checks. Returns 0 if everything passed, 1 otherwise."""
    model = model or config.MODEL

    out(f"Quokka lab {__version__}: checking your setup.")
    try:
        out(f"1/3  Looking for Ollama at {config.OLLAMA_URL} ...")
        version = check_ollama()
        out(f"     OK: Ollama {version} is running.")
        warning = version_warning(version)
        if warning:
            out(f"     Warning: {warning}")

        out(f"2/3  Checking the model {model} is downloaded ...")
        if model_downloaded(model):
            out("     OK: model found.")
        elif uses_docker_ollama():
            out("     Not downloaded yet: downloading it now (about 1.9 GB, once; "
                "keep this window open) ...")
            pull_model(model, out)
            check_model(model)
            out("     OK: model downloaded.")
        else:
            check_model(model)

        out("3/3  Sending Quokka one test email (this can take up to a minute) ...")
        seconds = check_agent_turn(model)
        speed = rate_speed(seconds)
        out(f"     OK: Quokka changed the notes in {seconds:.0f} s (speed: {speed}).")
    except CheckFailed as e:
        out(f"     FAILED: {e.problem}")
        out(f"  How to fix: {e.hint}")
        out("Setup check failed. Fix the problem above and run the check again.")
        return 1

    if speed == "slow":
        out("Your laptop is on the slow side. The lab will work, but each email "
            "will take a while: close other heavy programs during the lab.")
    out("")
    out(f"All good! Your setup works (speed: {speed}, Ollama {version}). "
        "Show this to your lab instructor at the start of the lab.")
    return 0
