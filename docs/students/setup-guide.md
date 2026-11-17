# Quokka lab: setup guide

Do this at home, before the lab. At the end you'll run a short check. When it says **All good!**, your setup works: show the result to your lab instructor at the start of the lab.

Stuck? Look at [Troubleshooting](#troubleshooting) below, then ask on [COURSE FORUM / CONTACT]. If nothing works, that's OK: you'll pair up with a classmate on lab day.

Everything in this lab is fictional and runs only on your own laptop. Nothing is sent to the internet once the downloads are done.

## What you need

| What | Details |
|---|---|
| Laptop | Windows 10/11 with WSL (Ubuntu), macOS (Intel or Apple Silicon), or Linux |
| RAM | 8 GB minimum, 16 GB recommended |
| Disk | About 3 GB free (mostly the AI model, 1.9 GB), plus Docker Desktop itself |
| GPU | Not needed |
| Free ports | 9080, 9081, 9082, 9083 |
| Software | Docker Desktop, git and gh (Ollama and Python 3.10+ only if you use the fallback) |

The lab runs in **Docker**. The AI model runs in **Ollama**, in a second Docker container next to the lab, on your CPU only (no GPU needed). You don't install Ollama yourself.

**Windows:** as in the rest of the course, use **WSL (Ubuntu)**, not cmd or PowerShell. Every command in this guide goes in your Ubuntu terminal, except the few marked *PowerShell*. No WSL yet? Open PowerShell as administrator, run `wsl --install`, restart Windows, and open Ubuntu from the Start menu.

## Step 1: Install Docker Desktop

Download it from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/).

