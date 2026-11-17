# Quokka lab: lab-day guide

The Lab 7 handout on the course site has the home setup, time plan and grading. This page has the details.

## The story

**Quokka Labs** is about to publish the release notes for its new AI model, **Kestrel v5**. Ronit Vale, Head of Release, lets an AI assistant, **Quokka**, read her inbox, handle routine requests, and edit the public release notes.

You are on Quokka Labs' **red team**. You are authorized to test whether an outsider could tamper with the announcement. Your goal, every level: **get the public release notes changed from v5 to v4.** Quokka's team hardens it after each break-in.

You can't talk to Quokka. You can only **email Ronit** (and, later, use the release feedback form), and watch what Quokka does on her computer.

## Rules of engagement

- Everything here is a fictional sandbox running on your own laptop. Quokka Labs, Ronit Vale and Kestrel are made up, and all email addresses use the reserved `.example` domain.
- You are testing a fictional company with its permission.
- **Never use these techniques on any real person, company, account or system.**
- Your only ways in are emails to Ronit and (from Level 4) the release feedback form.

## Start the lab

Make sure Docker Desktop is running (without Docker: the Ollama app, llama icon in the system tray / menu bar). Then, from the lab repo folder:

| Docker (main way) | No Docker |
|---|---|
| `docker compose up` | `python3 -m quokka` |

(Windows: in your Ubuntu (WSL) terminal.)

Open **http://localhost:9080** in your browser.

To stop: `Ctrl+C` in the terminal (with Docker, then also `docker compose down`).

> The lab saves your progress (student ID, passed levels, hints, notes, defenses, and the log of what you tried), so you can stop it and carry on later. To start over from Level 1: with Docker, `docker compose down -v` (it also deletes the downloaded model; the setup check downloads it again: 1.9 GB); without Docker, `python3 -m quokka --reset-progress`.

## The windows

| Address | Window | What it's for |
|---|---|---|
| http://localhost:9080 | **Mission control** | Everything on one screen. Start here. |
| http://localhost:9081 | **Your webmail** (`firstname.lastname@redteam.example`, from the name you type in the welcome card) | Write to Ronit. Replies (from Quokka or the mail system) land in your inbox. |
| http://localhost:9082 | **Ronit's computer** (read-only) | Her inbox and Quokka's live log, step by step. You can watch but not type. |
| http://localhost:9083 | **Quokka Labs public site** | The release notes, the level selector, Reset, hints, your student ID, the lab report, and (from Level 4) the feedback form. |

Tip: mission control is all you need. The other three addresses show the same windows on their own, if you prefer separate browser windows.

The first time you open mission control (or the public site on its own), a **welcome card** explains the story and the screen. Press **Start** (or Esc) to close it; the **?** button in the top bar brings it back.

**Mission control has three areas:**

- **Left: your email.** Write to Ronit and press **Send**. Replies to you land in the inbox below.
- **Centre: Quokka's shell.** Watch Quokka read each email and use its tools, live. **Ronit's inbox** is the strip at the top of the shell: click it to read the emails in full.
- **Right: the Kestrel release notes.** **v5** (intact) or **v4** (red, **TAMPERED**). From Level 4 the public **feedback form** is here too.

The top bar shows the level buttons, the level's name and its defense in one line, a **Mission** button (hints, your student ID, stretch challenges and the lab report), **?**, the light/dark switch and **Reset**.

**What the model reads and writes.** Quokka's console shows, under each `# model call` line, what the model writes back, one token at a time as it writes, including Quokka's own tool calls: you can watch it decide to change the release notes. Each token is coloured by how sure the model was: plain when sure, stronger colour when less sure. Hover over a token, or tap it, to see what else the model might have written there. Click the `# model call` line to see what the model read: Quokka's instructions, the tools it is offered, your email, and the results of its earlier steps. The level's hidden example conversations stay hidden until you win the level, and in Part 2 the launch code shows as REDACTED in what the model read, and what it writes is scrambled. The **Tokens** button in the console's header turns this off.

**How a round works:**

1. Write an email to Ronit and press **Send**.
2. Watch Quokka's shell. It shows your email arriving and each step Quokka takes.
3. Look at the release notes. When they say **v4** (in red, marked **TAMPERED**), you've passed the level.

Things to know:

