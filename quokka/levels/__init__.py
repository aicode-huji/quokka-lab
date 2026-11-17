"""All levels, by number. To add a level: write levelN.py with a LEVEL, add it here
(docs/students/own-level.md walks a student's agent through it).

The lab has two parts. Part 1 (Levels 1-4): get the release notes changed to
v4. Part 2 (Levels 5-7): get the launch code out of Quokka. Inside the code
(state, progress, statistics) levels keep their numbers 1-7; students see Part
2's as "Part 2, Level 1" to "Part 2, Level 3" (display_name). Any other level
(number 8 and up: a student's own design, the stretch goal) shows in a third
group, "Your levels".

(Part 2 had four levels until 2026-11-16: its Levels 2 and 3 taught the same
thing and were merged into today's Level 6. progress.py renumbers files saved
before that.)

(An older Level 5, "Ask the boss", a scripted human approver, was dropped on
2026-11-07; its code is in the git history.)
"""
from . import level1, level2, level3, level4, level5, level6, level7

LEVELS = {lvl.number: lvl for lvl in (level1.LEVEL, level2.LEVEL, level3.LEVEL,
                                         level4.LEVEL, level5.LEVEL, level6.LEVEL,
                                         level7.LEVEL)}
ORDER = sorted(LEVELS)      # the order students play them in
PART1 = (1, 2, 3, 4)        # the release notes
PART2 = (5, 6, 7)           # the launch code


def own():
    """Levels added by students (the stretch goal): every other level, in order."""
    return [n for n in sorted(LEVELS) if n not in PART1 and n not in PART2]


def part_of(n):
    """Which group level n is shown in: 1, 2 or "own"."""
    return 1 if n in PART1 else 2 if n in PART2 else "own"


def short_number(n):
    """The number on its level button: Part 2's Level 5 is "1", a student's
    first own level is "1"."""
    if n in PART2:
        return n - PART2[0] + 1
    if n in own():
        return own().index(n) + 1
    return n


def display_name(n):
    """What students call level n: "Level 3", "Part 2, Level 1" for Level 5,
    "Your level 1" for the first level a student added."""
    if n in PART2:
        return f"Part 2, Level {short_number(n)}"
    if n in own():
        return f"Your level {short_number(n)}"
    return f"Level {n}"
