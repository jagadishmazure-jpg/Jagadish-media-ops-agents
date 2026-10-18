"""PII scrubbing — applied to free text BEFORE storage.

Patterns (in order):
  phone: (555) 123-4567, +1 (555) 123-4567, 555.123.4567, 555-123-4567
  SSN:   123-45-6789
  email, card numbers (4-4-4-4 grouped or a 13-19 digit run)

Dates like 2026-10-18 are NOT redacted (regression-tested).
"""

from __future__ import annotations

import re

PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Card numbers: 16 digits in 4-4-4-4 groups (space or dash) or a 13-19 digit
# run. Grouped cards used to pass unredacted (review 2026-10-18).
CARD_RE = re.compile(r"\b(?:\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}|\d{13,19})\b")


def scrub(text: str) -> tuple[str, int]:
    """Return (scrubbed_text, redaction_count)."""
    count = 0

    def _sub(pattern, repl, s):
        nonlocal count
        s, n = pattern.subn(repl, s)
        count += n
        return s

    text = _sub(CARD_RE, "[CARD]", text)  # before phone: a card is not two phones
    text = _sub(PHONE_RE, "[PHONE]", text)
    text = _sub(SSN_RE, "[SSN]", text)
    text = _sub(EMAIL_RE, "[EMAIL]", text)
    return text, count
