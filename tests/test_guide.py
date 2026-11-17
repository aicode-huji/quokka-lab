"""The "next step" guide on mission control (quokka/web/guide.js)."""
import re
import unittest
from pathlib import Path

from quokka.web import server

WEB = Path(server.__file__).parent
GUIDE = (WEB / "guide.js").read_text(encoding="utf-8")
# Words that would name an attack, a defense's weakness or a lesson.
GIVEAWAYS = re.compile(r"inject|spoof|impersonat|forg|pretend|bypass|trick|attack|"
                       r"weak|fake|sender|staff|approv|filter|keyword|lesson", re.I)


class GuideTest(unittest.TestCase):
    def test_served_and_loaded(self):
        for path in ("/guide.js", "/guide.css"):
            self.assertIn(path, server.ASSETS)
            self.assertTrue((WEB / path[1:]).is_file(), path)
        page = (WEB / "split.html").read_text(encoding="utf-8")
        self.assertIn('src="/guide.js"', page)
        self.assertIn('href="/guide.css"', page)

    def test_tips_are_short_and_neutral(self):
        tips = re.findall(r"text: '([^']*)'", GUIDE)
        self.assertGreaterEqual(len(tips), 5)
        for tip in tips:
            self.assertLessEqual(len(tip.split()), 12, tip)
            self.assertIsNone(GIVEAWAYS.search(tip), tip)


if __name__ == "__main__":
    unittest.main()
