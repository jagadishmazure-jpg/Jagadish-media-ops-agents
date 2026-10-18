"""Text-to-SQL: 5 fixed intents over the read-only views.

One simplified retry, then explicit escalation (EscalationNeeded) — never a
hallucinated query. All SQL runs through the hardened gateway in views.py.
"""

from __future__ import annotations

import re
import sqlite3

from .views import run_query


class EscalationNeeded(Exception):
    pass


def _intents():
    return [
        # specific intents first (ordering matters — see tests)
        ("creative_fatigue",
         re.compile(r"fatigue|decaying|worn out|ctr decay", re.IGNORECASE),
         lambda q: _creative_fatigue(q)),
        ("budget_pacing",
         re.compile(r"pacing|on track|overspend|underspend|budget.*(status|pace)", re.IGNORECASE),
         lambda q: _budget_pacing(q)),
        ("campaign_roas",
         re.compile(r"\broas\b|return on ad|revenue", re.IGNORECASE),
         lambda q: _campaign_roas(q)),
        ("audience_performance",
         re.compile(r"audience|segment", re.IGNORECASE),
         lambda q: _audience_performance(q)),
        ("spend_anomalies",
         re.compile(r"anomal|spike|unusual spend", re.IGNORECASE),
         lambda q: _spend_anomalies(q)),
    ]


def _campaign_roas(q: str) -> str:
    return ("SELECT campaign_id, name, status, total_spend, total_conversions, "
            "revenue, roas FROM v_campaign_roas ORDER BY roas DESC")


def _budget_pacing(q: str) -> str:
    return ("SELECT campaign_id, name, budget_total, spent_to_date, "
            "expected_spend, pacing_ratio, pacing_status "
            "FROM v_budget_pacing ORDER BY pacing_ratio DESC")


def _creative_fatigue(q: str) -> str:
    return ("SELECT creative_id, name, format, campaign_id, ctr_first7, "
            "ctr_last7, decay_pct, fatigued FROM v_creative_fatigue "
            "ORDER BY decay_pct DESC")


def _audience_performance(q: str) -> str:
    return ("SELECT audience, impressions, clicks, ctr, spend, conversions "
            "FROM v_audience_perf ORDER BY conversions DESC")


def _spend_anomalies(q: str) -> str:
    # Campaigns whose pacing ratio is far off 1.0 are the spend anomalies.
    return ("SELECT campaign_id, name, budget_total, spent_to_date, "
            "pacing_ratio, pacing_status FROM v_budget_pacing "
            "WHERE pacing_status != 'on_track'")


def answer(conn: sqlite3.Connection, question: str) -> dict:
    """Match one intent, run it, return rows. One retry, then escalate."""
    for name, pattern, build in _intents():
        if pattern.search(question):
            try:
                sql = build(question)
            except EscalationNeeded:
                try:
                    sql = _retry_broaden(name, question)
                except EscalationNeeded:
                    raise
            cols, rows = run_query(conn, sql)
            return {"intent": name, "sql": sql, "columns": cols, "rows": rows}
    raise EscalationNeeded(f"no intent matched: {question!r}")


def _retry_broaden(name: str, question: str) -> str:
    if name == "campaign_roas":
        return ("SELECT campaign_id, name, total_spend, roas "
                "FROM v_campaign_roas")
    raise EscalationNeeded(f"retry exhausted for intent {name}")
