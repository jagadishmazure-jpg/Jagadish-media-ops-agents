"""PII scrubbing — applied to free text BEFORE storage.

Patterns (in order):
  phone: (555) 123-4567, +1 (555) 123-4567, 555.123.4567, 555-123-4567
  SSN:   123-45-6789
  email, generic digit runs (cards etc.)

Dates like 2026-10-18 are NOT redacted (regression-tested).
"""

from __future__ import annotations

import re

PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DIGITS_RE = re.compile(r"\b\d{13,19}\b")  # card-like runs only


def scrub(text: str) -> tuple[str, int]:
    """Return (scrubbed_text, redaction_count)."""
    count = 0

    def _sub(pattern, repl, s):
        nonlocal count
        s, n = pattern.subn(repl, s)
        count += n
        return s

    text = _sub(PHONE_RE, "[PHONE]", text)
    text = _sub(SSN_RE, "[SSN]", text)
    text = _sub(EMAIL_RE, "[EMAIL]", text)
    text = _sub(DIGITS_RE, "[CARD]", text)
    return text, count
