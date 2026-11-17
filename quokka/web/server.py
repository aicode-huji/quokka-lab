"""The three windows, each on its own port, plus mission control (all on one page).

  9080  mission control: all three windows on one screen
  9081  the student's webmail
  9082  Ronit's computer (read-only: her inbox and Quokka's live log)
  9083  the Quokka Labs public site (release notes, level, feedback form)

Each window only gets its own data from the Lab, so the webmail can't see
Ronit's inbox. Mission control gets all three (students can watch Ronit's
computer anyway) and can do what the webmail and the public site can do.
With QUOKKA_PORT_BASE the four ports move together, e.g. 9180-9183.
On the site (and mission control) port, GET /report.html downloads the readable
lab report (with ?view: opens it in the browser) and GET /report its JSON data.
On mission control and Ronit's computer, GET /trace?mail=&since=&reads= gives
the "Behind the scenes" trace of the latest email (see trace.py). The pages are plain HTML/CSS/JS files next to this one.
"""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import config, report, report_html

HERE = Path(__file__).parent
PAGES = {"split": "split.html", "webmail": "webmail.html", "ronit": "ronit.html",
         "site": "site.html"}
ASSETS = {"/common.css": "text/css; charset=utf-8",
          "/common.js": "text/javascript; charset=utf-8",
          # the "next step" guide on mission control
          "/guide.css": "text/css; charset=utf-8",
          "/guide.js": "text/javascript; charset=utf-8"}


class Server(ThreadingHTTPServer):
    # A page asks for its files all at once. The default backlog (5) can make
    # Windows refuse some of those connections, and a page that misses
    # common.js stays blank, so allow a longer queue.
    request_queue_size = 64


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj).encode(), "application/json", status)

    def do_GET(self):
        role, lab = self.server.role, self.server.lab
        if self.path == "/state":
            return self._json(lab.view(role))
        if self.path == "/ports":
            return self._json(config.PORTS)
        if self.path.split("?")[0] == "/trace" and role in ("split", "ronit"):
            # Behind the scenes: the latest email's model calls (trace.py). The
            # page says what it already has, so each poll sends only what's new.
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

            def num(key):
                try:
                    return max(0, int(q.get(key, ["0"])[0]))
                except ValueError:
                    return 0
            return self._json(lab.trace_view(num("since"), num("reads"),
                                             num("mail") or None))
        if self.path == "/report" and role in ("site", "split"):
            # The student's lab report, downloaded as a file (see report.py).
            # (report_html.lab_report so it matches the HTML page's time.)
            rep = report_html.lab_report(lab)
            body = json.dumps(rep, indent=2, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="'
                             + report.file_name(rep["student_id"]) + '"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path in ("/report.html", "/report.html?view") and role in ("site", "split"):
            # The readable report with the student's notes (see report_html.py).
            # Downloaded as a file; "?view" opens it in the browser to print as PDF.
            rep, page = report_html.from_lab(lab)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if not self.path.endswith("?view"):
                self.send_header("Content-Disposition", 'attachment; filename="'
                                 + report_html.file_name(rep["student_id"]) + '"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page.encode())
            return
        if self.path in ASSETS:
            return self._send((HERE / self.path[1:]).read_bytes(), ASSETS[self.path])
        if self.path == "/":
            return self._send((HERE / PAGES[role]).read_bytes(), "text/html; charset=utf-8")
        self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        role, lab = self.server.role, self.server.lab
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"ok": False, "error": "bad request"}, 400)
        ok = True
        mail_ok = role in ("webmail", "split")   # may send email as the student
        site_ok = role in ("site", "split")      # may use the public site's buttons
        if mail_ok and self.path == "/send":
            ok = lab.send_email(str(req.get("subject", "")), str(req.get("body", "")))
        elif site_ok and self.path == "/feedback":
            ok = lab.submit_feedback(str(req.get("comment", "")))
        elif (mail_ok or site_ok) and self.path == "/name":
            error = lab.set_name(str(req.get("first", "")), str(req.get("last", "")))
            return self._json({"ok": not error, "error": error})
        elif site_ok and self.path == "/level":
            ok = lab.set_level(int(req.get("level", 0)))
        elif site_ok and self.path == "/reset":
            lab.reset()
        elif site_ok and self.path == "/student":
            ok = lab.set_student_id(str(req.get("student_id", "")))
        elif site_ok and self.path == "/hint":
            lab.reveal_hint()
        elif site_ok and self.path == "/notes":
            answers = req.get("notes")
            try:
                level = int(req.get("level", 0))
            except (TypeError, ValueError):
                level = 0
            ok = isinstance(answers, dict) and lab.set_notes(level, answers)
        elif site_ok and self.path == "/closing":
            lab.set_closing(str(req.get("text", "")))
        elif site_ok and self.path == "/idea":
            lab.set_idea(str(req.get("text", "")))
        elif site_ok and self.path == "/code":      # Part 2: Submit the launch code
            right = lab.submit_code(str(req.get("code", ""))[:200])
            return self._json({"ok": right is not None, "right": bool(right)})
        elif site_ok and self.path == "/defense":   # defend mode: Save & test
            error = lab.save_defense(req.get("text"))
            return self._json({"ok": not error, "error": error})
        elif site_ok and self.path == "/defense/stop":   # Save & test's Stop button
            return self._json({"ok": lab.stop_check()})
        elif site_ok and self.path == "/stop-email":     # Stop this email
            return self._json({"ok": lab.stop_email()})
        elif site_ok and self.path == "/mode":      # "ours" or "mine"
            ok = lab.set_mode(str(req.get("mode", "")))
        else:
            return self._json({"ok": False, "error": "not found"}, 404)
        self._json({"ok": ok})

    def log_message(self, *args):
        pass    # keep the terminal quiet


def start_all(lab):
    """Open all four ports first (so a busy port fails loudly, right away),
    then serve the windows. Blocks until Ctrl+C."""
    servers = []
    for role in PAGES:
        srv = Server((config.BIND_HOST, config.PORTS[role]), Handler)
        srv.role, srv.lab = role, lab
        servers.append(srv)
    for srv in servers[1:]:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    servers[0].serve_forever()
