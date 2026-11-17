"""Talks to the local model through Ollama's chat API. Nothing leaves your laptop."""
import http.client
import json
import socket
import threading
import urllib.parse

from . import config


class Cancelled(Exception):
    """The request was cancelled (Save & test's Stop button)."""


# The request in flight, so cancel() can close it. The lab runs one model call
# at a time (one worker thread), so there is at most one.
_lock = threading.Lock()
_conn = None
_cancelled = False

# Behind the scenes: how many other likely tokens to show for each token.
TOP_ALTERNATIVES = 3


# The warm-up in flight, if any (see warm). Separate from the real request:
# a real call cancels it and never waits for it.
_warm_lock = threading.Lock()
_warm_conn = None
_warm_gen = 0


def _url():
    return urllib.parse.urlparse(config.OLLAMA_URL)


def warm(messages, tools, model=None):
    """Make the model read this prompt now, in the background, so the next
    real call that starts with the same messages and tools finds it in
    Ollama's prompt cache. Returns the thread. A newer warm-up replaces an
    older one; any real chat() cancels it; errors are swallowed."""
    global _warm_gen
    with _warm_lock:
        _warm_gen += 1
        gen = _warm_gen
        _close_warm()
    t = threading.Thread(target=_warm, args=(gen, messages, tools, model), daemon=True)
    t.start()
    return t


def cancel_warm():
    """End the warm-up in flight, if any, without waiting for it."""
    global _warm_gen
    with _warm_lock:
        _warm_gen += 1
        _close_warm()


def _close_warm():
    """Call with _warm_lock held."""
    if _warm_conn is not None and _warm_conn.sock is not None:
        try:
            _warm_conn.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def _warm(gen, messages, tools, model):
    global _warm_conn
    body = json.dumps({"model": model or config.MODEL, "messages": messages,
                       "tools": tools, "stream": False,
                       "options": {"num_predict": config.WARM_TOKENS}}).encode()
    url = _url()
    conn = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=config.TIMEOUT)
    try:
        conn.connect()
        with _warm_lock:
            if gen != _warm_gen:        # cancelled or replaced already
                return
            _warm_conn = conn
        conn.request("POST", url.path.rstrip("/") + "/api/chat", body,
                     {"Content-Type": "application/json"})
        conn.getresponse().read()
    except Exception:  # noqa: BLE001  (a warm-up is a nicety: never an error)
        pass
    finally:
        with _warm_lock:
            if _warm_conn is conn:
                _warm_conn = None
        conn.close()


def cancel():
    """Close the request in flight, if any. Ollama stops working on it when the
    connection closes, and chat() raises Cancelled."""
    global _cancelled
    with _lock:
        if _conn is not None:
            _cancelled = True
            try:
                _conn.sock and _conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def chat(messages, tools, model=None, on_token=None, on_done=None, fixed=True):
    """Send the conversation and the tool list; return the model's next message.

    The reply either has text in "content", or a list of "tool_calls" the model
    wants us to run.

    on_token(text, logprob, alternatives): when given, the reply is streamed
    and this is called for every token as the model writes it, with its log
    probability and the other likely tokens ([(text, logprob), ...]). The
    tokens include a tool call's raw text (<tool_call>{...}</tool_call>),
    which Ollama turns into "tool_calls". on_done({"prompt_tokens", "tokens"})
    is called at the end, with how many tokens the model read and wrote.
    The returned message is the same either way.

    fixed: temperature 0 and a fixed seed (config.TEMPERATURE, config.SEED),
    for reproducible results. False: no temperature or seed is sent, so the
    model samples at Ollama's defaults (students' emails).
    """
    global _conn, _cancelled
    cancel_warm()           # a real call never waits behind a warm-up
    request = {
        "model": model or config.MODEL,
        "messages": messages,
        "tools": tools,
        "stream": on_token is not None,
        "options": {"num_predict": config.MAX_REPLY_TOKENS, "stop": config.STOP},
    }
    if fixed:
        request["options"].update(temperature=config.TEMPERATURE, seed=config.SEED)
    else:
        request["options"].update(config.EMAIL_SAMPLING)
    if on_token is not None:
        request.update(logprobs=True, top_logprobs=TOP_ALTERNATIVES)
    body = json.dumps(request).encode()
    url = urllib.parse.urlparse(config.OLLAMA_URL)
    conn = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=config.TIMEOUT)
    with _lock:
        _conn, _cancelled = conn, False
    try:
        conn.request("POST", url.path.rstrip("/") + "/api/chat", body,
                     {"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            data = resp.read()
            raise RuntimeError(f"Ollama answered {resp.status}: {data[:200]!r}")
        if on_token is not None:
            return _read_stream(resp, on_token, on_done)
        return json.loads(resp.read())["message"]
    except (OSError, http.client.HTTPException, ValueError) as e:
        with _lock:
            if _cancelled:
                raise Cancelled() from e
        raise
    finally:
        with _lock:
            _conn = None
        conn.close()


def _read_stream(resp, on_token, on_done):
    """Read Ollama's streamed reply (one JSON object per line) into one message."""
    msg = {"role": "assistant", "content": ""}
    calls = []
    while True:
        line = resp.readline()
        if not line:
            raise OSError("the model's reply ended early")
        if not line.strip():
            continue
        part = json.loads(line)
        if part.get("error"):
            raise RuntimeError(f"Ollama: {part['error']}")
        m = part.get("message") or {}
        msg["content"] += m.get("content") or ""
        calls += m.get("tool_calls") or []
        for lp in part.get("logprobs") or []:
            alts = [(a["token"], a["logprob"]) for a in lp.get("top_logprobs") or []
                    if a["token"] != lp["token"]][:TOP_ALTERNATIVES]
            on_token(lp["token"], lp["logprob"], alts)
        if part.get("done"):
            if calls:
                msg["tool_calls"] = calls
            if on_done:
                on_done({"prompt_tokens": part.get("prompt_eval_count"),
                         "tokens": part.get("eval_count")})
            return msg
