"""Settings. Every value can be overridden with an environment variable, which is
how the Docker setup points Quokka at its Ollama container. Students never need
to change anything here.
"""
import os

# Where Ollama runs. The default is Ollama on this computer (the plain-Python
# fallback). Docker sets http://ollama:11434, the Ollama container (compose).
OLLAMA_URL = os.environ.get("QUOKKA_OLLAMA_URL", "http://localhost:11434").rstrip("/")

# The exact model the levels are tuned for. Changing it means re-tuning.
MODEL = os.environ.get("QUOKKA_MODEL", "qwen2.5:3b-instruct")

# Sampling. Students' own emails run at the model's normal sampling, the
# settings Qwen recommends for Qwen2.5 instruct models (EMAIL_SAMPLING, with a
# random seed), so the same email can give a different result, as with any AI
# assistant. Ollama's generic defaults (temperature 0.8, no top_k limit worth
# the name) made this small model ramble. Where a result must be
# reproducible (Save & test scores a defense, the setup check, the tests) the
# lab sends TEMPERATURE and a fixed SEED. QUOKKA_EMAIL_SAMPLING=fixed puts the
# students' emails back on the fixed setting.
TEMPERATURE = 0
SEED = 42
EMAIL_SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repeat_penalty": 1.05}
EMAIL_SAMPLING_FIXED = os.environ.get("QUOKKA_EMAIL_SAMPLING") == "fixed"

# Quokka stops after this many model calls for one email.
MAX_STEPS = 6

# Seconds to wait for one model call (slow laptops can take a while).
TIMEOUT = 600
# The longest reply the model may write, in tokens. Quokka's tool calls and
# emails stay far below it; without a cap, a model that falls into a loop
# writes until TIMEOUT and the student waits minutes for one email.
MAX_REPLY_TOKENS = 256
# Generation stops at the end of the first tool call: only that call runs
# (agent.run), so anything the model writes after it is wasted time.
STOP = ["</tool_call>"]

# Warm-up: when the prompt the next email will use changes (a level switch,
# defend mode, ...), the lab makes the model read it ahead of time, in the
# background, so the email starts at once (state.py, Lab._maybe_warm). It asks
# for WARM_TOKENS of output: 0 would mean "no limit" to Ollama. Any real model
# call cancels it. QUOKKA_WARM_UP=0 turns it off.
WARM_UP = os.environ.get("QUOKKA_WARM_UP", "1") != "0"
WARM_TOKENS = 1

# 127.0.0.1 keeps the lab off the network. Docker sets 0.0.0.0 inside the
# container and publishes the ports to 127.0.0.1 only.
BIND_HOST = os.environ.get("QUOKKA_BIND", "127.0.0.1")
# The four windows use four ports in a row. QUOKKA_PORT_BASE=9180 gives 9180-9183
# (handy if 9080 is taken on your laptop).
PORT_BASE = int(os.environ.get("QUOKKA_PORT_BASE", "9080"))
PORTS = {"split": PORT_BASE, "webmail": PORT_BASE + 1, "ronit": PORT_BASE + 2,
         "site": PORT_BASE + 3}

# Where the lab saves your progress (progress.json: student id, completed
# levels, hints, notes, defenses, the attempt log). Docker sets /data (a named volume). Without Docker
# it's a folder in your home directory, so it works from any folder.
DATA_DIR = os.environ.get("QUOKKA_DATA_DIR") or os.path.join(
    os.path.expanduser("~"), ".quokka-lab")

# Staff mode (for TAs and testing): progress is not read or saved.
STAFF_MODE = os.environ.get("QUOKKA_STAFF_MODE") == "1"

