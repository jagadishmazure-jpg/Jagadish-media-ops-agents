"""Read-only views + SELECT-only gateway for media telemetry.

Four published views:
  v_campaign_roas   — spend, conversions, revenue, ROAS per campaign
  v_budget_pacing   — budget vs expected spend at day 14 of 30
  v_creative_fatigue— CTR first-7 vs last-7 days, decay %, fatigue flag
  v_audience_perf   — impressions/clicks/CTR/spend/conversions per audience

Gateway rules (cited in errors):
  SEC-SELECT-01: query must be a single SELECT (first keyword check).
  SEC-SELECT-02: no write/DDL keywords outside string literals, no
                 comments, no stacked statements.
  SEC-SELECT-03: every table named after FROM/JOIN must be a published
                 view (text allowlist); the SQLite authorizer in
                 ``authz.py`` is the backstop.

Row cap is enforced at fetch time with ``fetchmany(ROW_CAP + 1)`` —
never by rewriting LIMIT, and never with ``fetchall()`` on the
planner path (see docs/adr/0001-sqlite-authorizer-backstop.md).
"""

from __future__ import annotations

import re
import sqlite3

from .authz import views_only

ROW_CAP = 100

ALLOWED_VIEWS = (
    "v_campaign_roas",
    "v_budget_pacing",
    "v_creative_fatigue",
    "v_audience_perf",
)

AVG_ORDER_VALUE = 50.0
TODAY = 14  # day 14 of the flight


class GatewayError(Exception):
    pass


