"""Creative-fatigue detector (domain differentiator #2).

Flags creatives whose CTR decayed more than FATIGUE_THRESHOLD_PCT
(default 25%) comparing the first 7 days to the last 7 days.

  FATIGUE-01: decay = (ctr_first7 - ctr_last7) / ctr_first7 * 100.
  FATIGUE-02: a creative with <1000 impressions in either window is
              marked "insufficient_data", never "fatigued".

Reads the v_creative_fatigue view directly (engine read).
"""

from __future__ import annotations

import sqlite3

FATIGUE_THRESHOLD_PCT = 25.0
MIN_IMPRESSIONS = 1000


def detect_fatigue(conn: sqlite3.Connection,
                   threshold_pct: float = FATIGUE_THRESHOLD_PCT) -> list:
    """Return list of {creative_id, name, format, campaign_id, ctr_first7,
    ctr_last7, decay_pct, status, recommendation}."""
    rows = conn.execute(
        "SELECT creative_id, name, format, campaign_id, ctr_first7, "
        "ctr_last7, decay_pct, fatigued FROM v_creative_fatigue "
        "ORDER BY decay_pct DESC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        imp = conn.execute(
            "SELECT SUM(CASE WHEN day <= 7 THEN impressions ELSE 0 END) AS i1, "
            "SUM(CASE WHEN day > 7 THEN impressions ELSE 0 END) AS i2 "
            "FROM creative_daily WHERE creative_id = ?",
            (d["creative_id"],),
        ).fetchone()
        if (imp["i1"] or 0) < MIN_IMPRESSIONS or (imp["i2"] or 0) < MIN_IMPRESSIONS:
            status = "insufficient_data"
            rec = "Collect more impressions before judging fatigue (FATIGUE-02)."
        elif (d["decay_pct"] or 0.0) > threshold_pct:
            status = "fatigued"
            rec = (f"CTR decayed {d['decay_pct']}% (> {threshold_pct}%): "
                   "rotate in fresh creative (FATIGUE-01).")
        else:
            status = "healthy"
            rec = "CTR stable; keep running."
        d["status"] = status
        d["recommendation"] = rec
        out.append(d)
    return out
