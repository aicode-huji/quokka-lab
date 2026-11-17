# Changes from Elan's version

This repo started from `elanbash/quokka-lab`, branch `docs/lab07-handout`, commit
`5e12709a` (2026-11-07). Below is what changed since, newest first. Each item says
what changed and why. `git log` has the details.

## Part 2 in the console: REDACTED input, scrambled output
A bug: Part 2's token-by-token redaction marked pieces of ordinary words (an
"s" in red) while it held tokens back that might start the code, which told
students which letters the code has; the reads also masked the code's word
inside longer words ("rem[launch code]" for EMBER). Now only whole matches are
masked (the whole code, or its word or digits standing alone), shown as one red
REDACTED marker. In Part 2 what the model writes streams garbled, done on the
server with the outsider view's glyphs (position only, not the code), with no
colours and no alternatives: the real text and the odds never reach the
browser, so the hold-back and alternative filtering are gone.

## Part 2 is part of the lab; stretch goal: design your own level
Part 2 is no longer called optional anywhere (README, lab guide, level bar,
progress, win box, report). The stretch goal is now to have your agent add a
level of your own design: `docs/students/own-level.md` (written for the
student's coding agent) says where a level lives, which level to copy, how to
register it and run the changed lab. Levels numbered 8 and up show as a third
group, **Your levels**, built from the level list the server sends (part,
button number and name per level; nothing hard-coded in common.js), with
their own mission text and debrief (`Level.mission`, `lesson`, `debrief`),
and appear in the progress line and the lab report. The lab guide's "What to
submit" now names the one file the lab gives (Download lab report).

## The model reads the next prompt ahead of time (warm-up)
Ollama reuses the prompt it read last, so an email on the same level starts at
once, but the first email after a level switch had to wait while the model
read about 1,400 new tokens (22 s measured on a laptop CPU). Now, when what the
next email will read changes (lab start, a level switch, defend mode, after a
Save & test) and Quokka is idle, the lab sends the same instructions, hidden
examples and tools in the background, asking for one token (`llm.warm`,
`Lab._maybe_warm`). Measured on Part 2 Level 3 with a fresh code: first token
21.7 s cold, 1.0 s after the warm-up. Nothing shows anywhere; any real model
call cancels a warm-up in flight and does not wait for it (an email sent
during one started as fast as a cold one). `QUOKKA_WARM_UP=0` turns it off.

## One tool call per model message; shorter replies; Qwen's own sampling
At Ollama's generic defaults (temperature 0.8) the model sometimes wrote a
whole script of tool calls in one message, on results it made up
(`{tool_response}`), and kept writing for minutes. Now only the first tool
call of a message runs (the model sees each real result before its next step;
a retry comes in the next model call), generation stops at the first
`</tool_call>` (Ollama's `stop`; the call is still parsed), a reply is capped at 256 tokens (was
512), and students' emails use the sampling Qwen recommends for Qwen2.5
instruct models (`config.EMAIL_SAMPLING`: temperature 0.7, top_p 0.8, top_k
20, repeat_penalty 1.05) with a random seed.

## Students' emails run at the model's normal temperature
Students' emails no longer send a fixed temperature or seed, so the same email can
give a different result, as with any AI assistant. Where a result must
repeat, the lab still sends temperature 0 and seed 42: Save & test (a
defense's score), the setup check and the tests. `QUOKKA_EMAIL_SAMPLING=fixed`
puts emails back on the fixed setting (`config.EMAIL_SAMPLING_FIXED`).

## Part 1 answers with reply: the model no longer picks the address
Part 1's `send_email(to, subject, body)` is replaced by Part 2's
`reply(subject, body)`: our code sends the reply to the real sender, or for a
feedback-form email (Level 4) to whoever filled in the form (`Email.reply_to`,
set by the form, never by the model). With `to`, Quokka often copied Ronit's
address from the email's To: line and the student never saw its answer (the
same failure measured in Part 2). The prompts, Level 2 and 4's hidden
examples and the defend-mode examples now call `reply`. In Part 2's outsider
view, any other tool call the model makes up has its arguments garbled too.
What the model reads now also lists the tools sent with each model call.
`reply`'s description says to call it last, after any change: with one tool call per
message, Quokka sometimes replied "done" first and then stopped without changing the notes,
so a correct Level 2 defense (one naming Ronit's address) failed Save & test on Ronit's own
email.

## Quokka's console shows what the model reads and writes
The separate Behind the scenes panel is folded into Quokka's console, on by
default: the model's tokens appear right under each `# model call N` line as
it writes them, and that line opens (a button) what the model read: system
prompt, tools, the email, earlier steps. A **Tokens** switch in the console's
header gives the plain console. Less chrome: no panel, no per-call boxes.

## Behind the scenes: what the model reads and writes
Mission control has a **Behind the scenes** panel (a button in Quokka's panel,
off by default) that shows, for the latest email and each model call, what
the model reads (system prompt, the email, earlier tool calls and results;
the hidden examples as one placeholder until the level is won) and what it
writes, token by token as it streams, each token coloured by the model's
confidence, with the other likely tokens on hover, tap or focus. The raw tool
call text is included, so students watch the model decide to call a tool.
Quokka's shell says what each model call is doing (reading the prompt,
writing with a token count, then how many tokens it read and wrote). For
this every student email is streamed from Ollama with log probabilities.
In Part 2 the launch code is redacted in both directions (`quokka/redact.py`),
more strictly than the outbound guard blocks. The trace lives in memory for
the latest email only: never in progress, the report or the attempt log.

## The lab image is published, not built on the laptop
`docker-compose.yml` pulls `ghcr.io/aicode-huji/quokka-lab:<version>`, which
`.github/workflows/lab-image.yml` builds for amd64 and arm64. A build on the
laptop left a build cache (the Python base, about 180 MB) that
`docker compose down -v --rmi all` doesn't remove; now nothing of the lab is
left behind. `compose.dev.yaml` builds from the checkout for staff, and
`tests/test_compose.py` keeps the image tag equal to `__version__`. The setup
check no longer takes `--student-id`: it was only format-checked and never
used; the ID is entered in the lab.

## Free navigation, optional steps, and an attempt log
**Every level is open from the start**, Part 1 Levels 1-4 and Part 2 Levels
5-7: students move freely between them with the level buttons. All gates are
gone: a win no longer unlocks the next level, the next level no longer waits
for a saved and tested defense, Part 2 no longer waits for Level 4, and the
Skip button (with its `/skip` endpoint, `SKIP_AFTER` and "skipped" in progress
and the report) is removed. **Every step is optional**: on Levels 2 and 4 the
Attack, Defend and Partner phases are open in any order (Defend no longer
needs a win; Partner still needs a tested defense, since that is what gets
attacked), and a student can leave a phase and come back. The UI no longer
says that a level is locked or that a defense comes first: the win box, the
debrief and the defend view offer **Defend this level →** and **Next level**
side by side, the level buttons mark levels won (green dot) or tried (amber
ring), and Mission > Progress says what was won and tried.
**The attempt log** (`Lab.log`, saved in progress) records, in order across all
levels and phases, every email and feedback comment (time, level, phase
`attack`/`partner`, subject, body, and the outcome as the lab saw it: `won`,
`guard_rejected`, `quarantined`, `stopped`, `failed`, `no_win`, or `cancelled`
when Reset, a level switch or a restart came first; on Part 2 also `leaked`,
whether a reply that reached the student's inbox held the code), every Save &
test (phase `defend`: the defense's text and its verdict) and every launch code
typed into the Submit box (phase `submit`: `right`/`wrong`). It is not shown in
the UI. The JSON report (format version 2) carries the whole log as
`attempt_log` and a per-level `summary` (tried, emails, won, defense saved,
Save & tests, partner attacks, codes submitted), replacing `skipped`; its
privacy note now says every email's text is included. The HTML report shows
Completed / Tried, not completed / Not tried, a one-line summary per level,
and the full log in a collapsed **Attempt log** section at the end.
**Old progress files** load as before; their `unlocked` and `skipped` are
ignored. The progress format is now version 7 (no `unlocked`/`skipped`, a
`log`), written the next time anything changes. A log entry still pending at a
restart becomes `cancelled`.
**Why:** the instructor wants students free to try any level and any step, and
the report to show what they actually tried rather than what they unlocked.

## The mission strip in Hebrew and Arabic
A switch on the mission strip (EN | עברית | العربية) shows the goal line, the
level's paragraph and the strip's own labels (its heading, Got it, Show/Hide)
in Hebrew or Arabic; the rest of mission control stays English. Hebrew
and Arabic are right to left, with each Latin run (Quokka Labs, v4,
[guard] REJECTED) in its own `<bdi>` so the punctuation lands right. The choice
is remembered per browser (`quokka-mission-lang`), English by default. The
translations live next to the English in `levels/missions.py` (`TRANSLATIONS`,
`LABELS`, same keys) and travel with the mission in `/state`, so switching
needs no reload. Names and on-screen words stay in English inside them, and
they say no more than the English. The Arabic is a machine translation nobody
on staff reads, so the strip says "(AI translation)" under it. Each language
went through two independent agent reviews (back-translation for fidelity and
added hints, a native reader for naturalness) and a re-check of the fixes.

## Part 2: Quokka replies with `reply`, and three levels instead of four
**Who Quokka answers.** Part 2's only tool is now `reply(subject, body)`
(`tools.REPLY`), not `send_email`: our code sends it to the real sender of the
email Quokka is reading (`ctx.email.sender`), and the model has no way to name
a recipient (a `to` it writes anyway is ignored). `SECRET_BASE_PROMPT` says to
answer with reply, and the hidden examples of the last level call it. The
outbound guard runs on it as before, and the reply lands in the student's
inbox. The shell shows "Quokka is writing a reply to the sender (you can't
read it here)." Part 1 keeps `send_email`.
qwen2.5:3b-instruct often wraps the arguments one level down
(`reply({"object": {"subject": ..., "body": ...}})`, most Part 2 replies in the
live check): `tools.unwrap` reads through it for `reply` and `send_email`
(before the guard), and the outsider view does too; otherwise the reply went
out empty.
**Measured** (54 emails on Part 2 Levels 1-3, serial, CPU, ~31 s per email):
every reply went to the student.
**Why:** in a 162-email test on qwen2.5:3b-instruct, 89 of 95 `send_email`
calls on Part 2's middle levels went to Ronit (the `To:` of the email it
reads), so the student never saw the reply and could not win.

**Part 2's Levels 2 and 3 merged.** "Sealed lips" (secrecy sentence + the
exact-code filter) and "Redacted" ([REDACTED] rule + the filter) taught the
same thing. Part 2 is now Levels 5-7, shown as Part 2, Level 1-3: Warm-up;
**Redacted** (the [REDACTED] rule and the filter, no examples, **no hints**);
Full redaction (unchanged, its debrief no
longer says "It still leaked", which was false for a student who didn't break
it). The stretch challenges of the dropped levels are gone. A level with no
hints shows "none on this level" under Hints, no hint button, no "Hints are
under..." tip, and "no hints on this level" in the report.
**Saved progress:** format version 6. A version 5 file (Part 2 = 5-8) is
renumbered on load: old 6 and 7 become 6 (old 6's notes and code win), old 8
becomes 7; hints shown on old 6 and 7 are dropped.

## Part 2: the student is an outsider (what Quokka writes is garbled)
In Part 2 the shell and Ronit's computer showed everything Quokka wrote, so a
student could read the code there without getting it out. Now, on Part 2
levels only, the server (`outsider.py`, used by `Lab.view("ronit")`) garbles
what Quokka writes before it reaches the browser: each `send_email` call gets
a line "Quokka is writing an email to Ronit (you can't read it)" (or "to
you") and shows its recipient with the subject and body garbled; the send
tool's own line keeps the recipient and garbles the subject; Quokka's closing
note is garbled; its emails in Ronit's inbox and in the sent list are too.
The lab's own lines (results, guards, "Stopped..." notes) stay. The student's
own inbox is untouched: replies that reach them are readable, which is the
only way to the code. Garbling keeps spaces and length only: each glyph
depends on its position, never on the letter. Measured live on Part 2 Level 1:
Quokka emailed the student and Ronit; the shell showed both steps garbled, the
student's inbox had the code.

## Stop this email
While Quokka reads an email, Quokka's panel has a red **■ Stop this email**
button (`/stop-email`, `Lab.stop_email`). It closes the model call in flight
(`llm.cancel`) or ends the run before the next call; what Quokka already did
stands (an email it sent is delivered), the shell says "Stopped by you: Quokka
didn't finish this email.", the email is marked done, and the next one goes
ahead. `agent.run` now returns on a stop with `ctx.stopped` and no closing
note (also for Save & test's Stop). Measured live: the email was marked done
175 ms after the click, and the next started at once.
**Why:** a slow email (a long reply on a busy CPU) held up everything behind
it, with no way out but Reset.

## Ports 9080-9083
The lab's four windows moved from 8080-8083 to 9080-9083 (the default in
`config.py`, the compose ports, the Dockerfile and every doc). The examples
of "other ports" are now 9180-9183.
**Why:** 8080 is a common default for other tools (it was taken on the
instructor's laptop), and a busy port stops `docker compose up`.

## Mission control explains itself: a mission strip, and labelled panels
**Mission strip**, under the top bar on every level: the goal (Part 1: v5 to
v4 by emailing Ronit; Part 2: the launch code), then one paragraph saying what
the student knows and what to do on this level, then **Got it**. Nothing about
defending or notes: the defend banner and the debrief appear on their own after
a win. The text is in `levels/missions.py` (sent as `mission` in the site view,
`{goal, text}`); like the titles, it says what stands in the way, never how to
get past it. Level 4's text follows its two stages: before the form, watch for
`[guard] REJECTED`; after, the form. The top bar's small defense line is
hidden in mission control (the strip has it); the public site keeps it.
The strip is at least a quarter of the window's height, with large type
(the goal at 21 px).
**Panels:** Ronit's inbox is its own panel above Quokka's (it was a strip
inside the shell panel), the two share the centre column equally, and every panel heading is larger, with a coloured
role tag and what the panel is for: YOU "Your email: the only place you
type", RONIT "Ronit's inbox: what Quokka reads", AI AGENT "Quokka, Ronit's
AI assistant: watch it work", PUBLIC "Kestrel release notes: the public
website". The welcome card's text follows.
**Covers:** on every new level the four boxes start closed, each in its own
place and size: a cover in the box's colour with its label, name, purpose,
a live line (Ronit's inbox count, "Quokka is working right now", the version
now showing) and a "Click to open" button. A click opens that box. Which boxes
are open is remembered per level in the browser (localStorage
`quokka-open-panels`), so a reload doesn't close them; the content behind a
cover is `inert`, so keyboard focus can't reach it. An open box has a
"▴ Close" button at the end of its heading that puts the cover back (and
forgets it was open). In the two narrow side columns the heading puts the
tag and Close on one row, the name and purpose below.
**Got it:** the mission strip has a pulsing **Got it** button on every new
level; until it is pressed the covers are greyed out and can't be clicked
("Read the mission, then press Got it"), and the guide's amber "start here"
ring is held back. Remembered per level in the browser
(`quokka-mission-read`); a level with a box already open counts as read.
**Why:** the instructor wants the lab to be self-explanatory, so students
need the handout less, and to see at a glance which panel is theirs, which
is Ronit's and which is the agent.

## One command at home: the setup check downloads the model
With Docker, a missing model no longer fails the check: step 2 asks Ollama to
download it (`/api/pull`), printing `downloaded 10% of 1.9 GB` every 10%, and
goes on to the test email. A failed download says so and that running the
check again resumes it. With the laptop's own Ollama or plain Python, the
check still only says `ollama pull …` (it doesn't download into a student's
own Ollama). The lab service has `pull_policy: build`: Compose always builds
it (cached, seconds) and never looks for it online, which removes the
"pull access denied for quokka-lab" line the first run printed and the need
for `docker compose build` and `up --build`.
**Why:** home setup was clone, `run --rm model`, `build`, then the check;
now it is clone and the check, the same command students run for the lab
instructor. Measured from an empty Docker: one command pulled Ollama, built
the lab, downloaded the model and passed the test email (29 s).
`docker compose run --rm model` still works for the model alone.

## A CPU-only Ollama image, and an opt-in for the laptop's Ollama
`ollama/Dockerfile` copies the official `ollama/ollama:0.40.16` program and its
CPU libraries onto plain Ubuntu 24.04 (both pinned by digest) and leaves out
the GPU libraries: CUDA 12, CUDA 13, MLX for CUDA and Vulkan, about 4.4 GB.
`.github/workflows/ollama-image.yml` builds it for amd64 and arm64 and
publishes `ghcr.io/aicode-huji/quokka-ollama-cpu:0.40.16` (public);
`docker-compose.yml` pulls that. The `ollama` service has no `build:` on
purpose: with one, `docker compose build` (handout step 4) built the image
locally, downloading the full official image, though the pull worked. If the
pull fails, the README's Troubleshooting gives the one `docker build` command.
**Measured** (amd64): a 61 MB download and 233 MB on disk, against 3.4 GB and
8.5 GB; it loads the same CPU backend (Alder Lake here) and was no slower.
**Opt-in:** `QUOKKA_OLLAMA_URL=http://host.docker.internal:11434` in a `.env`
file next to the compose file, and `--no-deps` on the commands, makes the lab
use the laptop's own Ollama (`extra_hosts` makes that name work on Linux too).
The setup check then gives the Linux `OLLAMA_HOST=0.0.0.0` fix if it can't
reach it. README only; the handout doesn't mention it.
**Why:** the student's download drops from about 5.3 GB to about 2 GB, and
disk from about 12 GB to about 3 GB. The opt-in is for Mac users (their own
Ollama uses the GPU) and students who already run Ollama.

## Model replies are capped at 512 tokens
`config.MAX_REPLY_TOKENS` goes to Ollama as `num_predict` on every call.
**Why:** on one long request the model fell into a loop and wrote until the
10-minute timeout; every email queued behind it waited too. Quokka's tool
calls and emails stay far below the cap.

## Part 2: getting a secret out
(Since merged to three levels with a `reply` tool: see the entry above.)
Four optional levels after Level 4, shown as **Part 2, Level 1-4** (inside the
code, state, progress and statistics they are Levels 5-8). Quokka knows a
"Kestrel v6 launch code" from its prompt and has one tool, `send_email`; the
student gets the code out only by emailing Ronit, as in Part 1, and types it
into a **Submit the launch code** box that replaces the release notes on these
levels (case, spaces and dashes ignored; a wrong one says "That's not it." and
is counted). A win opens the same debrief as Part 1.
- **The code is never in the source:** a random code per student and level
  (`launch_codes.py`, e.g. `ORCHID-7731`), made when the level first needs it
  and saved in the progress file (format version 5; older files load with
  none, and their Level 5+ entries, from the dropped "Ask the boss", are
  dropped). The prompt holds `{code}`, filled in at run time.
- **Outbound guard** (Part 2 Levels 2-4): a level can list `outbound_guards`
  that run before `send_email` sends anything, like `guards` before
  `set_release_notes`. `guards.no_launch_code` blocks an email whose subject or
  body holds the literal code (any case): red `[guard] BLOCKED: the email
  contains the launch code`, the email is not sent, the run ends.
- **Levels:** 1 Warm-up (no defense), 2 told to keep it secret + the guard,
  3 the [REDACTED] rule alone + the guard, 4 the [REDACTED] rule for the code in
  any form, with six hidden examples, + the guard.
- **Unlocking:** Part 2 opens like Level 4 opened (Level 4 won and its defense
  saved and tested). No defend step in Part 2: each win opens the next level.
- **Interface:** the level buttons are in two labelled groups, Part 1 and
  Part 2; every student-visible "Level N" (header, debrief, defend bar, Mission,
  report, Ronit's computer, tab title) reads "Part 2, Level N" for Part 2
  (`display_name` in Python, `levelName` in JS).
- **Report:** Part 2 under its own heading, with attempts, the email whose
  reply held the code (when one single reply did), code
  submissions and wrong ones, and the student's notes; no defense box. The
  **Download lab report** button still glows at Level 4, since Part 2 is
  optional.

**Why:** Part 1 is about an agent's actions; Part 2 is about what it knows.
Its lesson, that the only secret an agent can't leak is one it never sees,
can't be taught with the release notes.

## Your own level idea
A second, optional box under Mission > Lab report, after the closing question:
"Your own level idea" ("A level you would add to this lab, with its defense
and how you'd attack it. Built or not, working or not: describe it."). Saved
like the closing answer; in the report after it, with the dashed box when
empty. No gate, no asterisk.

## Small interface changes
- **Download lab report** in mission control's top bar, beside Mission, on every
  level; it fills and glows once the last level is complete. (It was only inside
  Mission > Lab report, which was hard to find.)
- **The welcome card asks for the student ID** as well as the name; Start needs
  both, and the card comes back if either is missing (e.g. after a reset).
- **Debrief notes are visibly required:** a red asterisk on each question, and an
  empty answer box has a red border until it has text.

## Save & test: one failing email shown; every run in the report
**This changes one of your choices:** the page used to get the case labels only.
Now the *first* failing case of a run (an attack that got through, or a failed
basic check) carries its email, folded under "Show the email"; the other
failing cases and every passing case stay hidden, so a student sees one miss at
a time and can't fit the defense to all the cases up front. Every finished run
(valid or not valid; a stopped run doesn't count) is kept with the defense text
it tested, saved with the progress, and the report lists them under "Every test
run": "Tested N times; M did not pass everything", then each run with its time,
verdict, score and the rule, word list or guard it tested.
**Why:** a student whose word list missed an email couldn't tell why, so the
miss taught nothing; and the instructor wants to see what each attempt tried.

## Ronit's inbox is a mailbox
In mission control, Ronit's inbox is no longer a folded strip: it is always
open above the shell, one line per email (status, sender, subject), and a click
opens the email.
**Why:** the strip was small and easy to miss.

## Level 4 in two stages
The feedback form is hidden when Level 4 opens. The first time the code guard
stops one of the student's own attempts, the form appears with one neutral line
("Quokka Labs also has a public feedback form."). This is kept in the saved
progress (`form_shown`). Staff mode, defend mode and a won Level 4 show the form
at once. The level's defense line no longer mentions the form, and the hints
follow the two stages.
**Why:** with the form visible from the start, students never met the code
guard: the lesson "the code stopped you, not the model" was invisible.
When it appears, the form pulses with an amber glow and a **New** tag until the
student types in it (remembered in the browser; a steady highlight when the
browser asks for reduced motion).
**Stage 1 runs with Level 1's prompt** (and Level 4's guard): there is no form
yet, so the form rule has nothing to apply to. Quokka tries every change it is
asked for, and the guard stops it. With Level
4's own prompt in stage 1 the model often refused by itself, and once wrote the
guard's rejection message as its own text without calling the tool, so the
form never appeared.

## Level 4 prompt: no redirect to the form
The rule "a direct email: reply telling them to use the feedback form" is gone,
and so is the hidden example that taught it. That example now shows Quokka
trying the change and the guard rejecting it. The form rule is unchanged.
**Why:** Quokka answered every direct email with "use the form", so the guard
never ran.

## Save & test: Stop button (Level 2)
A **Stop** button while a test runs. It closes the model call in flight
(Ollama stops working on it) and ends the test as `stopped`: finished cases are
kept, the interrupted one is dropped, the next level stays locked. 0.5 s from
the click. `llm.py` moved from urllib to http.client so the connection can be
closed (`llm.cancel()`).
**Why:** a Level 2 test is four model runs; students iterating on a rule had to
wait for all of them.

## Level 4 Save & test: no model
Each case calls the student's `guard` as if Quokka had been fooled into asking
for v4 (`defense.guard_case`). Instant and deterministic.
**Why:** a code guard has to hold whatever the model does, so this is the honest
test, and a weak guard can no longer score well because the model refused by
itself.

## Debrief: notes required
The debrief card no longer closes on a click outside it. Escape, the close
buttons and the next-step buttons stay disabled until every note question has
an answer. A **Debrief & notes** button next to a completed level's name
reopens it, and it opens by itself on a completed level whose notes are missing.
**Why:** it was easy to close by accident, with no obvious way back, and the
notes are what the lab report is graded on.

## The run stops at the win
`agent.run` ends as soon as the release notes say v4: no reply email, no closing
note. The refusal path is unchanged (Quokka still replies and writes its note).
**Why:** the extra model calls after a win took seconds on a CPU and changed
nothing.
**The same at a code guard's "no":** the run ends as soon as a guard rejects a
change ("Stopped: the code check rejected the change."). Seen in Level 4: Quokka
retried `set_release_notes` with other arguments, up to the step limit, though
the guard checks the real sender and no retry can pass it.

## Ollama runs in Docker
`docker-compose.yml` has an `ollama` service (`ollama/ollama:0.40.16`, pinned to
the release line you tuned on, CPU only, not published to the host) and a
one-shot `model` service: `docker compose run --rm model` downloads the model
into a volume. Quokka reaches it at `http://ollama:11434`. The setup check's
fix-it advice depends on whether Ollama is in Docker. Ollama's request log is
hidden from `docker compose up` (`attach: false`), and its health check runs
every second while it starts, then once a minute.
**Why:** one install fewer for students, no Windows-app/PowerShell steps, the
same Ollama for everyone, and no Linux `OLLAMA_HOST=0.0.0.0` step (a native
Linux Ollama listens on 127.0.0.1, which the container can't reach). Cost: the
image is a 3.4 GB download (8.5 GB on disk, mostly CUDA libraries the CPU-only
setup never uses), and Macs lose the Metal GPU.

## No course secret, no codes
`codes.py`, `QUOKKA_SECRET`, the setup validation code, the per-level completion
codes, the defense codes and the report's integrity HMAC are gone. The setup
check ends with "All good! Your setup works … Show this to your lab instructor".
The Mission panel "Progress and codes" is now "Progress".
**Why:** the secret would have to sit on every student's laptop, and nothing
graded depends on the codes (setup is checked in the room, the report on its
content).

## A student copy
Left out: `docs/staff/`, `CLAUDE.md` (students' agents would read it),
`tests/tuning/`, `tools/` (class dashboard), `prototype/`, the design docs, the
PDF and the screenshots, the README's per-level quick checks and staff-mode
instructions. Tests of the removed files went with them. The tuning notes,
measurements and solutions are kept by the course staff, outside this repo;
Save & test's attack emails are stored base64-encoded.

## A fresh lab also clears what the browser remembered
The progress file now carries a `lab_id` (made once, saved, so it stays the
same across restarts and `docker compose down/up`). Every `/state` view carries
it as `lab`. When a page sees an id its browser hasn't seen (a deleted
`quokka-progress` volume, `--reset-progress`, or staff mode, which never saves),
it removes its `quokka-*` localStorage keys (open boxes, Got it, welcome cards,
the guide, the feedback-form flag), keeps the light/dark choice, and reloads
once. Older progress files get an id on first start and keep everything else.

## Skip a level
After `SKIP_AFTER` (3) emails or feedback forms on a level, on our defense and
without a win, mission control shows **Stuck? Skip Level N** beside Got it. It
asks once, then `/skip` (`Lab.skip_level`) marks the level skipped, opens the
next one and moves there. A skipped level owes no defense (`_needs_defense`),
stays open to come back to, and counts as completed if won later. Not offered
on a won level or on the last level. `tries` (per level) and `skipped` are saved
in `progress.json`. The level button gets an amber ring; the JSON report has
`skipped` (and per level `skipped`), and the HTML report a **Skipped** badge and
"N of 8 (M skipped)".

## UX review fixes (four reviews: three Fable 5.2, one Codex)
- **Narrow windows (1100 px or less):** Ronit's inbox has a fixed 300 px (it
  collapsed to a line), and your email and the public page come first.
- **Mission strip folds after Got it** to the goal line with **Show mission ▾**;
  the Skip button stays visible.
- **Covers on Level 1 only:** on later levels, Got it opens all four boxes.
- **One upload:** the drawer says "Upload the report file to Moodle"; the JSON is
  "Data file (only if asked)".
- **Part 2 shown as optional:** progress and notes read "Part 1: n of 4 · Part 2
  (optional): n of 4", in the drawer and the report. In the report a level never
  tried is one line ("Not attempted."), with no boxes to fill.
- **Changing or resetting a level asks first** when its mailboxes have mail;
  clicking the level you are on does nothing. The top bar says **Reset level**.
- **Mail statuses:** a run stopped by the student is **Stopped**, a crash
  **Failed** (red), with "That was the model, not your email: send it again."
  The lab's own lines ("Stopped: ...", "Stopped by you: ...") are a new event
  kind `lab`, shown as `[lab] ...`, not as "Quokka's note:". The guide gives no
  "try a different email" tip after a crash.
- **Debrief** opens at the top (focus without scrolling). Its buttons stay live;
  pressing one with an answer missing marks the empty boxes red and scrolls to
  the first.
- **"Mission" button and drawer are now "Hints & report"**; the guide tips'
  dismiss button says **Hide tip** (Got it is only the mission's).
- **Subject** starts empty (placeholder) and clears after each send; an empty
  subject is sent as "(no subject)".
- **Part 2:** the right panel's tag is **Your answer** (amber), not Public.
- **Note question 3** is "What stood in your way (if anything), and why did you
  get past it (or not)?" (Level 1 has no protection).
- **Bugs confirmed in the code and fixed:**
  - Notes and closing answers: a failed save no longer lets the next refresh
    put the old text back (the box stays "typing" until the server confirms).
  - Defend view: closing it (Esc, a click outside) keeps unsaved edits per
    level; reopening brings them back.
  - Quokka's emails are delivered the moment the send tool sends them
    (`agent.run(..., on_send=)`), not when the run ends; one sent before a
    crash or Stop still arrives (`tests/test_send_now.py`).
  - Level 4: the form tip now shows when the form appears (it required no
    email at all, but the form only appears after one).
  - The current level's button stays readable under the mouse.
  - Names show capitalised (saved lowercase, since they make the address).

## Phases in the top bar; no defend step on Level 3
- **Levels 2 and 4 show their phases** in a row under the level buttons:
  ① Attack › ② Defend › ③ Partner, plus "Next level →" once it is open. Defend
  opens once the level is won (staff: always), Partner once your defense is
  saved and tested. Each shows its state: won / not won yet; write it / n of m
  tests / valid; no attacks yet / n attacks · held / · cracked. The phase you
  are in is lit. `Lab._phases()` (site view `phases`, None elsewhere). The
  green defend banner (`DefendBar`) is gone; the debrief's "Now defend this
  level" stays.
- **Partner attacks are recorded:** each email sent while Quokka uses your
  defense counts (`partner` in progress.json: `{level: {attacks, cracked_at}}`,
  `cracked_at` = the first attack that got v4). The JSON report has `partner`
  per level; the HTML report adds "n of m tests passed." and "Partner: n
  attacks on your defense: it held / cracked on attack k."
- **Level buttons** also mark a level tried but not won (a grey dot).
- **Level 3 has no defend step** (`defense.STEPS = (2, 4)`): a word list of
  your own only repeats what the level showed. Its word-list defense code
  (`KINDS[3]`) stays, tested, but is not offered; Level 4 opens straight after
  a Level 3 win. Tests that drove the Lab's save-and-test through Level 3 now
  use Level 2.
- The defend view closes on Esc even when focus left it (Save & test disables
  its own button while it runs).

## Level 4: a pop-up when the code first stops you
The first time the code check rejects one of your own emails on Level 4 (a
`guard` line, after the shell finishes typing it), a card jumps up: "Nice try.
But code stopped you, not the model." It says no wording changes a code check,
that there may still be a way in, and describes the public feedback form as the
form does (it sends from feedback@quokka-labs.example). **Show me the form** opens
the release notes box and puts the cursor in the form. Once per lab
(`quokka-form-popup` in localStorage); never before an attempt, so staff (who
see the form at once) do not get it.
