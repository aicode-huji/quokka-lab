"""The Compose file pulls the published lab image; it never builds on a student's laptop.  Run:
    python -m unittest discover tests
"""
import re
import unittest
from pathlib import Path

from quokka import __version__

ROOT = Path(__file__).resolve().parent.parent
LAB_IMAGE = "ghcr.io/aicode-huji/quokka-lab"


def service(name):
    """The lines of one service's block in docker-compose.yml."""
    text = (ROOT / "docker-compose.yml").read_text()
    m = re.search(rf"^  {name}:\n((?:    .*\n|\s*\n)+)", text, re.M)
    assert m, f"no service {name!r}"
    return m.group(1)


class TestLabImage(unittest.TestCase):
    def test_compose_pulls_the_published_image_of_this_version(self):
        self.assertIn(f"    image: {LAB_IMAGE}:{__version__}\n", service("quokka"))

    def test_compose_does_not_build_it(self):
        # A build on the laptop leaves a build cache that `down --rmi all` doesn't remove.
        self.assertNotRegex(service("quokka"), r"(?m)^    build:")
        self.assertNotIn("pull_policy: build", service("quokka"))

    def test_workflow_publishes_the_same_name(self):
        wf = (ROOT / ".github/workflows/lab-image.yml").read_text()
        self.assertIn(f"REPO: {LAB_IMAGE}\n", wf)


if __name__ == "__main__":
    unittest.main()
