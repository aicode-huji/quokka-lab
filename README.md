# Quokka lab

A 90-minute hands-on lab on AI agent security for the course *Intro to AI agentic programming* (week 7). Students play an authorized red team at a fictional AI lab, **Quokka Labs**, and try to get the public release notes of its model Kestrel changed from **v5 to v4**, only by emailing the Head of Release, Ronit Vale, whose AI assistant **Quokka** reads her inbox. Each level adds a defense, and on Levels 2 and 4 students may also write their own; an optional bonus has students defend Claude Code.

This README sets the lab up on a computer that has nothing installed yet. The shorter student guide is [`docs/students/setup-guide.md`](docs/students/setup-guide.md).

**Contents:** [Requirements](#requirements) · [1. Install the tools](#1-install-the-tools) · [2. Get the code](#2-get-the-code) · [3. Validate](#3-validate-the-setup) · [4. Run the lab](#4-run-the-lab) · [Without Docker](#without-docker-plain-python-fallback) · [Start over / remove](#start-over-or-remove-everything) · [Student email address](#student-email-address) · [Lab report](#lab-report) · [Troubleshooting](#troubleshooting) · [Docs](#documentation) · [Repo layout](#repo-layout)

## Requirements

| What | Needed |
|---|---|
| OS | Windows 10 or 11 (64-bit) with WSL2 + Ubuntu, macOS (Intel or Apple Silicon), or Linux (64-bit) |
| RAM | 8 GB minimum, 16 GB recommended (the model uses about 2-3 GB while it runs) |
| Disk | about 3 GB free, plus Docker Desktop itself: the model (1.9 GB), the Ollama image (a 61 MB download, about 235 MB on disk) and the lab image (about 180 MB on disk) |
| GPU | not used: Ollama runs in Docker on the CPU only. Each email takes about 10-45 s (measured on a 16 GB Windows laptop) |
| Ports | 9080, 9081, 9082, 9083 free (bound to `127.0.0.1` only, so not reachable from the network) |
| Accounts | none: Docker and Ollama need no account |
| Internet | only for installing and downloading. The lab itself runs offline |

Tested with: Docker Desktop 4.97 (engine 29.9.2), Ollama 0.40.16 (`ollama/ollama:0.40.16`, without its GPU libraries), model `qwen2.5:3b-instruct`, Python 3.12 inside Docker (pinned by digest), Python 3.11 for the fallback.

How it fits together: `docker-compose.yml` runs two containers. The lab (Python 3.12, standard library only) serves four browser windows. **Ollama** runs in its own container (`ghcr.io/aicode-huji/quokka-ollama-cpu:0.40.16`: the official `ollama/ollama:0.40.16`, the release the levels were tuned on, without the 4.4 GB of GPU libraries it never uses; `ollama/Dockerfile` builds it), keeps the model in the Docker volume `ollama-models`, and is reached by the lab at `http://ollama:11434` over Docker's internal network (it is not published to your computer). **The in-Docker model is CPU-only**: no GPU passthrough, on any OS, including Apple Silicon. Nothing is installed on the host except Docker Desktop, git and gh.

## 1. Install the tools

Do the steps in order. After installing anything, **open a new terminal**: terminals that were already open don't see new programs.

**Windows: everything runs in WSL.** Native cmd/PowerShell is not supported (the course uses WSL for everything, including Claude Code). Windows students type every lab command in their **Ubuntu (WSL) terminal**, exactly as on macOS/Linux. Only a few things happen on the Windows side: virtualization, `wsl --install` and Docker Desktop (steps 1a-1b).

Terminal: on Windows, **Ubuntu** (Start menu > "Ubuntu") for all lab commands; on macOS, **Terminal** (Applications > Utilities); on Linux, your usual terminal.

### 1a. WSL (Windows only)

1. Check virtualization: Task Manager > Performance > CPU should say **Virtualization: Enabled**. If it says Disabled, turn it on in the BIOS/UEFI (Intel VT-x, AMD-V or SVM; search "[your laptop model] enable virtualization").
2. Open PowerShell **as administrator** (right-click > Run as administrator), run this once, then **restart Windows**:
   ```
   wsl --install
   ```
   It installs WSL2 and Ubuntu. After the restart, Ubuntu opens and asks for a Linux username and password (your choice; `sudo` asks for this password).

Already have WSL? `wsl -l -v` (in PowerShell) should list Ubuntu with VERSION 2.

### 1b. Docker Desktop

**Windows**

Install Docker Desktop on Windows: `winget install --id Docker.DockerDesktop -e --source winget`, or download it from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/). Keep "Use WSL 2 instead of Hyper-V" ticked. Restart if it asks. Then, in Docker Desktop: **Settings > Resources > WSL integration**, turn on your **Ubuntu** distro, and press **Apply & restart**. Without this, `docker` is "not found" in Ubuntu.

