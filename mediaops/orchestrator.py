"""ReAct orchestrator with multi-intent fan-out.

Routes a question across tools (SQL intents, reallocation engine,
fatigue detector, SOP RAG, policy signal), audits every turn, and
escalates what it cannot answer. Refuses nothing domain-wise here —
media ops has no clinical/safety refusal class — but budget shifts
above the gate threshold and campaign pauses go through confirmation.
"""

from __future__ import annotations

from . import fatigue, reallocate, sop_rag, text2sql
from .audit import AuditLog
from .escalation import ConfirmationGate


class Orchestrator:
    def __init__(self, conn, policy_feed=None, approver=None):
        self.conn = conn
        self.policy_feed = policy_feed
        self.audit = AuditLog()
        self.gate = ConfirmationGate(approver=approver)

    def ask(self, question: str) -> dict:
        self.audit.record("orchestrator", "question", {"q": question})
        q = question.lower()
        result: dict = {"question": question, "tools": []}
        matched = False

        # Fan-out: SQL intents.
        try:
            sql_out = text2sql.answer(self.conn, question)
            result["tools"].append({"tool": "text2sql", **sql_out})
            self.audit.record("text2sql", sql_out["intent"],
                              {"rows": len(sql_out["rows"])})
            matched = True
        except text2sql.EscalationNeeded as e:
            result["tools"].append({"tool": "text2sql", "escalated": str(e)})

        # Reallocation engine.
        if "reallocat" in q or "shift budget" in q or "move spend" in q:
            matched = True
            plan = reallocate.plan_reallocation(self.conn)
            result["tools"].append({"tool": "reallocate", **plan})
            self.audit.record("reallocate", "plan",
                              {"moves": len(plan["moves"])})
            for m in plan["moves"]:
                # SOP-01: a single shift above 20% of *a* campaign's budget
                # (donor or recipient) needs approval; use the real size.
                pct = reallocate.move_pct(self.conn, m)
                g = self.gate.request("budget_shift", {"amount_pct": pct, "move": m})
                m["amount_pct"] = round(pct, 4)
                m["gate"] = g

        # Fatigue detector.
        if "fatigue" in q or "tired creative" in q or "ctr decay" in q:
            matched = True
            flags = fatigue.detect_fatigue(self.conn)
            bad = [f for f in flags if f["status"] == "fatigued"]
            result["tools"].append(
                {"tool": "fatigue", "flagged": bad, "checked": len(flags)})
            self.audit.record("fatigue", "scan", {"flagged": len(bad)})

        # SOP RAG.
        if "policy" in q or "sop" in q or "how should" in q or "process" in q:
            matched = True
            rag = sop_rag.answer(question)
            result["tools"].append({"tool": "sop_rag", **rag})

        # Policy signal.
        if "policy change" in q or "platform update" in q:
            matched = True
            if self.policy_feed is None:
                result["tools"].append(
                    {"tool": "policy_signal",
                     "gap": "no policy feed configured"})
            else:
                try:
                    changes = self.policy_feed.changes_since(0)
                    result["tools"].append(
                        {"tool": "policy_signal", "changes": changes})
                except Exception as e:
                    result["tools"].append(
                        {"tool": "policy_signal", "gap": str(e)})

        # Pause requests always gate.
        if "pause" in q and "campaign" in q:
            matched = True
            g = self.gate.request("pause_campaign", {"q": question})
            result["gate"] = g
            self.audit.record("gate", "pause_campaign", g)

        if not matched:
            result["escalated"] = "no tool matched; escalated to operator"
            self.audit.record("orchestrator", "escalate", {})
        return result
