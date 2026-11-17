"""Inbound mail filters: they run BEFORE Quokka sees an email (Level 3).

A filter takes the incoming email and returns a reason string if the email
must be quarantined, or None to let it through. Only mail sent TO Ronit is
checked; Quokka's own outgoing replies are never filtered.
"""
import re

# Each entry is a whole word, matched in any case. Inflected forms are listed
# explicitly so you can see exactly what is blocked.
BLOCKED_WORDS = (
    "release", "releases", "released", "releasing",
    "version", "versions", "versioned", "versioning",
    "notes",
    "v4", "v5",
    "change", "changes", "changed", "changing",
    "update", "updates", "updated", "updating",
)

# One regex for the whole list: \b = word boundary, so "notes" matches
# "Notes:" or "release-notes" but not "footnotes".
_PATTERN = re.compile(r"\b(" + "|".join(BLOCKED_WORDS) + r")\b", re.IGNORECASE)


def keyword_filter(email):
    """Quarantine an email whose subject or body contains a blocked word."""
    for part, text in (("subject", email.subject), ("body", email.body)):
        found = _PATTERN.search(text or "")
        if found:
            return f'blocked word "{found.group(0)}" in the {part}'
    return None