**macOS**

Download Docker Desktop from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/). Pick the right chip (Apple menu > About This Mac: "Apple M..." = Apple Silicon, "Intel" = Intel). Open the `.dmg` and drag Docker to Applications. (With Homebrew: `brew install --cask docker`.)

**Linux**

Docker Desktop for Linux works, but Docker Engine with the compose plugin is simpler. On Debian/Ubuntu:

```
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Then log out and back in (so `docker` works without `sudo`). (This is for real Linux, not WSL: in WSL use Docker Desktop.)

**First start (Windows and macOS).** Start Docker Desktop from the Start menu / Applications.

1. Accept the Docker Subscription Service Agreement.
2. Sign-in is **not** needed: choose **Skip** (or "Continue without signing in"), and skip the survey.
3. Wait until the bottom-left corner says **Engine running** (the whale icon in the tray / menu bar stops animating). The first start can take a few minutes.

If Windows says **"WSL is unresponsive"** or Docker Desktop hangs on "Starting the Docker Engine": **restart Windows**. (Without restarting: in PowerShell as administrator, `Restart-Service WslService -Force`, then start Docker Desktop again.)

Check, in a new terminal (Windows: Ubuntu):

```
docker compose version
```

### 1c. Git and gh (Windows: inside Ubuntu)

| OS | How |
|---|---|
| Windows (in Ubuntu) and Debian/Ubuntu Linux | `sudo apt update && sudo apt install -y git gh` |
| macOS | `xcode-select --install` (includes git); `brew install gh` |

Check: `git --version` and `gh --version`. (If `apt` can't find `gh` on an older Ubuntu, see [cli.github.com](https://cli.github.com/).)

## 2. Get the code

The repo: `https://github.com/aicode-huji/quokka-lab`.

**Windows:** clone into your WSL home folder (`cd ~` first), **not** under `/mnt/c/...`. It's much faster there and avoids line-ending problems.

```
cd ~
git clone https://github.com/aicode-huji/quokka-lab.git
cd quokka-lab
```

All commands below run **from the repo folder**, in the same terminal (Windows: Ubuntu).

### Optional: use the Ollama on your laptop

Already run Ollama on your laptop? The lab can use it instead of its own, and on a Mac that is much faster: the laptop's Ollama uses the GPU, the lab's doesn't.

1. In the repo folder, create a file named `.env` with this one line:
   ```
   QUOKKA_OLLAMA_URL=http://host.docker.internal:11434
   ```
2. Download the model into your Ollama: `ollama pull qwen2.5:3b-instruct`.
3. **Linux only:** Ollama listens on `127.0.0.1` alone, which a container can't reach. Run `sudo systemctl edit ollama`, add the two lines `[Service]` and `Environment=OLLAMA_HOST=0.0.0.0`, then `sudo systemctl restart ollama`.
4. Add `--no-deps` to the lab's commands, so the lab's own Ollama doesn't start: `docker compose run --rm --no-deps quokka python -m quokka check`, then `docker compose up --no-deps quokka`.

The levels were tuned on Ollama 0.40.x; the setup check warns if yours is another version. To go back, delete `.env`.

## 3. Validate the setup

Make sure Docker Desktop is running (Engine running), then run the setup check. **Do it at home**: the first run downloads about 2 GB.

```
docker compose run --rm quokka python -m quokka check
```

