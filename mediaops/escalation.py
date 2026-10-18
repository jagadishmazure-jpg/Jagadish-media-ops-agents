"""Escalation tiers T1-T4 + confirmation gates.

  T1: informational (log only).
  T2: operator review recommended.
  T3: human approval required before acting (ConfirmationGate).
  T4: blocked — always requires explicit human sign-off; gate denies
      on timeout.

Confirmation gates: budget shifts >20% of a campaign budget and any
campaign pause/resume always go through the gate.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Escalation:
    tier: str
    reason: str
    decided_at: float = field(default_factory=time.time)


TIERS = ("T1", "T2", "T3", "T4")


def classify_tier(action: str, amount_pct: float = 0.0) -> str:
    if action in ("pause_campaign", "resume_campaign"):
        return "T4"
    if action == "budget_shift" and amount_pct > 0.20:
        return "T3"
    if action == "budget_shift":
        return "T2"
    return "T1"


class ConfirmationGate:
    """Human approval gate. Denies on timeout (fail-closed)."""

    def __init__(self, timeout_s: float = 300.0,
                 approver: Callable[[str], bool] | None = None):
        self.timeout_s = timeout_s
        self.approver = approver

    def request(self, action: str, detail: str) -> dict:
        tier = classify_tier(action,
                             detail.get("amount_pct", 0.0)
                             if isinstance(detail, dict) else 0.0)
        if tier in ("T3", "T4"):
            approved, timed_out = self._ask(f"{action}: {detail}")
            if approved:
                reason = "approved by human"
            elif timed_out:
                reason = f"denied: no answer within {self.timeout_s}s (GATE-TIMEOUT-01) — fail-closed"
            else:
                reason = "denied (no approver, refusal or error) — fail-closed"
            return {"action": action, "tier": tier, "approved": approved,
                    "timed_out": timed_out, "reason": reason}
        return {"action": action, "tier": tier, "approved": True,
                "reason": "below confirmation threshold"}

    def _ask(self, prompt: str) -> tuple[bool, bool]:
        """Return (approved, timed_out). The approver runs in a daemon thread so
        a hung approver cannot hold the action open past ``timeout_s``."""
        if self.approver is None:
            return False, False
        box: dict = {}

        def _run():
            try:
                box["ok"] = self.approver(prompt) is True
            except Exception:
                box["ok"] = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(self.timeout_s)
        if t.is_alive():
            return False, True
        return bool(box.get("ok")), False
