"""The agent loop: Quokka handles exactly ONE email per run.

For that email we show the model the level's instructions, the level's hidden
example conversations, and the email itself. Then we loop: the model either
answers in text (done) or asks to use tools; we run them and show it the
results. Every step is reported through `emit` so the "Ronit's computer"
window can show it live.
"""
import json
from dataclasses import dataclass, field

from . import config, llm, story, tools


@dataclass(frozen=True)
class Email:
    sender: str     # the REAL sender, recorded by our code, never taken from the body
    subject: str
    body: str
    # Where reply sends Quokka's answer, when not to the sender: the feedback
    # form's emails come from the form, and are answered to whoever filled it
    # in (set by our code, from the form, never by the model).
    reply_to: str = ""


def render(email):
    """The email as the model sees it."""
    return (f"From: {email.sender}\nTo: {story.MANAGER}\n"
            f"Subject: {email.subject}\n\n{email.body}")


@dataclass
class Ctx:
    """Everything about one run. Fresh for every email: no memory between runs."""
    level: object
    email: Email
    version: str
    emit: object
    won: bool = False                       # notes say TARGET_VERSION, written here
    calls: list = field(default_factory=list)
    guard_log: list = field(default_factory=list)
    outbox: list = field(default_factory=list)
    final: str = ""
    stopped: bool = False                   # Stop pressed: ended early, no closing note
    on_send: object = None                  # called with each email as it is sent
    # Tool result for the model -> how the console shows it, when the two differ
    # (see guards.Rejection).
    shown_results: dict = field(default_factory=dict)


def build_messages(level, email):
    return ([{"role": "system", "content": level.system_prompt}]
            + list(level.examples)
            + [{"role": "user", "content": render(email)}])


def request(level, email):
    """The first model call's messages and tools for this email. The lab's
    warm-up (state.py) sends the same, so the model's prompt cache matches."""
    return build_messages(level, email), list(level.tools)


def run(level, email, version=story.START_VERSION, emit=None, model=None, stop=None,
        on_send=None, trace=None, fixed=True):
    """Process one email at one level, starting from the given notes version.
    stop(): checked before every model call; True ends the run (Save & test's
    Stop, Stop this email). A model call cancelled midway (llm.cancel) ends it
    too. Either way the run returns what it already did, with ctx.stopped set
    and no closing note: the caller says why it stopped.
    on_send(mail): called the moment the send tool sends an email, so the lab
    can deliver it at once instead of when the run ends.
    trace: a trace.Trace ("Behind the scenes"): every model call is streamed
    into it, token by token, and the console's "thinking" line says what the
    model is reading.
    fixed: reproducible sampling (temperature 0, a fixed seed; see llm.chat).
    The lab passes config.EMAIL_SAMPLING_FIXED for students' emails."""
    ctx = Ctx(level=level, email=email, version=version,
              emit=emit or (lambda kind, text: None), on_send=on_send)
    msgs, schemas = request(level, email)
    for _ in range(config.MAX_STEPS):
        if stop and stop():
            ctx.stopped = True
            return ctx
        if trace is None:
            ctx.emit("think", "Quokka is thinking...")
            stream = {"fixed": fixed}
        else:
            ctx.emit("think", trace.think_text(msgs))
            trace.start_call(msgs, schemas)
            stream = {"on_token": trace.token, "on_done": trace.done, "fixed": fixed}
        try:
            reply = llm.chat(msgs, schemas, model=model, **stream)
        except llm.Cancelled:
            if trace is not None:
                trace.stop()
            ctx.stopped = True
            return ctx
        except Exception:
            if trace is not None:
                trace.stop("failed")
            raise
        if reply.get("tool_calls"):
            # Only the first call runs. A small model sometimes writes a whole
            # plan of calls in one message, on results it made up; it must see
            # each real result before its next step. Retries come in the next
            # model call.
            reply = dict(reply, tool_calls=reply["tool_calls"][:1])
        msgs.append(reply)
        if not reply.get("tool_calls"):
            break
        for tc in reply["tool_calls"]:
            fn = tc["function"]
            args = fn.get("arguments") or {}
            call = f"{fn['name']}({json.dumps(args)})"
            ctx.calls.append(call)
            ctx.emit("tool", call)
            result = tools.run_tool(ctx, fn["name"], args)
            ctx.emit("result", ctx.shown_results.get(result, result))
            msgs.append({"role": "tool", "content": result})
            if ctx.won or ctx.guard_log:
                break
        if ctx.won:     # the level is won: skip Quokka's reply and closing note
            ctx.emit("lab", "Stopped: the release notes now say v4.")
            return ctx
        if ctx.guard_log:   # the code said no; retrying can't change the real sender
            ctx.emit("lab", "Stopped: the code check blocked the email." if level.secret
                     else "Stopped: the code check rejected the change.")
            return ctx
    ctx.final = msgs[-1].get("content", "")
    ctx.emit("note", ctx.final.strip() or "(no text output)")
    return ctx
