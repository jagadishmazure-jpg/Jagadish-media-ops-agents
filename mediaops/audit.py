"""Hash-chained audit log with tamper detection."""

from __future__ import annotations

import hashlib
import json
import time


class AuditLog:
    def __init__(self):
        self.entries = []
        self._prev = "GENESIS"

    def record(self, actor: str, action: str, detail: dict | None = None) -> dict:
        entry = {
            "seq": len(self.entries),
            "ts": time.time(),
            "actor": actor,
            "action": action,
            "detail": detail or {},
            "prev": self._prev,
        }
        body = json.dumps(entry, sort_keys=True, default=str)
        entry["hash"] = hashlib.sha256(
            (self._prev + body).encode()).hexdigest()
        self._prev = entry["hash"]
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        prev = "GENESIS"
        for e in self.entries:
            if e["prev"] != prev:
                return False
            body = json.dumps(
                {k: v for k, v in e.items() if k != "hash"},
                sort_keys=True, default=str)
            if hashlib.sha256((prev + body).encode()).hexdigest() != e["hash"]:
                return False
            prev = e["hash"]
        return True
