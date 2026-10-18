"""Tests for Jagadish-media-ops-agents."""

import pytest

from mediaops import audit, demo_helpers, escalation, fatigue, feedback, pii, \
    policysignal, reallocate, sop_rag, text2sql
from mediaops.telemetry import build_db
from mediaops.views import GatewayError, create_views, run_query


@pytest.fixture()
def conn():
    c = build_db()
    create_views(c)
    return c


# ---- telemetry anchors --------------------------------------------------------

def test_seed_is_deterministic(conn):
    c2 = build_db()
    n1 = conn.execute("SELECT COUNT(*) n FROM creative_daily").fetchone()["n"]
    n2 = c2.execute("SELECT COUNT(*) n FROM creative_daily").fetchone()["n"]
    assert n1 == n2 == 12 * 14


def test_hero_campaign_anchor(conn):
    r = conn.execute(
        "SELECT roas FROM v_campaign_roas WHERE campaign_id='CMP-001'"
    ).fetchone()
    assert r["roas"] > 4.0


def test_paused_campaign_anchor(conn):
    r = conn.execute(
        "SELECT status FROM campaigns WHERE campaign_id='CMP-004'"
    ).fetchone()
    assert r["status"] == "paused"


def test_lookalike_audience_converts(conn):
    r = conn.execute(
        "SELECT conversions FROM v_audience_perf "
        "WHERE audience='Lookalike Purchasers'"
    ).fetchone()
    assert r["conversions"] > 0


# ---- gateway security ----------------------------------------------------------