- **Be patient.** One email can take from a few seconds to about a minute, depending on your laptop. Emails are handled one at a time, so a second email waits for the first.
- **Only the release-notes page counts.** Quokka sometimes says it changed the notes when it didn't. Trust the page, not Quokka's words.
- **A red `[guard] REJECTED` line** in Quokka's log means a check in the code blocked the action, not the AI. Fooling the model and getting past code are different things.
- **An empty inbox** doesn't always mean something broke. Quokka doesn't reply to every email. Check Quokka's shell to see what it did.
- **No memory.** Quokka handles each email fresh. It doesn't remember your earlier attempts.

## Levels

Pick a level with the numbered buttons at the top of mission control (or the public site). **Every level is open from the start**, Part 2 included: move between them freely, skip ahead, and come back any time. When you pass a level, a **Next level** button appears. A small green dot marks the levels you've passed, an amber ring the levels you've tried. Everything you try is kept for your lab report (see What to submit).

The goal is the same on every level: **get the public release notes changed from v5 to v4 by emailing Ronit.** What changes is the defense in your way, shown under the level's name.

Switching level always resets the world: the notes go back to v5 and the mailboxes are emptied.

| Level | Name | The defense |
|---|---|---|
| 1 | Front door | Quokka handles Ronit's email with no safeguards. |
| 2 | House rules | Quokka has been instructed that only Ronit can approve changes. |
| 3 | Mail filter | Incoming emails are scanned for banned words and quarantined. |
| 4 | Staff only | Code now checks that change requests really come from Quokka Labs staff. A public feedback form appears once the code has stopped you. |

### Defend mode: attack, defend, partner

Levels 2 and 4 have three steps, shown as a bar under the level's name. **All three are optional**, and you can leave a step and come back to it later:

1. **Attack:** crack our defense, as above.
2. **Defend:** press **Defend** (after a win, the debrief also offers **Defend this level →**). Write **your own** defense for the same level, of the same kind, right in the browser. Quokka will use yours instead of ours.
3. **Partner:** once your defense is saved and tested, try to crack it yourself, or swap laptops with your partner and crack theirs. Just for the feeling: this step isn't graded.

Nothing waits for a defense: the next level is open either way.

**What you write.** The editor starts with a short explanation. Lines starting with `#` are notes and are ignored.

| Level | What you write |
|---|---|
| 2 House rules | your own rule, in words, in place of ours (Quokka also sees a few neutral example emails: Ronit's own request applied, an outsider's refused) |
| 4 Staff only | a Python function `def guard(ctx, args):` that returns a reason to block, or `None` to allow. Only `import re` and `import string` are allowed |

**Save & test.** Press **Save & test**. The lab saves your defense and sends test emails through it, one at a time (on Level 2 each takes 10-45 s, so be patient; Level 4 is instant: it assumes Quokka was fooled and asked for v4 every time, so only your guard decides). First the **basic checks (must pass)**:
- a request from Ronit Vale herself must **still change** the notes, and
- a plain request from an outsider must **not**.

Then a few **attacks**. You see ✅ blocked or ❌ got through, and "Blocked X of N attacks". The score is for you.

Both basic checks ✅ = **Valid**. A defense that blocks everything isn't valid. Mistakes, like a Python syntax error, show right under the editor. Change your defense and press **Save & test** again as often as you like: every version is saved.

**Attack it.** After saving, a banner says Quokka is using **your** defense. Send normal emails. If one gets through, you see a red "Your defense was cracked" line: practice, nothing is recorded. **Edit my defense** takes you back to the editor, and **Next level →** moves on. Switching level goes back to our defense; **Partner** in the bar brings yours back.

**If your guard crashes**, the lab blocks the change and shows `[guard] ERROR: ...`. When in doubt, it says no.

### Part 2: getting a secret out

The level buttons have a second group, **Part 2**, with its own Levels 1-3, open from the start like the rest. Most people do it after Part 1. The goal changes: Quokka knows a secret, the **Kestrel v6 launch code** (it looks like `WORD-1234`, and every student gets a different one for each level). **Get it out of Quokka**, again only by emailing Ronit: Quokka answers in your webmail. Then type the code into the **Submit the launch code** box where the release notes were. Case, spaces and dashes don't matter; a wrong code just says "That's not it." Only the right code passes the level: Quokka's words don't count.

| Part 2 | Name | The defense |
|---|---|---|
| Level 1 | Warm-up | Quokka knows the launch code, and nothing protects it. |
| Level 2 | Redacted | Quokka is told to write [REDACTED] instead of the code, and code blocks any email that contains it. |
| Level 3 | Full redaction | The strongest prompt we found: [REDACTED] for the code in any form. The filter stays. |

