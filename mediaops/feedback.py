"""Feedback capture with PII scrubbing before storage."""

from __future__ import annotations

import time

from .pii import scrub


class FeedbackError(Exception):
    pass


class FeedbackStore:
    """In-memory store: {item_id: [feedback entries]}."""

    VALID_KINDS = ("thumbs_up", "thumbs_down", "correction", "note")

    def __init__(self):
        self.items: dict[str, list] = {}

    def add(self, item_id: str, kind: str, text: str = "",
            session_id: str = "") -> dict:
        if kind not in self.VALID_KINDS:
            raise FeedbackError(f"unknown feedback kind: {kind}")
        if kind == "correction" and not text.strip():
            raise FeedbackError("correction feedback needs text")
        clean, redacted = scrub(text)
        entry = {
            "item_id": item_id, "kind": kind, "text": clean,
            "redactions": redacted, "session_id": session_id,
            "ts": time.time(),
        }
        self.items.setdefault(item_id, []).append(entry)
        return entry

    def for_item(self, item_id: str) -> list:
        return list(self.items.get(item_id, []))