def create_views(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE VIEW IF NOT EXISTS v_campaign_roas AS
        SELECT c.campaign_id, c.name, c.status,
               ROUND(SUM(d.spend), 2) AS total_spend,
               SUM(d.conversions) AS total_conversions,
               ROUND(SUM(d.conversions) * 50.0, 2) AS revenue,
               ROUND(SUM(d.conversions) * 50.0 / NULLIF(SUM(d.spend), 0), 2) AS roas
        FROM campaigns c
        LEFT JOIN ad_sets a ON a.campaign_id = c.campaign_id
        LEFT JOIN creatives cr ON cr.ad_set_id = a.ad_set_id
        LEFT JOIN creative_daily d ON d.creative_id = cr.creative_id
        GROUP BY c.campaign_id;

        CREATE VIEW IF NOT EXISTS v_budget_pacing AS
        SELECT campaign_id, name, status, budget_total, spent_to_date,
               14 AS day_today, start_day, end_day, expected_spend,
               CASE WHEN expected_spend > 0
                    THEN ROUND(spent_to_date / expected_spend, 2) END AS pacing_ratio,
               CASE WHEN status != 'active' THEN status
                    WHEN start_day > 14 THEN 'not_started'
                    WHEN spent_to_date > 1.15 * expected_spend THEN 'overspending'
                    WHEN spent_to_date < 0.85 * expected_spend THEN 'underspending'
                    ELSE 'on_track' END AS pacing_status
        FROM (
            SELECT c.campaign_id, c.name, c.status, c.budget_total,
                   c.start_day, c.end_day,
                   ROUND(COALESCE(SUM(d.spend), 0), 2) AS spent_to_date,
                   ROUND(c.budget_total * MAX(0, MIN(14, c.end_day) - c.start_day + 1) * 1.0
                         / NULLIF(c.end_day - c.start_day + 1, 0), 2) AS expected_spend
            FROM campaigns c
            LEFT JOIN ad_sets a ON a.campaign_id = c.campaign_id
            LEFT JOIN creatives cr ON cr.ad_set_id = a.ad_set_id
            LEFT JOIN creative_daily d ON d.creative_id = cr.creative_id
            GROUP BY c.campaign_id
        );

        CREATE VIEW IF NOT EXISTS v_creative_fatigue AS
        SELECT cr.creative_id, cr.name, cr.format, a.campaign_id,
               ROUND(SUM(CASE WHEN d.day <= 7 THEN d.clicks ELSE 0 END) * 1.0
                     / NULLIF(SUM(CASE WHEN d.day <= 7 THEN d.impressions ELSE 0 END), 0), 4)
                     AS ctr_first7,
               ROUND(SUM(CASE WHEN d.day > 7 THEN d.clicks ELSE 0 END) * 1.0
                     / NULLIF(SUM(CASE WHEN d.day > 7 THEN d.impressions ELSE 0 END), 0), 4)
                     AS ctr_last7,
               ROUND((1.0 - (SUM(CASE WHEN d.day > 7 THEN d.clicks ELSE 0 END) * 1.0
                     / NULLIF(SUM(CASE WHEN d.day > 7 THEN d.impressions ELSE 0 END), 0))
                     / NULLIF(SUM(CASE WHEN d.day <= 7 THEN d.clicks ELSE 0 END) * 1.0
                     / NULLIF(SUM(CASE WHEN d.day <= 7 THEN d.impressions ELSE 0 END), 0), 0)) * 100, 1)
                     AS decay_pct,
               CASE WHEN (1.0 - (SUM(CASE WHEN d.day > 7 THEN d.clicks ELSE 0 END) * 1.0
                     / NULLIF(SUM(CASE WHEN d.day > 7 THEN d.impressions ELSE 0 END), 0))
                     / NULLIF(SUM(CASE WHEN d.day <= 7 THEN d.clicks ELSE 0 END) * 1.0
                     / NULLIF(SUM(CASE WHEN d.day <= 7 THEN d.impressions ELSE 0 END), 0), 0)) * 100 > 25
                    THEN 1 ELSE 0 END AS fatigued
        FROM creatives cr
        JOIN ad_sets a ON a.ad_set_id = cr.ad_set_id
        JOIN creative_daily d ON d.creative_id = cr.creative_id
        GROUP BY cr.creative_id;

        CREATE VIEW IF NOT EXISTS v_audience_perf AS
        SELECT a.audience,
               SUM(d.impressions) AS impressions,
               SUM(d.clicks) AS clicks,
               ROUND(SUM(d.clicks) * 1.0 / NULLIF(SUM(d.impressions), 0), 4) AS ctr,
               ROUND(SUM(d.spend), 2) AS spend,
               SUM(d.conversions) AS conversions
        FROM ad_sets a
        JOIN creatives cr ON cr.ad_set_id = a.ad_set_id
        JOIN creative_daily d ON d.creative_id = cr.creative_id
        GROUP BY a.audience;
        """
    )


_WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|"
    r"attach|detach|pragma|vacuum|reindex|grant|revoke)\b",
    re.IGNORECASE,
)
_FROM_JOIN_RE = re.compile(r"\b(?:from|join)\b", re.IGNORECASE)
# Whitespace, comment markers, quotes, brackets and parentheses that may sit
# between FROM/JOIN and the table name (``FROM ("t")`` included).
_LEAD_RE = re.compile(r"""^[\s/*"'\[\]()`]+""")
_UNQUOTE_RE = re.compile(r"""^["'\[]|["'\]]$""")


def _strip_literals(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def _first_keyword(sql: str) -> str:
    m = re.match(r"\s*([A-Za-z]+)", sql)
    return m.group(1).upper() if m else ""


def _unquote(name: str) -> str:
    return _UNQUOTE_RE.sub("", name).lower()


def _referenced_tables(sql: str) -> set:
    """Table names after FROM/JOIN. Sees through ``FROM/**/t`` and
    ``FROM "t"`` because the regex scans the raw text; the authorizer
    is the backstop for anything this misses."""
    tables = set()
    for m in _FROM_JOIN_RE.finditer(sql):
        rest = _LEAD_RE.sub("", sql[m.end():])
        name = re.match(r"[A-Za-z_][\w$]*", rest)
        if name and name.group(0).lower() not in ("select", "with", "values"):
            tables.add(_unquote(name.group(0)))
    return tables


def _check(sql: str) -> None:
    if _first_keyword(sql) != "SELECT":
        raise GatewayError("SEC-SELECT-01: only SELECT queries are allowed")
    nos = _strip_literals(sql)
    if "--" in nos or "/*" in nos:
        raise GatewayError("SEC-SELECT-02: SQL comments are not allowed")
    body = nos.rstrip()
    if body.endswith(";"):
        body = body[:-1]
    if ";" in body:
        raise GatewayError("SEC-SELECT-02: stacked statements are not allowed")
    if _WRITE_RE.search(nos):
        raise GatewayError("SEC-SELECT-02: write/DDL keywords are not allowed")
    tables = _referenced_tables(nos)
    bad = {t for t in tables if t not in ALLOWED_VIEWS}
    if bad:
        raise GatewayError(
            "SEC-SELECT-03: only published views may be queried, blocked: "
            + ", ".join(sorted(bad))
        )


def run_query(conn: sqlite3.Connection, sql: str):
    """Run a planner query through the hardened gateway.

    Text checks (SEC-SELECT-01/02/03) first, then the SQLite authorizer
    backstop (strict view-aware: base-table reads allowed only on behalf
    of an allowed view), then ``fetchmany(ROW_CAP + 1)`` truncation.
    Returns ``(columns, rows)``.
    """
    _check(sql)
    try:
        with views_only(conn, ALLOWED_VIEWS) as denied:
            try:
                cur = conn.execute(sql)
            except sqlite3.DatabaseError as e:
                if denied:
                    raise GatewayError(
                        "SEC-SELECT-03: denied by database authorizer: "
                        + ", ".join(sorted(set(denied)))) from None
                raise GatewayError(f"SEC-SELECT-03: query failed: {e}") from None
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(ROW_CAP + 1)[:ROW_CAP]
    except GatewayError:
        raise
    except sqlite3.Error as e:
        raise GatewayError(f"SEC-SELECT-01: query failed: {e}") from None
    return cols, rows
