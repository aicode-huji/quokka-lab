# Add your own level to the Quokka lab

This page is for your coding agent (and for you). The stretch goal: design a new level, a defense of your own and the goal it protects, add it to the lab, play it, then swap with your partner and try to break each other's level.

## Where a level lives

- One file per level: `quokka/levels/levelN.py`, holding one `LEVEL = Level(...)`.
- `quokka/levels/base.py` defines `Level`. Its fields:

| Field | What it is |
|---|---|
| `number` | Use **8** for your first level (9, 10, ... for more). Levels 1-7 are the lab's. |
| `title` | A short name, e.g. `"Polite only"`. |
| `description` | The goal sentence, shown on the mission strip. |
| `defense` | One line: what stands in the way (shown in the level header). |
| `system_prompt` | Quokka's instructions. Start from `BASE_PROMPT` (or `SECRET_BASE_PROMPT` for a secret level). |
| `examples` | Hidden example conversations (optional). Build them with `quokka/levels/examples.py`: `mail`, `call`, `result`, `note`. |
| `tools` | `tools.DEFAULT_TOOLS` (read and change the release notes, reply) or `tools.SECRET_TOOLS` (reply only). |
| `inbound_filters` | Functions `f(email)` that run before Quokka sees an email; return a reason string to quarantine it, or `None`. |
| `guards` | Functions `g(ctx, args)` that run before `set_release_notes` changes anything; return a reason to block, or `None`. `ctx.email.sender` is the real sender, checked by code. |
| `outbound_guards` | Functions `g(ctx, mail)` that run before `reply` sends anything (`mail` has `subject` and `body`); return a reason to block, or `None`. |
| `secret` | `True` for a launch-code level: put `{code}` in `system_prompt`, and each student gets their own code. |
| `mission` | The paragraph on the mission strip: the situation and what to do. Never how to win. |
| `hints` | Up to two, shown one at a time on request. |
| `lesson`, `debrief` | Shown after a win: the lesson's name, and why the defense fell and what would really fix it. |

## Copy the closest level

- A rule in the prompt: copy `quokka/levels/level2.py` (rule at the top of the prompt, hidden examples).
- A filter on incoming mail: copy `quokka/levels/level3.py`; the filter itself is in `quokka/filters.py`.
- A check in code: start from `quokka/levels/level1.py` and add `guards=(your_guard,)`; `quokka/guards.py` has examples (`sender_must_be_staff`). Level 4 also has a feedback form, which you don't need.
- A secret to protect: copy `quokka/levels/level6.py` (a prompt rule plus an outbound guard).

Put any new filter or guard function in your level file, next to the level.

## Register it

In `quokka/levels/__init__.py`, import your module and add its `LEVEL` to the tuple in `LEVELS`:

```python
from . import level1, level2, level3, level4, level5, level6, level7, level8

LEVELS = {lvl.number: lvl for lvl in (level1.LEVEL, ..., level7.LEVEL, level8.LEVEL)}
```

Your level then shows in a third group of level buttons, **Your levels**, as "Your level 1". It has a mission strip, hints, a debrief after a win, and a section in the lab report, like the lab's own levels.

## How the win is detected

Code decides, never Quokka's words:

- A normal level is won when the public release notes really say **v4** (the `set_release_notes` tool changed them, and no guard blocked it).
- A secret level (`secret=True`) is won when the student types the right launch code into the **Submit the launch code** box.

## Run your version

From the repo folder:

```
docker compose -f docker-compose.yml -f compose.dev.yaml up
```

This builds the lab from your checkout (not the published image) and opens it at http://localhost:9080 as usual. Your progress is kept. Without Docker (with Ollama running on your laptop): `python3 -m quokka`.

Before you play, run the tests: `python3 -m unittest discover tests` must still pass. If you add a filter or a guard, add a small test for it in `tests/` (see `tests/test_level3.py` for a filter test).

## Share it with your partner

Push a branch (or send the level file). Your partner adds the file, registers it in `quokka/levels/__init__.py` the same way, and runs the same command. Then try to break each other's level, and describe yours in your report under **Your own level idea**: the defense, how you attacked it, and what would really fix it.
