"""Print the media-specific logic the retail and marketplace repos do not
have: campaign pacing against flight dates, ROAS by campaign, and budget moves
gated by their real size."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediaops import demo_helpers  # noqa: E402

conn = demo_helpers.demo_db()
for r in demo_helpers.pacing_table(conn):
    print(f"pacing {r['campaign_id']} ratio={r['pacing_ratio']} {r['pacing_status']}")
for r in demo_helpers.campaign_table(conn):
    print(f"roas   {r['campaign_id']} {r['roas']}")
plan = demo_helpers.reallocation_plan(conn)
for m in plan["moves"]:
    print(f"move   {m['from_campaign']} -> {m['to_campaign']} ${m['amount']:,.2f}")