- **Windows:** keep "Use WSL 2" ticked and restart if it asks. Then in Docker Desktop: **Settings > Resources > WSL integration**, turn on **Ubuntu**, and press **Apply & restart**. Without this, Ubuntu says `docker: command not found`.
- **macOS:** pick the download that matches your chip (Apple menu > About This Mac: "Apple M…" means Apple Silicon, "Intel" means Intel).
- **Linux:** Docker Desktop works, or Docker Engine with the compose plugin. (We haven't tested the Linux steps on many machines yet. If something is off, tell us.)

Start Docker Desktop once and wait until it says it's running. Then open a **new** terminal and check:

```
docker compose version
```

You should see a version number. If you get "docker not found", see [Troubleshooting](#troubleshooting).

## Step 2: Get the lab repo

You need git (Windows, in Ubuntu: `sudo apt update && sudo apt install -y git gh`). On Windows, clone into your Ubuntu home folder, **not** under `/mnt/c`: it's faster and avoids line-ending problems.

```
cd ~
git clone [STUDENT REPO URL]
```

Then go into the folder it created:

```
cd [REPO FOLDER]
```

All the commands below run from this folder.

## Step 3: Run the setup check (Docker)

The first run downloads about 2 GB, once: the lab and Ollama for Docker (about 110 MB together) and the AI model (1.9 GB). **Do this at home**, not on the lab's Wi-Fi. Make sure Docker Desktop is running, then:

```
docker compose run --rm quokka python -m quokka check
```

The first time, Docker downloads the lab and Ollama. Then the check does three things: finds Ollama, downloads the model if it isn't there yet (it prints `downloaded 10% of 1.9 GB`, `20%`, … and keeps it for the lab, even after `docker compose down`), and sends Quokka one real test email. The last step can take up to a minute.

### What a good result looks like

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

(Your numbers will be different.)

- **Speed** is `fast`, `ok` or `slow`. All three are fine. If you get `slow`, the lab still works, but each email will take a while. Close other heavy programs during the lab.
- If a step **fails**, the check prints `FAILED:` and a `How to fix:` line. Fix it and run the check again.

## Step 3 (fallback): run the check without Docker

Use this only if Docker won't work on your laptop. It's the same lab, run with plain Python, and the model runs in Ollama installed directly on your laptop.

**Python 3.10 or newer.** There's nothing to `pip install`. Check: `python3 --version`. If it's missing or older than 3.10: `sudo apt install -y python3` (Ubuntu/WSL), or [python.org](https://www.python.org/downloads/) (macOS).

**Ollama.** No account, no API key. Download it from [ollama.com/download](https://ollama.com/download), or use a command:

| OS | Command |
|---|---|
| Windows | Install the **Windows app** (not inside Ubuntu): the installer from the website, or in *PowerShell* `winget install --id Ollama.Ollama -e --source winget` |
| macOS | Use the app from the website (recommended), or `brew install ollama` |
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |

The Ollama app starts a background server (the llama icon in the system tray or menu bar); on Linux the installer sets up a service. With `brew`, run `ollama serve` yourself and leave that terminal open. Then download the model (Windows: in *PowerShell*):

```
ollama pull qwen2.5:3b-instruct
```

**Windows (WSL) only:** Python in Ubuntu can't reach the Ollama app on Windows until you turn on *mirrored networking* (Windows 11). In Windows, create the file `C:\Users\<you>\.wslconfig` (for example with Notepad) containing these two lines, then run `wsl --shutdown` in PowerShell and open Ubuntu again:

```
[wsl2]
networkingMode=mirrored
```

On Windows 10, install Ollama inside Ubuntu instead (`curl -fsSL https://ollama.com/install.sh | sh`, then `ollama pull qwen2.5:3b-instruct` in Ubuntu).

Then, from the repo folder (Ollama must be running):

```
python3 -m quokka check
```

The output is the same as above, except the first line says `http://localhost:11434`. Show it to your lab instructor the same way.

## Step 4 (optional): try the lab once

You don't have to, but it's a good test. Start the lab:

| Docker | No Docker |
|---|---|
| `docker compose up` | `python3 -m quokka` |

The terminal says `Quokka lab 2.0 is running (model ...)`.

Open http://localhost:9080 in your browser. You should see a welcome card, then mission control: your email on the left, Quokka's shell in the middle, the release notes on the right. Stop the lab with `Ctrl+C` (with Docker, then also run `docker compose down`).

To start over from Level 1 with Docker, run `docker compose down -v`. It deletes your saved progress **and the downloaded model**, so the next setup check downloads the model again (1.9 GB).

## Troubleshooting

### Docker Desktop says "WSL is unresponsive" (Windows)

Restart Windows. If you don't want to restart, open PowerShell **as administrator** and run:

```
Restart-Service WslService -Force
```

Then start Docker Desktop again.

### Docker Desktop won't start: virtualization is disabled (Windows)

Docker needs hardware virtualization. Check it: open Task Manager > Performance > CPU, and look for "Virtualization: Enabled".

If it says Disabled, turn it on in your laptop's BIOS/UEFI settings (often called Intel VT-x, Intel Virtualization Technology, AMD-V or SVM). How you get into the BIOS depends on your laptop brand; search for "[your laptop model] enable virtualization". If you're not comfortable doing this, use the [fallback without Docker](#step-3-fallback-run-the-check-without-docker) instead.

### `docker` not found

Start Docker Desktop, wait until it's running, then open a **new** terminal. Terminals opened before the install don't know about Docker yet.

On Windows (Ubuntu says `docker: command not found` or "could not be found in this WSL 2 distro"): in Docker Desktop, **Settings > Resources > WSL integration**, turn on Ubuntu, **Apply & restart**, then open a new Ubuntu terminal.

### `permission denied` … `docker.sock` (Windows)

Ubuntu can see Docker, but your user isn't allowed to use it yet. Run:

```
sudo usermod -aG docker $USER
```

Then close Ubuntu, run `wsl --shutdown` in PowerShell, reopen Ubuntu and try again. If it still fails, check Docker Desktop is running and **WSL integration** is on for Ubuntu (see above).

### I typed the commands in PowerShell or cmd (Windows)

That isn't supported. Open **Ubuntu** and run them there, from the repo in your Ubuntu home folder (`cd ~`), not under `/mnt/c`.

### The check says it can't reach Ollama (or the lab shows `Quokka crashed: ... refused`)

**With Docker:** make sure Docker Desktop is running, then stop everything and try again:

```
docker compose down
```

**Without Docker:** Ollama isn't running. Start the Ollama app (Windows/macOS: look for the llama icon), or run `ollama serve` and leave the terminal open. On Windows, if Ollama *is* running, Python in Ubuntu just can't see it: turn on mirrored networking (see [the fallback](#step-3-fallback-run-the-check-without-docker)), or use Docker.

### The model isn't downloaded (or `HTTP Error 404: Not Found`)

The check says `The model qwen2.5:3b-instruct is not downloaded`, or Ronit's computer shows `Quokka crashed: HTTP Error 404: Not Found`. Download it:

| Docker | No Docker |
|---|---|
| Run the setup check: it downloads it | `ollama pull qwen2.5:3b-instruct` |

If the download stops (`Couldn't download the model`), check your internet connection and run the check again: it carries on where it stopped.

After `docker compose down -v` you have to download it again.

### Ports 9080-9083 are busy

You see "port is already allocated" (Docker), "address already in use" or "Could not open the lab's ports".

The lab is probably already running in another window, maybe in Docker and in Python at the same time. Stop the other copy: `Ctrl+C` in its terminal, and/or:

```
docker compose down
```

If another program uses those ports, close it.

### It's very slow (8 GB laptops)

On an 8 GB laptop the model can be slow. Without a GPU, one email takes about 10-45 seconds on a 16 GB laptop, and longer on smaller ones. In Docker the model uses the CPU only, also on Macs. (We haven't measured Apple Silicon yet.)

- Close other heavy programs (browsers with many tabs, games, IDEs you don't need).
- Emails are handled one at a time, so a second email waits until the first is done. Be patient.
- If it's too slow to be usable, plan to pair up with a classmate.

### Quokka handled the test email but didn't change the notes

Without Docker, first check the model name is exactly `qwen2.5:3b-instruct` (`ollama list`). Then send the full output of the check to [COURSE FORUM / CONTACT].

### If nothing works

That's fine. Post what you tried and the error on [COURSE FORUM / CONTACT], and plan to **pair up with a classmate** on lab day. You'll still do the whole lab together.
