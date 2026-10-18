"""Synthetic media ad-operations telemetry for fictional Velquist Media.

Deterministic (seed 42). Tables: campaigns, ad_sets, creatives,
creative_daily (14 days of impressions/clicks/spend/conversions).

Deterministic anchors (asserted in tests):
  * CMP-001 "Summer Launch" is the ROAS hero (ROAS > 4.0).
  * CRT-007 "Hero Video v3" shows creative fatigue: CTR decays >30%
    from the first 7 days to the last 7 days.
  * CMP-004 "Holiday Teaser" is paused.
  * Audience "Lookalike Purchasers" exists and converts.
"""

from __future__ import annotations

import random
import sqlite3

SEED = 42
DAYS = 14
AVG_ORDER_VALUE = 50.0

_CAMPAIGNS = [
    # (id, name, status, budget_total, start_day, end_day)
    ("CMP-001", "Summer Launch", "active", 50000.0, 1, 30),
    ("CMP-002", "Brand Awareness", "active", 30000.0, 1, 30),
    ("CMP-003", "Retargeting Push", "active", 20000.0, 5, 30),
    ("CMP-004", "Holiday Teaser", "paused", 10000.0, 20, 45),
]

_AD_SETS = [
    # (id, campaign_id, name, audience, budget)
    ("AS-001", "CMP-001", "Summer Prospecting", "18-34 Urban", 30000.0),
    ("AS-002", "CMP-001", "Summer Lookalike", "Lookalike Purchasers", 20000.0),
    ("AS-003", "CMP-002", "Brand Reach 25-44", "25-44 Suburban", 18000.0),
    ("AS-004", "CMP-002", "Brand Video", "18-34 Urban", 12000.0),
    ("AS-005", "CMP-003", "Cart Abandoners", "Site Visitors 30d", 12000.0),
    ("AS-006", "CMP-003", "Past Purchasers", "Lookalike Purchasers", 8000.0),
    ("AS-007", "CMP-004", "Holiday Early", "25-44 Suburban", 10000.0),
]

_CREATIVES = [
    # (id, ad_set_id, name, format, base_ctr, fatigued?)
    ("CRT-001", "AS-001", "Hero Video v1", "video", 0.022, False),
    ("CRT-002", "AS-001", "Static Banner A", "image", 0.015, False),
    ("CRT-003", "AS-002", "Hero Video v2", "video", 0.025, False),
    ("CRT-004", "AS-002", "Carousel Summer", "carousel", 0.018, False),
    ("CRT-005", "AS-003", "Brand Story 30s", "video", 0.012, False),
    ("CRT-006", "AS-003", "Brand Static", "image", 0.010, False),
    ("CRT-007", "AS-004", "Hero Video v3", "video", 0.025, True),  # fatigue anchor
    ("CRT-008", "AS-004", "Brand Banner B", "image", 0.011, False),
    ("CRT-009", "AS-005", "Abandoner Nudge", "image", 0.030, False),
    ("CRT-010", "AS-005", "Discount Video", "video", 0.028, False),
    ("CRT-011", "AS-006", "Loyalty Static", "image", 0.020, False),
    ("CRT-012", "AS-007", "Holiday Teaser", "video", 0.016, False),
]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    return con


def seed(con: sqlite3.Connection) -> None:
    rng = random.Random(SEED)
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE campaigns(
            campaign_id TEXT PRIMARY KEY, name TEXT, status TEXT,
            budget_total REAL, start_day INT, end_day INT);
        CREATE TABLE ad_sets(
            ad_set_id TEXT PRIMARY KEY, campaign_id TEXT, name TEXT,
            audience TEXT, budget REAL);
        CREATE TABLE creatives(
            creative_id TEXT PK, ad_set_id TEXT, name TEXT,
            format TEXT);
        CREATE TABLE creative_daily(
            creative_id TEXT, day INT, impressions INT, clicks INT,
            spend REAL, conversions INT);
        """.replace("TEXT PK", "TEXT PRIMARY KEY")
    )
    for c in _CAMPAIGNS:
        cur.execute("INSERT INTO campaigns VALUES (?,?,?,?,?,?)", c)
    for a in _AD_SETS:
        cur.execute("INSERT INTO ad_sets VALUES (?,?,?,?,?)", a)
    for cid, asid, name, fmt, _, _ in _CREATIVES:
        cur.execute(
            "INSERT INTO creatives VALUES (?,?,?,?)", (cid, asid, name, fmt)
        )
    for cid, asid, name, fmt, base_ctr, fatigued in _CREATIVES:
        for day in range(1, DAYS + 1):
            impressions = rng.randint(8000, 15000)
            # Fatigue anchor: CTR decays linearly from base to ~45% of base.
            ctr = base_ctr
            if fatigued:
                ctr = base_ctr * (1.0 - 0.55 * (day - 1) / (DAYS - 1))
            else:
                ctr = base_ctr * rng.uniform(0.9, 1.1)
            clicks = max(1, int(impressions * ctr))
            spend = round(impressions / 1000.0 * rng.uniform(8.0, 12.0), 2)
            conv_rate = 0.04 if "Lookalike" in asid or "AS-002" in asid or "AS-006" in asid else 0.025
            # Hero campaign converts better.
            if asid in ("AS-001", "AS-002"):
                conv_rate = 0.06
            conversions = max(0, int(clicks * conv_rate * rng.uniform(0.8, 1.2)))
            cur.execute(
                "INSERT INTO creative_daily VALUES (?,?,?,?,?,?)",
                (cid, day, impressions, clicks, spend, conversions),
            )
    con.commit()


def build_db() -> sqlite3.Connection:
    con = connect()
    seed(con)
    return con