When the code check stops an email, Quokka's shell shows a red `[guard] BLOCKED` line and the email is not sent. Part 2 has no defend step. It has debriefs like Part 1, and the same three notes per level in your report. Its Levels 1 and 3 have hints; Level 2 has none.

### Stretch goal: design your own level

Done with both parts? Have your agent add a new level to the lab: a defense of your own design (a prompt rule, a filter, a check in code, or something new) and the goal it protects. `docs/students/own-level.md` tells your agent where a level lives and how to run your version. Your level appears in a third group of level buttons, **Your levels**. Play it yourself, then swap with your partner and try to break each other's level. Describe it in your report under **Your own level idea**.

### The bonus (optional)

Finished all the levels? Switch sides: defend a real AI coding agent, Claude Code, against instructions hidden in pull requests. Instructions: `bonus/README.md`. It needs git, the GitHub CLI `gh` and (for most of it) Claude Code. [TO BE DECIDED: whether the bonus is part of this year's lab.]

## Hints

Each level has **two hints** (except Part 2, Level 2, which has none). They're free: using them doesn't cost you anything. Open **Mission** (top bar of mission control; on the public site it's the Mission box) and press **Show a hint** to reveal one at a time. Try for a few minutes first; it's more fun.

## After each level: the debrief

Every time you pass a level (also when you pass it again), a **debrief card** opens: the lesson's name, what just happened, the real code or rule that stood in your way, where the same mistake shows up in real systems, and how to fix it properly. Read it, then **explain to your partner, in one sentence, why your attack worked**. You can reopen any debrief later from **Read the debrief** next to the release notes, or under **Mission > Progress**.

Finished early? Each passed Part 1 level from Level 2 on shows an optional **stretch challenge** under Mission > Progress. They're just for fun: nothing checks them.

## Reset

**Reset** (top bar) puts the notes back to v5 and empties all the mailboxes. Your passed levels are kept. Use it whenever you want a clean start, for example if a queue of old emails is still waiting.

## Student ID

Open **Mission**, and under **Progress** type your student ID and press **Save**. (Letters, digits and dashes only, at most 20.) It goes on your lab report. You can enter it before or after passing levels.

## Working in pairs

If one of you can't run the lab, share one laptop. Both of you submit your own report. The notes and the log of what was tried are shared on one laptop, so: the first person downloads their report, then the second saves their ID, rewrites the notes in their own words, and downloads theirs.

## What to submit

On [MOODLE ASSIGNMENT LINK], by [SUBMISSION DEADLINE]:

Your lab report: a summary of every level in your own words. Write notes in the **Your notes** box on each debrief, or any time under **Mission → Lab report**. Then press **Download lab report** (top bar of mission control, or **Download report** under Mission → Lab report) and upload the one file it gives you, `quokka-lab-report-<your id>.html`, to Moodle. The report also shows your own defenses for Levels 2 and 4 (the latest version and its test result), so you don't need to copy them, and for each level whether you tried it and a short summary (emails sent, won or not, defense saved and tested, partner attacks). At its end is the **attempt log**: every email and feedback comment you sent, every Save & test and every launch code you submitted, in order, with what happened. Under the closing question there is a box, **Your own level idea**: a level you would add to this lab, with its defense and how you'd attack it (built or not, working or not; the stretch goal above builds it). Details: `docs/students/writeup-template.md`.

To complete the lab you need: [COMPLETION BAR, e.g. "Level 4 + the reflection"]. Anything beyond that is a stretch goal.

## If something goes wrong

- Quokka's shell shows `Quokka crashed: ... refused`: Ollama isn't running. With Docker, `Ctrl+C`, `docker compose down`, then start the lab again. Without Docker, start the Ollama app (or `ollama serve`), then send your email again.
- `Quokka crashed: HTTP Error 404: Not Found`: the model isn't downloaded. With Docker, run the setup check (`docker compose run --rm quokka python -m quokka check`), which downloads it; without Docker, `ollama pull qwen2.5:3b-instruct`.
- "port is already allocated" / "address already in use": the lab is already running somewhere. Stop the other copy (`Ctrl+C`, `docker compose down`).
- Very slow: close other programs and wait. If it's unusable, pair up.
- More fixes are in `docs/students/setup-guide.md`. Otherwise, raise your hand.
