"""Budget-reallocation engine (domain differentiator #1).

Shifts spend from low-ROAS campaigns to high-ROAS campaigns with
guardrails and a per-move rationale:

  REALLOC-MIN-01: no campaign may lose more than 30% of its budget.
  REALLOC-MAX-01: no campaign may gain more than 50% of its budget.
  REALLOC-FLOOR-01: every active campaign keeps a $2,000 minimum budget.
  REALLOC-PAUSED-01: paused campaigns are never touched.

Only active campaigns participate. Moves are computed from ROAS ranking:
the bottom half funds the top half, proportional to the ROAS gap.
"""

from __future__ import annotations

import sqlite3

MAX_LOSS_PCT = 0.30
MAX_GAIN_PCT = 0.50
MIN_BUDGET = 2000.0
SHIFT_PCT = 0.20  # fraction of donor budget moved per donor


def plan_reallocation(conn: sqlite3.Connection) -> dict:
    """Return {'moves': [...], 'total_shifted': float}.

    Each move: {from_campaign, to_campaign, amount, rationale}.
    Reads the v_campaign_roas view directly (engine read, not the
    capped planner gateway — engines must see every row).
    """
    rows = conn.execute(
        "SELECT campaign_id, name, status, total_spend, roas "
        "FROM v_campaign_roas"
    ).fetchall()
    active = [dict(r) for r in rows if r["status"] == "active"]
    if len(active) < 2:
        return {"moves": [], "total_shifted": 0.0,
                "note": "fewer than 2 active campaigns; nothing to reallocate"}

    ranked = sorted(active, key=lambda r: (r["roas"] or 0.0))
    donors = ranked[: len(ranked) // 2]
    recipients = ranked[len(ranked) // 2:]

    # Current budgets from the base table (engine read).
    budgets = {
        r["campaign_id"]: r["budget_total"]
        for r in conn.execute(
            "SELECT campaign_id, budget_total FROM campaigns")
    }

    moves = []
    gains: dict[str, float] = {r["campaign_id"]: 0.0 for r in recipients}
    for d in donors:
        cid = d["campaign_id"]
        budget = budgets[cid]
        amount = round(min(budget * SHIFT_PCT, budget * MAX_LOSS_PCT,
                           budget - MIN_BUDGET), 2)
        if amount <= 0:
            continue
        # Split the donor's shift across recipients by ROAS weight.
        total_roas = sum(r["roas"] or 0.0 for r in recipients) or 1.0
        for r in recipients:
            rcid = r["campaign_id"]
            if (r["roas"] or 0.0) <= (d["roas"] or 0.0):
                continue  # no gain from moving spend to an equal/lower ROAS (REALLOC-GAIN-01)
            share = round(amount * (r["roas"] or 0.0) / total_roas, 2)
            cap = budgets[rcid] * MAX_GAIN_PCT - gains[rcid]
            share = round(min(share, max(cap, 0.0)), 2)
            if share <= 0:
                continue
            gains[rcid] += share
            moves.append({
                "from_campaign": cid,
                "to_campaign": rcid,
                "amount": share,
                "rationale": (
                    f"REALLOC: move ${share:,.2f} from {cid} "
                    f"(ROAS {d['roas']}) to {rcid} (ROAS {r['roas']}); "
                    f"donor keeps >=70% of budget (REALLOC-MIN-01), "
                    f"recipient gain capped at 50% (REALLOC-MAX-01)"
                ),
            })
    total = round(sum(m["amount"] for m in moves), 2)
    return {"moves": moves, "total_shifted": total,
            "donors": len(donors), "recipients": len(recipients)}


def move_pct(conn: sqlite3.Connection, move: dict) -> float:
    """Size of one move as a share of the larger-affected campaign budget:
    max(amount / donor budget, amount / recipient budget)."""
    budgets = dict(conn.execute(
        "SELECT campaign_id, budget_total FROM campaigns WHERE campaign_id IN (?, ?)",
        (move["from_campaign"], move["to_campaign"])).fetchall())
    return max(move["amount"] / budgets[move["from_campaign"]],
               move["amount"] / budgets[move["to_campaign"]])