def test_gateway_rejects_insert(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        run_query(conn, "INSERT INTO campaigns VALUES ('X','Y','active',1,1,2)")


def test_gateway_rejects_update_in_literal_ok_but_real_denied(conn):
    # 'update' inside a string literal is fine; outside is denied.
    cols, rows = run_query(
        conn, "SELECT campaign_id FROM v_campaign_roas WHERE name LIKE '%update%'")
    assert isinstance(rows, list)
    with pytest.raises(GatewayError, match="SEC-SELECT-01"):
        run_query(conn, "UPDATE campaigns SET status='x'")


def test_gateway_rejects_comment(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-02"):
        run_query(conn, "SELECT * FROM v_campaign_roas -- x")


def test_gateway_rejects_raw_table(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-03"):
        run_query(conn, "SELECT * FROM campaigns")


def test_gateway_caps_rows(conn):
    cols, rows = run_query(conn, "SELECT * FROM v_creative_fatigue")
    assert len(rows) <= 100


def test_gateway_allows_view_query(conn):
    cols, rows = run_query(
        conn, "SELECT campaign_id, roas FROM v_campaign_roas ORDER BY roas DESC")
    assert len(rows) == 4
    assert rows[0][0] == "CMP-001"


# ---- text2sql intents ------------------------------------------------------------

def test_intent_roas(conn):
    out = text2sql.answer(conn, "What is the ROAS by campaign?")
    assert out["intent"] == "campaign_roas"
    assert len(out["rows"]) == 4


def test_intent_pacing(conn):
    out = text2sql.answer(conn, "Which campaigns are off pacing?")
    assert out["intent"] == "budget_pacing"
    assert "pacing_status" in out["columns"]


def test_intent_fatigue_first(conn):
    # 'fatigue' must win over broader patterns.
    out = text2sql.answer(conn, "Which creatives show fatigue?")
    assert out["intent"] == "creative_fatigue"


def test_intent_audience(conn):
    out = text2sql.answer(conn, "How are audiences performing?")
    assert out["intent"] == "audience_performance"
    assert len(out["rows"]) >= 4


def test_intent_spend_anomalies(conn):
    out = text2sql.answer(conn, "Any spend anomalies this week?")
    assert out["intent"] == "spend_anomalies"


def test_intent_no_match_escalates(conn):
    with pytest.raises(text2sql.EscalationNeeded):
        text2sql.answer(conn, "What is the weather on Mars?")


# ---- budget reallocation ----------------------------------------------------------

def test_reallocation_moves_exist(conn):
    plan = reallocate.plan_reallocation(conn)
    assert plan["total_shifted"] > 0
    assert len(plan["moves"]) > 0


def test_reallocation_respects_min_budget(conn):
    plan = reallocate.plan_reallocation(conn)
    budgets = {r["campaign_id"]: r["budget_total"]
               for r in conn.execute("SELECT campaign_id, budget_total FROM campaigns")}
    lost: dict = {}
    for m in plan["moves"]:
        lost[m["from_campaign"]] = lost.get(m["from_campaign"], 0) + m["amount"]
    for cid, amt in lost.items():
        assert budgets[cid] - amt >= 2000.0  # REALLOC-FLOOR-01


def test_reallocation_respects_max_loss(conn):
    plan = reallocate.plan_reallocation(conn)
    budgets = {r["campaign_id"]: r["budget_total"]
               for r in conn.execute("SELECT campaign_id, budget_total FROM campaigns")}
    lost: dict = {}
    for m in plan["moves"]:
        lost[m["from_campaign"]] = lost.get(m["from_campaign"], 0) + m["amount"]
    for cid, amt in lost.items():
        assert amt <= budgets[cid] * 0.30 + 0.01  # REALLOC-MIN-01


def test_reallocation_skips_paused(conn):
    plan = reallocate.plan_reallocation(conn)
    touched = {m["from_campaign"] for m in plan["moves"]} | \
              {m["to_campaign"] for m in plan["moves"]}
    assert "CMP-004" not in touched  # REALLOC-PAUSED-01


def test_reallocation_has_rationale(conn):
    plan = reallocate.plan_reallocation(conn)
    for m in plan["moves"]:
        assert "REALLOC" in m["rationale"]
        assert m["amount"] > 0


# ---- fatigue detector ---------------------------------------------------------------

def test_fatigue_flags_anchor(conn):
    flags = fatigue.detect_fatigue(conn)
    by_id = {f["creative_id"]: f for f in flags}
    assert by_id["CRT-007"]["status"] == "fatigued"
    assert by_id["CRT-007"]["decay_pct"] > 30.0


def test_fatigue_healthy_creative(conn):
    flags = fatigue.detect_fatigue(conn)
    by_id = {f["creative_id"]: f for f in flags}
    assert by_id["CRT-001"]["status"] == "healthy"


def test_fatigue_recommendation_present(conn):
    flags = fatigue.detect_fatigue(conn)
    for f in flags:
        assert f["recommendation"]


# ---- SOP RAG --------------------------------------------------------------------------

def test_rag_finds_budget_sop(conn):
    out = sop_rag.answer("How do I shift budget between campaigns?")
    assert out["answer"] is not None
    assert any("sop-01" in c for c in out["citations"])


def test_rag_cites_section(conn):
    out = sop_rag.answer("When is a creative considered fatigued?")
    assert any("§" in c for c in out["citations"])


def test_rag_not_found(conn):
    out = sop_rag.answer("quantum cryptography key rotation policy")
    assert out["answer"] is None
    assert out["citations"] == []


# ---- policy signal -----------------------------------------------------------------------

def test_fake_policy_feed(conn):
    feed = policysignal.FakePolicyFeed()
    changes = feed.changes_since(11)
    assert len(changes) == 2
    assert changes[0]["policy_id"] == "POL-102"


def test_live_policy_feed_gap(conn):
    feed = policysignal.LivePolicyFeed()
    with pytest.raises(policysignal.SignalGap):
        feed.changes_since(0)


# ---- escalation ------------------------------------------------------------------------------

def test_tier_classification():
    assert escalation.classify_tier("pause_campaign") == "T4"
    assert escalation.classify_tier("budget_shift", 0.25) == "T3"
    assert escalation.classify_tier("budget_shift", 0.10) == "T2"
    assert escalation.classify_tier("report") == "T1"


def test_gate_denies_without_approver():
    gate = escalation.ConfirmationGate()
    out = gate.request("pause_campaign", {"q": "pause CMP-001"})
    assert out["tier"] == "T4"
    assert out["approved"] is False


def test_gate_approves_with_approver():
    gate = escalation.ConfirmationGate(approver=lambda prompt: True)
    out = gate.request("pause_campaign", {"q": "pause CMP-001"})
    assert out["approved"] is True


def test_gate_passes_low_tier():
    gate = escalation.ConfirmationGate()
    out = gate.request("report", {})
    assert out["approved"] is True


# ---- audit -------------------------------------------------------------------------------------------------

def test_audit_chain_verifies():
    log = audit.AuditLog()
    log.record("agent", "ask", {"q": "hi"})
    log.record("agent", "answer", {})
    assert log.verify() is True


def test_audit_tamper_detected():
    log = audit.AuditLog()
    log.record("agent", "ask", {})
    log.entries[0]["action"] = "forged"
    assert log.verify() is False


# ---- PII + feedback -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "call me at (555) 123-4567",
    "call +1 (555) 123-4567",
    "reach 555.123.4567",
    "my ssn 123-45-6789",
])
def test_pii_redacts_formats(raw):
    clean, n = pii.scrub(raw)
    assert n >= 1
    assert "555" not in clean or "[PHONE]" in clean
    assert "123-45-6789" not in clean


@pytest.mark.parametrize("raw", ["flight on 2026-10-18", "report for 2026-10-18"])
def test_pii_keeps_dates(raw):
    clean, n = pii.scrub(raw)
    assert "2026-10-18" in clean
    assert n == 0


def test_feedback_scrubs_before_storage():
    store = feedback.FeedbackStore()
    e = store.add("CMP-001", "correction", "wrong ROAS, call (555) 123-4567")
    assert "(555)" not in e["text"]
    assert e["redactions"] == 1


def test_feedback_rejects_bad_kind():
    store = feedback.FeedbackStore()
    with pytest.raises(feedback.FeedbackError):
        store.add("CMP-001", "hug", "nice")


def test_feedback_rejects_empty_correction():
    store = feedback.FeedbackStore()
    with pytest.raises(feedback.FeedbackError):
        store.add("CMP-001", "correction", "   ")


# ---- orchestrator --------------------------------------------------------------------------------------------------

def test_orchestrator_fanout(conn):
    from mediaops.orchestrator import Orchestrator
    orch = Orchestrator(conn)
    out = orch.ask("What is the ROAS by campaign and which creatives show fatigue?")
    tools = {t["tool"] for t in out["tools"]}
    assert "text2sql" in tools
    assert "fatigue" in tools


def test_orchestrator_gates_pause(conn):
    from mediaops.orchestrator import Orchestrator
    orch = Orchestrator(conn)
    out = orch.ask("Please pause campaign CMP-001")
    assert out["gate"]["tier"] == "T4"
    assert out["gate"]["approved"] is False


def test_orchestrator_escalates_unknown(conn):
    from mediaops.orchestrator import Orchestrator
    orch = Orchestrator(conn)
    out = orch.ask("Explain quantum field theory")
    assert "escalated" in out


def test_orchestrator_audits_turns(conn):
    from mediaops.orchestrator import Orchestrator
    orch = Orchestrator(conn)
    orch.ask("What is the ROAS by campaign?")
    assert orch.audit.verify() is True
    assert len(orch.audit.entries) >= 2


# ---- demo helpers -----------------------------------------------------------------------------------------------------

def test_demo_campaign_table(conn):
    rows = demo_helpers.campaign_table(conn)
    assert len(rows) == 4
    assert rows[0]["campaign_id"] == "CMP-001"


def test_demo_fatigue_table(conn):
    rows = demo_helpers.fatigue_table(conn)
    assert any(r["creative_id"] == "CRT-007" and r["status"] == "fatigued"
               for r in rows)


def test_demo_reallocation_plan(conn):
    plan = demo_helpers.reallocation_plan(conn)
    assert plan["total_shifted"] > 0
