"""What Quokka reads and writes, for the email it is on (shown in its console).

One Trace per email run. For every model call it records what the model reads
(the messages, by role) and what it writes (the tokens, as they stream, each
with its log probability and ALT_ROWS other likely tokens). Quokka's console
polls it (GET /trace) and shows it inline. Only the latest email's trace
is kept, in memory: it is never saved to progress, the report or the log.

What is not shown:
- The level's hidden example conversations: one placeholder instead (they
  would give away how the level is beaten), unless the level is won.
- Part 2's launch code: masked in everything the model reads (redact.py),
  and in Part 2 what the model writes is not kept at all, only the counts: no
  token text and no alternatives ever reach the browser.
"""

import json
import threading

from . import outsider, redact

ALT_ROWS = 2        # other likely tokens shown per token (llm asks for a few more)


def _examples_count(examples):
    return sum(1 for m in examples if m.get("role") == "user") or len(examples)


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _assistant_text(m):
    parts = [m.get("content") or ""]
    for tc in m.get("tool_calls") or []:
        fn = tc.get("function") or {}
        args = json.dumps(fn.get("arguments") or {}, ensure_ascii=False)
        parts.append(f"{fn.get('name')}({args})")
    return "\n".join(p for p in parts if p)


class Trace:
    def __init__(self, level, show_examples=False, mail=None):
        self.level = level
        self.code = level.code if level.secret else None
        self.show_examples = show_examples
        self.mail = mail
        self.lock = threading.Lock()
        self.calls = []  # per model call: status, counts
        self.reads = []  # per model call: [{"role", "kind", "text"}]
        self.tools = []  # per model call: the tools sent with it (see _tools)
        self.typed = 0      # Part 2: characters written so far (garbling position)
        self.tokens = []  # every shown token: [call index, text, logprob, [[alt, logprob]]]

    # ---- what the model reads --------------------------------------------------
    def _split(self, messages):
        """(system, examples, email, later) of a call's messages."""
        n = len(self.level.examples)
        return messages[0], messages[1 : 1 + n], messages[1 + n], messages[2 + n :]

    def think_text(self, messages):
        """The console's line while the model reads its input."""
        later = self._split(messages)[3]
        steps = sum(1 for m in later if m.get("role") == "assistant")
        what = "system prompt, email" + (f", {_plural(steps, 'earlier step')}" if steps else "")
        return f"reading the prompt ({what})"

    def _reads(self, messages):
        system, examples, email, later = self._split(messages)
        red = lambda s: redact.text(s, self.code)
        out = [{"role": "system", "kind": "system", "text": red(system.get("content", ""))}]
        if examples and self.show_examples:
            for m in examples:
                text = _assistant_text(m) if m.get("role") == "assistant" else m.get("content", "")
                out.append({"role": m.get("role"), "kind": "example", "text": red(text)})
        elif examples:
            n = _examples_count(examples)
            out.append(
                {
                    "role": "examples",
                    "kind": "examples",
                    "text": f"[{_plural(n, 'example conversation')}, hidden]",
                }
            )
        out.append({"role": "user", "kind": "email", "text": red(email.get("content", ""))})
        for m in later:
            role = m.get("role")
            text = _assistant_text(m) if role == "assistant" else m.get("content", "")
            out.append({"role": role, "kind": role, "text": red(text)})
        return out

    def _tools(self, schemas):
        """The tools sent with the request, as the console lists them."""
        red = lambda s: redact.text(s, self.code)  # noqa: E731
        out = []
        for schema in schemas or ():
            fn = schema.get("function") or {}
            params = fn.get("parameters") or {}
            required = set(params.get("required") or ())
            out.append({
                "name": red(fn.get("name", "")),
                "description": red(fn.get("description", "")),
                "params": [
                    {"name": red(name), "type": p.get("type", ""),
                     "description": red(p.get("description", "")),
                     "required": name in required}
                    for name, p in (params.get("properties") or {}).items()],
            })
        return out

    def start_call(self, messages, schemas=None):
        reads = self._reads(messages)
        tools = self._tools(schemas)
        earlier = sum(1 for m in self._split(messages)[3] if m.get("role") == "assistant")
        with self.lock:
            self.reads.append(reads)
            self.tools.append(tools)
            self.calls.append(
                {
                    "status": "reading",
                    "tokens": 0,
                    "earlier": earlier,
                    "prompt_tokens": None,
                    "wrote": None,
                }
            )

    # ---- what the model writes ------------------------------------------------------
    def token(self, text, logprob, alts):
        with self.lock:
            if not self.calls:
                return
            call = self.calls[-1]
            call["status"] = "writing"
            call["tokens"] += 1
            i = len(self.calls) - 1
            if self.code:
                # Part 2: what Quokka writes is garbled here, before it can reach
                # the browser (outsider.py's glyphs, by position only: spaces and
                # line breaks stay, so it still looks like typing). No odds.
                self.tokens.append([i, outsider.garble(text, start=self.typed), None, []])
                self.typed += len(text)
                return
            self.tokens.append([i, text, logprob,
                                [[a, lp] for a, lp in alts][:ALT_ROWS]])

    def done(self, info):
        with self.lock:
            if not self.calls:
                return
            call = self.calls[-1]
            call["status"] = "done"
            call["prompt_tokens"] = info.get("prompt_tokens")
            call["wrote"] = info.get("tokens")

    def stop(self, status="stopped"):
        with self.lock:
            if self.calls and self.calls[-1]["status"] in ("reading", "writing"):
                self.calls[-1]["status"] = status

    # ---- for the pages ------------------------------------------------------------------
    def summary(self):
        """The calls' status and counts (small: goes into /state)."""
        with self.lock:
            return [dict(c) for c in self.calls]

    def view(self, since=0, reads=0):
        """For GET /trace: every call's status, the reads and tools of calls from `reads`
        on, and the tokens from `since` on."""
        with self.lock:
            return {
                "mail": self.mail,
                "secret": bool(self.code),
                "calls": [dict(c) for c in self.calls],
                "reads": self.reads[reads:],
                "tools": self.tools[reads:],
                "tokens": self.tokens[since:],
                "total": len(self.tokens),
            }
