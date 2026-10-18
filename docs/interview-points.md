# Interview points

## The 60-second pitch

"Media ad-ops is a resource-allocation problem: fixed budgets, diverging
ROAS, decaying creatives. I built agents that watch ROAS and pacing over
read-only SQL views, propose budget shifts with guardrails, and flag
creative fatigue from CTR time series — all behind a hardened query
gateway and human confirmation gates for anything that moves money."

## Deep cuts (pick 2–3)

- **Strict authorizer:** "SQLite's authorizer tells you which view a base-
  table read belongs to via the `source` argument. I allow base-table reads
  only when they come through an allowed view — direct reads are denied
  even with the text check disabled. That's what stopped the comma-join
  bypass class."
- **Fetch-time caps:** "I cap with `fetchmany(n+1)`, never by rewriting
  LIMIT — a `LIMIT 100000 -- x` comment trick returned 36k rows in a
  sibling repo before this fix."
- **Fail-closed gates:** "Budget shifts over 20% and campaign pauses need
  a human. No approver means denied, not queued."
- **Fatigue vs performance:** "A decaying creative is a rotation problem,
  not a budget problem. The detector separates the two so the engine
  never buys expensive impressions to compensate."

## Trade-offs to name

- Heuristic reallocation (ROAS-ranked), not a true optimizer — say so.
- Fixed $50 AOV; real ROAS needs revenue joins.
- TF-IDF has no stemming; SOP queries need the SOP's vocabulary.