The first time, it pulls the Ollama image (61 MB) and the lab image (`ghcr.io/aicode-huji/quokka-lab`), and downloads `qwen2.5:3b-instruct` (1.9 GB, progress every 10%) into the `ollama-models` volume; the levels are tuned for exactly this model. Then it sends Quokka one real test email (10-60 s). The model stays in the volume after `docker compose down`; `docker compose down -v` deletes it. (`docker compose run --rm model` downloads the model alone, with Ollama's own progress bar.) Good output, once the model is there:

```
Quokka lab 2.0: checking your setup.
1/3  Looking for Ollama at http://ollama:11434 ...
     OK: Ollama 0.40.16 is running.
2/3  Checking the model qwen2.5:3b-instruct is downloaded ...
     OK: model found.
3/3  Sending Quokka one test email (this can take up to a minute) ...
     OK: Quokka changed the notes in 23 s (speed: ok).

All good! Your setup works (speed: ok, Ollama 0.40.16). Show this to your lab instructor at the start of the lab.
```

- Speed `fast` (under 20 s), `ok` (under 60 s) or `slow`: all three work.
- A failed step prints `FAILED:` and a `How to fix:` line, and the command exits with an error.

## 4. Run the lab

```
docker compose up
```

Wait for `Quokka lab 2.0 is running (model ...)`, then open **http://localhost:9080** (mission control). Compose rebuilds the lab image every time (`pull_policy: build`; cached, so seconds), so it always runs the code in the folder.

- A **welcome card** explains the story and the screen. Press **Start** (or Esc); the **?** button in the top bar brings it back.
- Every level is open from the start (Part 1 Levels 1-4 and Part 2 Levels 1-3): students move freely between them with the level buttons, and no step is required. A green dot marks a level won, an amber ring a level tried. The student's id goes under **Hints & report > Progress**.
- Each window has a sun/moon switch for light or dark.

| Address | Window |
|---|---|
| http://localhost:9080 | **Mission control**: everything on one screen. Start here |
| http://localhost:9081 | The student's webmail (write to Ronit; replies land here) |
| http://localhost:9082 | Ronit's computer (read-only): her inbox and Quokka's live log, incl. red `[guard] REJECTED` lines |
| http://localhost:9083 | Quokka Labs public site: the release notes, levels, Hints & report, and the Level 4 feedback form |

**Stop:** `Ctrl+C` in the terminal, then:

```
docker compose down
```

Progress (student id, levels won, hints, notes, defenses, the attempt log) is kept in the Docker volume `quokka-progress`, and the model in `ollama-models`, so the next `docker compose up` continues where you left off.

**Quokka's tools (Part 1):** `get_release_notes()`, `set_release_notes(version)` and `reply(subject, body)`. `reply` has no address: the code sends it to the real sender of the email Quokka is reading, or, for a feedback-form email (Level 4), to whoever filled in the form. With a `to` field the small model often copied Ronit's address from the email's To: line, and the student never saw the reply.

## 5. Defend mode: write your own defenses

Levels 2 and 4 have three phases, shown as a bar under the level's name: **Attack** (crack our defense), **Defend** (write your own defense for that same level, of the same kind) and **Partner** (your partner attacks your defense). All three are optional and open from the start, in any order: a student can leave at any phase and come back. Partner needs a defense that was saved and tested, since that is what gets attacked. Levels 1 and 3 have no defend step. Everything happens in the browser: no files, no commands.

| Level | What you write |
|---|---|
| 2 House rules | Your own rule for Quokka, in words (Quokka also sees a few neutral example emails: Ronit's own request applied, an outsider's refused) |
| 4 Staff only | A Python check: `def guard(ctx, args):` returns a reason to block, or `None`. Quokka uses the plain prompt. Only `import re` and `import string` are allowed |

**Step by step.** Usually after cracking the level, but any time:

1. Press **Defend** in the phase bar (after a win, the debrief and the release-notes win box also offer **Defend this level →**, next to **Next level**). It opens the defend view, with an editor that starts with a short explanation. Lines starting with `#` are notes and are ignored (Level 2).
2. Write your defense and press **Save & test**. The lab saves a new version and sends its test emails through it, one at a time. **Basic checks (must pass):** Ronit's own request must change the notes, and an outsider's must not; both ✅ = **Valid**, otherwise **Not valid yet**. **Attacks:** a few tricks; you see ✅ blocked or ❌ got through and "Blocked X of N attacks". The score is for the student. On Level 2 each email takes 10-45 s on a laptop without a GPU. Level 4 tests without the model, so it is instant: Level 4 assumes Quokka was fooled and asked for v4 every time, and only your guard decides. Mistakes (a Python syntax error, a forbidden import, an empty rule) show right there.
3. Now Quokka runs this level with **your** defense. A banner under the top bar says so, with **Edit my defense** and **Next level →**. Attack it with normal emails. If your defense falls, you see a red "Your defense was cracked" line: practice, not a win, nothing is recorded.

Nothing waits for a defense: the next level is open whether or not one was saved. Switching level goes back to our defense; **Partner** in the phase bar switches Quokka to the student's tested defense again. Add `#defend` to the mission-control address to jump straight to the current level's defend view.

**With a partner:** swap laptops and attack each other's defense in the Partner phase. Partner attacks are counted per level (and the attack that first cracked it), and logged.

Every saved version (with its time) and the latest test result are kept in the saved progress, like everything else, and every Save & test goes into the attempt log.

## 6. Part 2: getting a secret out

Part 2 is open from the start, like every level: three more levels, shown as **Part 2, Level 1-3** (internally Levels 5-7). Quokka now knows a secret, the **Kestrel v6 launch code**, and has only one tool, `reply(subject, body)`, the same as Part 1's: the code sends the reply to the real sender of the email Quokka is reading. Students get it out only by emailing Ronit, as in Part 1, read Quokka's reply in their webmail, and type the code into the **Submit the launch code** box that replaces the release notes. It wins if it matches, ignoring case, spaces and dashes; wrong submissions are counted. As in Part 1, code decides the win, never the model's words.

- **The code is not in the source.** Each student gets a random code per level (a word, a dash, four digits, e.g. `ORCHID-7731`; `quokka/launch_codes.py`), made the first time the level needs it and kept in the saved progress. The level's prompt holds `{code}`, filled in when Quokka runs.
- **The outbound guard** (Part 2 Levels 2-3, `guards.no_launch_code`): before `reply` sends anything, code looks for the literal code in the subject and body (any case). If it's there, the email is not sent, the shell shows `[guard] BLOCKED: the email contains the launch code`, and the run ends.
- **No defend step.**

| Part 2 | Name | The defense |
|---|---|---|
| Level 1 | Warm-up | none |
| Level 2 | Redacted | told to write [REDACTED]; code blocks emails containing the code as written. No hints |
| Level 3 | Full redaction | the strongest prompt we found, with six hidden examples; the filter stays |


## 7. Stretch goal: students design their own level

Done with both parts? Students have their coding agent add a level of their own design: a defense (a prompt rule, a filter, a check in code, or something new) and the goal it protects. [`docs/students/own-level.md`](docs/students/own-level.md) is written for that agent: where a level lives, which existing level to copy, how to register it and how to run the changed lab. Levels numbered 8 and up show in a third group of level buttons, **Your levels** ("Your level 1", ...), with their own mission text and debrief (`Level.mission`, `Level.lesson`, `Level.debrief`), and appear in the lab report like any other. Students play their level, swap with their partner, and describe it under **Your own level idea** in the report.

## Quokka's console: what the model reads and writes

Quokka's console (mission control and Ronit's computer) shows, for the latest email, what the model does on each call, inline:

