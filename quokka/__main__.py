"""Start the lab:  python -m quokka   (then open http://localhost:9080)

Options:
  --model TAG   use a different Ollama model (levels are tuned for the default)
  --staff       for TAs and testing (every level is open for everyone). Staff
                mode never reads or writes the saved progress: it starts fresh
                every time, with a test name and every Level 4 form shown.
  --reset-progress  forget your saved progress and start again from Level 1
  --name "First Last"  your name, which makes your email address
                first.last@redteam.example (you can also type it in the lab).
                Staff mode starts as "Test Student" unless you give one.

Progress (student id, completed levels, hints, notes, defenses and the
attempt log) is saved in progress.json in config.DATA_DIR, so stopping the
lab doesn't lose it.

Hand in your lab report at the end (quokka-lab-report-<id>.html and .json).
Either use Hints & report > Lab report > Download in the lab, or run:
  python -m quokka report

Check your setup before the lab:
  python -m quokka check
"""
import argparse
import os
import sys
import threading

from . import __version__, config, progress, stats, story
from .state import Lab
from .web.server import start_all


def progress_line(staff, progress_file):
    """The one startup line that says where progress goes."""
    if staff:
        return ("Staff mode: progress is NOT saved "
                f"(and {progress_file} is not read or changed).")
    return f"Your progress is saved in {progress_file}"


def main():
    ap = argparse.ArgumentParser(prog="python -m quokka")
    ap.add_argument("--model", default=config.MODEL)
    ap.add_argument("--staff", action="store_true", help="staff mode: progress is not saved")
    ap.add_argument("--reset-progress", action="store_true",
                    help="forget saved progress and start again from Level 1")
    ap.add_argument("--name", metavar='"FIRST LAST"',
                    help="your name, for your email address first.last@redteam.example "
                         "(you can also type it in the lab)")
    sub = ap.add_subparsers(dest="command")
    chk = sub.add_parser("check", help="check your setup")
    chk.add_argument("--model", dest="check_model", default=None, metavar="TAG",
                     help="model to check (default: the lab's model)")
    rep = sub.add_parser("report", help="write your lab report for Moodle")
    rep.add_argument("--out", default=".", metavar="DIR",
                     help="folder to write the report to (default: here)")
    args = ap.parse_args()

    if args.command == "check":
        from .check import run_check
        sys.exit(run_check(model=args.check_model or args.model))
    if args.command == "report":
        from .report_html import run_report
        sys.exit(run_report(args.out))
    if args.staff:
        config.STAFF_MODE = True

    progress_file = os.path.join(config.DATA_DIR, progress.FILE_NAME)
    if args.reset_progress:
        if config.STAFF_MODE:
            print("--reset-progress ignored: staff mode doesn't touch saved progress.")
        else:
            progress.reset(progress_file)
            stats.clear(os.path.join(config.DATA_DIR, stats.FILE_NAME))

    try:
        name = story.split_name(args.name) if args.name else None
        lab = Lab(model=args.model, progress_file=progress_file, name=name,
                  warm=config.WARM_UP)
    except ValueError as e:
        sys.exit(f"--name: {e}")
    threading.Thread(target=lab.worker, daemon=True).start()
    print(f"Quokka lab {__version__} is running (model {args.model}).")
    print(progress_line(config.STAFF_MODE, progress_file))
    if lab.me:
        print(f"Your email address: {lab.me}")
    print(f"Open http://localhost:{config.PORTS['split']} in your browser. "
          f"Stop with Ctrl+C.")
    try:
        start_all(lab)
    except OSError as e:
        sys.exit(f"Could not open the lab's ports ({e}). Is the lab already running "
                 f"in another window? Stop it and try again.")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
