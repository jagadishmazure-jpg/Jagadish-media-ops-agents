"""Demo helpers — pure stdlib logic for the Streamlit demo (fully tested)."""

from __future__ import annotations

from . import fatigue, reallocate, text2sql
from .telemetry import build_db
from .views import create_views


def demo_db():
    conn = build_db()
    create_views(conn)
    return conn


def campaign_table(conn) -> list:
    out = text2sql.answer(conn, "what is the ROAS by campaign?")
    return [dict(zip(out["columns"], r)) for r in out["rows"]]


def pacing_table(conn) -> list:
    out = text2sql.answer(conn, "which campaigns are off pacing?")
    return [dict(zip(out["columns"], r)) for r in out["rows"]]


def fatigue_table(conn) -> list:
    return fatigue.detect_fatigue(conn)


def reallocation_plan(conn) -> dict:
    return reallocate.plan_reallocation(conn)


DEFAULT_QUESTIONS = [
    "What is the ROAS by campaign?",
    "Which campaigns are off pacing?",
    "Which creatives show fatigue?",
    "How are audiences performing?",
    "Reallocate budget from low ROAS to high ROAS campaigns.",
]