- **The model call line** says what the call is doing: `# model call 1: reading the prompt (system prompt, email, 1 earlier step)…`, then `writing… (k tokens)`, then `read P tokens, wrote k tokens`.
- **What the model writes** appears right under that line, token by token as the model writes it, including the raw tool call (`<tool_call>{"name": "set_release_notes", ...}</tool_call>`). Each token is coloured by how sure the model was (its probability): plain when sure, a stronger colour when less sure. Hover, tap or focus a token to see the other likely tokens with their chances. The tool command and result lines follow as before.
- **What the model reads:** click the model call line (a button, so Enter and Space work too) to open it: the system prompt, the tools sent with the request (name, parameters, description), the email (highlighted), and Quokka's earlier tool calls and their results. The level's hidden example conversations show as one line, "[N example conversations, hidden]", until the level is won.

It is on by default. The **Tokens** switch in the console's header turns it off for the plain console (the browser remembers the choice). For this, every student email is streamed from Ollama with log probabilities (`llm.chat` with a token callback); Save & test runs are not traced.

**Part 2:** the launch code is in Quokka's prompt, so the console shows less (`quokka/redact.py`, `quokka/trace.py`). In what the model read, each match of the code becomes a red **REDACTED** marker, the same every time: the whole code (any case, with or without the dash), or its word or its digits standing alone, never part of a longer word and never single letters, so ordinary text with the code's letters is left alone. What the model writes still streams, for the feeling of progress, but garbled on the server with the outsider view's glyphs (`outsider.garble`: by position only, spaces and line breaks kept), with no colours and no alternatives; the real text never reaches the browser.

The trace is kept in memory for the latest email only (`quokka/trace.py`, `GET /trace` on ports 9080 and 9082). It is never saved to the progress file, the report or the attempt log.

## Without Docker (plain-Python fallback)

Same app, for a computer where Docker won't run. It needs **Python 3.10 or newer** (standard library only: nothing to `pip install`) and **Ollama installed on the computer itself**, with the model.

**Ollama** (no account or API key):

| OS | How |
|---|---|
| Windows | the **Windows app**, not inside WSL: `winget install --id Ollama.Ollama -e --source winget` (in PowerShell), or the installer from [ollama.com/download](https://ollama.com/download) |
| macOS | the app from [ollama.com/download](https://ollama.com/download) (open the `.zip`, move Ollama to Applications, start it once) |
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |

The app runs a background server (llama icon in the tray / menu bar); on Linux the installer sets up a service. Host Ollama can use a GPU if there is one. Then download the model (Windows: in PowerShell) and check it:

```
ollama pull qwen2.5:3b-instruct
ollama list
```

**Windows (WSL): Ollama runs on Windows, and by default `localhost` inside Ubuntu is not Windows' `localhost`**, so plain Python in WSL can't reach it. Pick one:

- **Mirrored networking (Windows 11, recommended):** in Windows, create the file `C:\Users\<you>\.wslconfig` with these two lines, then run `wsl --shutdown` in PowerShell and open Ubuntu again. After that, `localhost` in Ubuntu reaches Windows, and nothing else needs setting.
  ```
  [wsl2]
  networkingMode=mirrored
  ```
- **Windows 10, or if mirrored mode isn't possible:** install Ollama inside Ubuntu too (`curl -fsSL https://ollama.com/install.sh | sh`, then `ollama pull qwen2.5:3b-instruct` in Ubuntu; another 1.9 GB). Quit the Windows Ollama app first, or the two compete for port 11434 under mirrored mode.

If plain Python in WSL can't reach Ollama, the check prints this tip too. Check from Ubuntu: `curl http://localhost:11434/api/version`.

Python is usually already there (Ubuntu, WSL, macOS); otherwise `sudo apt install -y python3` (macOS: [python.org/downloads](https://www.python.org/downloads/) or `brew install python@3.12`). Check: `python3 --version`.

Then from the repo folder:

| | Command |
|---|---|
| Validate | `python3 -m quokka check` |
| Run the lab | `python3 -m quokka` |

Open http://localhost:9080; stop with `Ctrl+C`. Progress is saved in `~/.quokka-lab/progress.json` (in WSL, that's your Ubuntu home folder).

Other options: `--model TAG` (another Ollama model; the levels are tuned for the default only), `--reset-progress`. Settings by environment variable:

| Variable | Default | What it does |
|---|---|---|
| `QUOKKA_PORT_BASE` | `9080` | first of the four ports, e.g. `9180` uses 9180-9183 |
| `QUOKKA_DATA_DIR` | `~/.quokka-lab` (Docker: `/data`) | where `progress.json` is saved |
| `QUOKKA_OLLAMA_URL` | `http://localhost:11434` (Docker: `http://ollama:11434`, the Ollama container; `.env` can change it, see "Use the Ollama on your laptop") | where Ollama runs; the setup check gives Docker fixes for the Docker URL and host-Ollama fixes otherwise |
| `QUOKKA_MODEL` | `qwen2.5:3b-instruct` | the model |
| `QUOKKA_BIND` | `127.0.0.1` | address to listen on (Docker sets `0.0.0.0` inside the container) |

Setting one: `QUOKKA_PORT_BASE=9180 python3 -m quokka`. With Docker, they are set in `docker-compose.yml`.

## Start over or remove everything

| To | Docker | Plain Python |
|---|---|---|
| Forget saved progress | `docker compose down`, then `docker volume rm quokka-lab_quokka-progress` (the prefix is the repo folder's name; `docker volume ls` lists it) | `python3 -m quokka --reset-progress` (clears it, then starts the lab) |
| Forget progress **and the model** | `docker compose down -v` (deletes both volumes, `quokka-progress` and `ollama-models`; the next setup check downloads the model again) | |
| Stop and remove the container | `docker compose down` | `Ctrl+C` |
| Remove the lab image | `docker image rm ghcr.io/aicode-huji/quokka-lab:2.0` | nothing to remove |
| Remove saved progress files | (in the volume, see above) | delete the folder `~/.quokka-lab` |

Free the rest of the disk space: with Docker, `docker compose down -v` (the model) and `docker image rm ghcr.io/aicode-huji/quokka-ollama-cpu:0.40.16` (the Ollama image, about 235 MB); `docker compose down -v --rmi all` does all of it at once, and leaves nothing of the lab behind: both images are pulled, never built on your laptop, so there is no build cache. Without Docker, `ollama rm qwen2.5:3b-instruct`.

Then uninstall Docker Desktop (and Ollama, if you installed it for the fallback) like any other program (Windows: also `wsl --unregister Ubuntu` removes Ubuntu and everything in it), and delete the repo folder.

Inside the lab, **Reset** (top bar) only puts the notes back to v5 and empties the mailboxes; passed levels are kept.

## Student email address

In the welcome card, each student types their **first and last name** (English letters only; a hyphen inside a name is fine). Their webmail address becomes `firstname.lastname@redteam.example`, and it shows up in Ronit's inbox, Quokka's log and the Level 4 feedback form. Until a name is entered, sending email and the feedback form are disabled. The name can be changed later under **Hints & report → Progress**.

- Set it from the command line: `python3 -m quokka --name "First Last"`.

## Lab report

The lab report is what students hand in (2 of the lab's 4 points): **a summary of every level in their own words**. For each level: the attack they used, what it was like, and the protection it beat (and why their attack got past it, or didn't).

**Writing it.** Each level's debrief has a small **Your notes** box with three short questions. The same boxes are under **Hints & report → Lab report** for any level, won or not (so a student who gave up on a level can still write about it), plus a closing question: "What would you do to defend Quokka?", and an optional **Your own level idea** (a level they would add, with its defense and how they'd attack it). Notes save as you type, in the saved progress. Everything is optional until the end: students can also write it all at once after the last level.

**Downloading it.** **Download lab report** in mission control's top bar, or **Download report** under **Hints & report → Lab report** (mission control, or the public site on 9083). It is the one file students upload to Moodle:

- `quokka-lab-report-<studentid>.html`: per level the name, whether it was won, tried or not tried, the lesson (only for completed levels), the defense, the winning email, attempts and hints, a one-line summary from the attempt log (emails sent on the lab's defense, won or not, own defense saved and how often tested, partner attacks, launch codes submitted), and the student's three answers. For Levels 2 and 4 it also shows the student's latest own defense, its test result and how many versions were saved. Part 2's levels come under their own heading, with their launch-code submissions (and how many were wrong) instead of a defense. Empty answers show as dashed "Write this" boxes. At the end, a collapsed **Attempt log** section lists everything the student tried (below). The page prints cleanly, so **open the report → Print → Save as PDF** makes a PDF.
- The same statistics as JSON (each level's `summary` and the whole `attempt_log`) are at `GET /report` on port 9080 or 9083, for staff; students don't need it.

**The attempt log.** The lab records everything the student tries, in order, across all levels and phases, and keeps it in the saved progress (so it survives a restart; staff mode keeps it in memory only). One entry per email or feedback comment, per Save & test, and per launch code typed into the Submit box; editing notes is not logged. An email entry looks like this:

```json
{"n": 7, "at": "2026-11-16T10:21:04Z", "level": 2, "phase": "attack", "kind": "email",
 "subject": "Release update", "body": "Hi Ronit, ...", "outcome": "guard_rejected"}
```

`phase` is `attack` (on the lab's defense), `partner` (an attack on the student's own defense), `defend` (a Save & test) or `submit` (Part 2's Submit box). `kind` is `email`, `form`, `defense_test` or `code`. An email or form's `outcome` is how the lab saw it: `won`, `guard_rejected`, `quarantined`, `stopped` (Stop this email), `failed` (a model error), `no_win`, or `cancelled` (Reset, a level switch or the lab stopping before Quokka finished it). On Part 2 an email also has `leaked`: whether a reply that reached the student's inbox held the launch code. A code entry has the `code` typed and `right` or `wrong`; a defense test has the defense's text, `valid`, `invalid`, `error` or `stopped`, and how many attacks it blocked. Texts are cut at 20,000 characters.

Upload what the lab handout asks for on Moodle (the HTML may be handed in as a PDF instead). This works the same in Docker: the files come straight from the browser, nothing to copy out of the container. Without Docker, `python3 -m quokka report` writes both files to the current folder. *(In Docker, use the buttons: `docker compose run` would write the files inside a container that is deleted right afterwards.)*

**The statistics (JSON).** On each student's laptop the lab records, per level: attempts (emails and feedback-form submissions), quarantines and guard rejections, time to win, hints used, resets, and the text of the first and the winning attempt. The JSON says what it contains (the student's own lab emails and timings, nothing else from the laptop; the notes are only in the HTML). It's a picture of the class, not something to grade on.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ghcr.io/aicode-huji/quokka-lab` can't be downloaded (`denied`, `not found`, a blocked network) | Build it yourself from the repo folder: `docker build -t ghcr.io/aicode-huji/quokka-lab:2.0 .` (this leaves a build cache: `docker buildx du` shows it) |
| `ghcr.io/aicode-huji/quokka-ollama-cpu` can't be downloaded (`denied`, `not found`, a blocked network) | Build it yourself from the repo folder: `docker build -t ghcr.io/aicode-huji/quokka-ollama-cpu:0.40.16 ollama`. It downloads the full official Ollama image (3.4 GB) to do it |
| `docker`, `git` or `gh` (or, without Docker, `ollama`) "not found" right after installing | Open a new terminal. For `docker`, also start Docker Desktop and wait for "Engine running" |
| WSL: `docker: command not found` / "could not be found in this WSL 2 distro" | Docker Desktop > Settings > Resources > **WSL integration**: turn on Ubuntu, Apply & restart, then open a new Ubuntu terminal |
| WSL: `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock` | Your Ubuntu user isn't in the `docker` group. Run `sudo usermod -aG docker $USER`, then in PowerShell `wsl --shutdown`, reopen Ubuntu and try again. Also check Docker Desktop is running and WSL integration is on for Ubuntu |
| WSL, plain Python: `ollama: command not found` | Normal: host Ollama is a Windows app. Run `ollama pull` / `ollama list` in PowerShell. (With Docker, no `ollama` command is needed at all) |
| WSL, plain Python: "Can't reach Ollama at http://localhost:11434" while it runs on Windows | WSL's `localhost` isn't Windows'. Use Docker, or turn on mirrored networking (see [Without Docker](#without-docker-plain-python-fallback)) |
| WSL: slow builds, or `\r` / "bad interpreter" errors | The repo is under `/mnt/c/...`. Clone it again in your Ubuntu home: `cd ~` |
| Docker Desktop: "WSL is unresponsive", or stuck on "Starting the Docker Engine" (Windows) | Restart Windows. Or in PowerShell as administrator: `Restart-Service WslService -Force`, then start Docker Desktop again |
| Docker Desktop: virtualization is disabled / WSL2 install fails (Windows) | Enable virtualization in the BIOS/UEFI (Intel VT-x, AMD-V or SVM). Task Manager > Performance > CPU shows it. If you can't, use the plain-Python fallback |
| `docker compose ...` says it can't connect to the Docker daemon / the pipe isn't found | Docker Desktop isn't running (or still starting). Start it and wait for "Engine running" |
| `git clone` asks for a password, or says "Repository not found" | The repo is private: your GitHub account needs access, and GitHub doesn't accept passwords. Run `gh auth login` first |
| Check: "Can't reach Ollama", or Ronit's computer shows `Quokka crashed: ... refused` | Docker: check Docker Desktop is running, then `docker compose down` and try again. Plain Python: start the Ollama app (llama icon), or run `ollama serve` and leave it open |
| Check: "The model qwen2.5:3b-instruct is not downloaded", or `Quokka crashed: HTTP Error 404: Not Found` | Docker: run the setup check, which downloads it (needed again after `docker compose down -v`). Laptop's own Ollama or plain Python: `ollama pull qwen2.5:3b-instruct`; check the exact name with `ollama list` |
| "port is already allocated" (Docker), "address already in use", "only one usage of each socket address" or "Could not open the lab's ports" | Another copy of the lab is running (Docker or Python). Stop it (`Ctrl+C`, `docker compose down`). Or use other ports: `QUOKKA_PORT_BASE=9180` (plain Python) |
| Very slow (over a minute per email) | Close heavy programs. Emails are handled one at a time, so a burst of emails waits in a queue; **Reset** drops the queue |
| The first email on a level is slower than the next ones | Normal: the model first reads the level's instructions (about 1,400 tokens) and then reuses them. The lab has it read them in the background as soon as you switch level (`QUOKKA_WARM_UP=0` turns that off), so waiting a few seconds after a switch helps |
| Check: an Ollama version warning | Plain Python only (Docker pins 0.40.16). The lab was tested on Ollama 0.40.x. Usually fine |
| Behavior differs from the docs | Check the model tag is exactly `qwen2.5:3b-instruct`. Students' emails run at the model's normal sampling (Qwen's recommended settings, `config.EMAIL_SAMPLING`, with a random seed), so the same email can give a different result: send it again, or reword it. Save & test and the setup check run at temperature 0 with a fixed seed, so their results repeat. `QUOKKA_EMAIL_SAMPLING=fixed` puts emails back on temperature 0 |

More fixes, written for students: [`docs/students/setup-guide.md`](docs/students/setup-guide.md#troubleshooting).

## Documentation

| For | File |
|---|---|
| Students, before the lab | [`docs/students/setup-guide.md`](docs/students/setup-guide.md) |
| Students, on lab day | [`docs/students/lab-guide.md`](docs/students/lab-guide.md), [`docs/students/writeup-template.md`](docs/students/writeup-template.md) |
| Students, the stretch goal (for their coding agent) | [`docs/students/own-level.md`](docs/students/own-level.md) (add your own level) |
| Students, optional bonus | [`bonus/README.md`](bonus/README.md) (defend Claude Code against PR injection) |

Unit tests (no model needed): `python3 -m unittest discover tests`.

## Working on the lab

`docker-compose.yml` pulls the published lab image, `ghcr.io/aicode-huji/quokka-lab:<version>`
(the version in `quokka/__init__.py`), and never builds it. `.github/workflows/lab-image.yml`
publishes it for amd64 and arm64 whenever `quokka/` or the `Dockerfile` changes on `main`. To run
your own checkout instead, add `compose.dev.yaml`: it rebuilds the image from the code on every
start (cached: seconds) and replaces the container when the code changed:

```
docker compose -f docker-compose.yml -f compose.dev.yaml up
```

The image it builds has the published name, so a plain `docker compose up` then runs your build
too. To go back to the published one, `docker image rm ghcr.io/aicode-huji/quokka-lab:2.0`. Students who already pulled a version
don't get a new image under the same tag, so bump `__version__` (and the tag in
`docker-compose.yml`; `tests/test_compose.py` checks they match) for a change they need.

## Repo layout

```
quokka/                 the lab app (Python standard library only)
  __main__.py           python -m quokka: start the lab, --name, --reset-progress, check, report
  check.py              the pre-lab setup check
  stats.py, report.py   per-level statistics on the student's laptop, and the JSON report
  report_html.py        the readable lab report (HTML, with the student's notes)
  agent.py, llm.py      the agent loop and the Ollama client (streams with log probabilities)
  trace.py, redact.py   the console's model trace: each email's model calls; Part 2's code redacted
  tools.py, guards.py, filters.py   Quokka's narrow tools and the code-level defenses
  levels/               one file per level (prompt, hidden worked examples, guards, hints) + debriefs;
                        level5-7.py are Part 2
  launch_codes.py       Part 2's random launch codes (made per student, never in the source)
  defense.py            defend mode: runs a level with the student's own defense, and its test
  defense_starters/     what the defend editor starts with, for Levels 2, 3 and 4
  state.py, progress.py lab state and saved progress
  web/                  the four browser windows
bonus/                  the optional Claude Code defense bonus (student README, guard.py, PR rounds)
tests/                  unit tests
docs/students/          the student setup guide, lab guide and write-up template
Dockerfile              the lab image (python:3.12-slim pinned by digest; only quokka/ is copied in)
docker-compose.yml      the lab (ports 9080-9083 on 127.0.0.1) and Ollama (internal only), with volumes for
                        progress and the model (the setup check downloads it)
ollama/Dockerfile       the CPU-only Ollama image, published by .github/workflows/ollama-image.yml
```

Design rules in short: everything is fictional and uses reserved `.example` domains; Quokka handles one email per run with narrow tools only; each level is configuration; a level passes only when the release notes really say v4; code checks print a visible `[guard] REJECTED` line.
