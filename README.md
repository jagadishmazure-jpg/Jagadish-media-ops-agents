# Jagadish-media-ops-agents

End-to-end media ad-operations agents for fictional **Velquist Media** —
the 13th domain showcase on the FDE agentic spine (after the 12-domain
expansion: healthcare, insurance-underwriting, warehouse, energy-grid,
telecom-incident, airline-disruption, pharma-qa, predictive-maintenance,
marketplace-seller, property-ops, contract-lifecycle, food-ingredients-ops).

> **Synthetic demo data.** Every campaign, creative, spend figure and policy
> change in this repo is invented for illustration. This is an independent
> portfolio project, not affiliated with any real company. Nothing here is
> media-buying advice.

## Recruiter summary

- **Problem:** media ad-ops teams juggle campaign ROAS, budget pacing,
  creative fatigue and audience performance across dozens of campaigns —
  slow, spreadsheet-driven, and easy to overspend.
- **Approach:** a ReAct orchestrator over synthetic ad telemetry with
  text-to-SQL on read-only views, a budget-reallocation engine, a
  creative-fatigue detector, SOP retrieval, and a strict SQLite authorizer
  backstop on every query.
- **Proof:** 65 tests green; real run: CMP-001 at **5.73 ROAS**,
  CRT-007 flagged fatigued at **34.4% CTR decay**, reallocation plan moves
  **$6,000** from CMP-002 (ROAS 1.33) to CMP-001/CMP-003 with guardrails.

## How it works

1. **Sensing** — synthetic telemetry (campaigns, ad sets, creatives,
   14 days of daily impressions/clicks/spend/conversions) seeded
   deterministically into SQLite.
2. **Reasoning** — text-to-SQL maps 5 intents (ROAS, pacing, fatigue,
   audience, spend anomalies) to fixed templates over 4 read-only views.
3. **Planning** — the budget-reallocation engine ranks campaigns by ROAS
   and proposes shifts with min/max guardrails and per-move rationales;
   the fatigue detector flags decaying creatives.
4. **Coordination** — the ReAct orchestrator fans out across tools and
   audits every turn.
5. **Acting** — budget shifts >20% and campaign pauses go through a
   fail-closed confirmation gate (T3/T4).
6. **Learning** — PII-scrubbed feedback (thumbs/corrections) is captured
   per item for future tuning.

## Real code excerpts and output

Budget reallocation (real run):

```
$6,000.00 total shift, 2 moves:
  CMP-002 -> CMP-003  $2,205.30  (ROAS 1.33 -> 3.33)
  CMP-002 -> CMP-001  $3,794.70  (ROAS 1.33 -> 5.73)
```

Fatigue scan (real run):

```
CRT-007 Hero Video v3 — fatigued (decay 34.4%)
  -> CTR decayed 34.4% (> 25.0%): rotate in fresh creative (FATIGUE-01).
```

Gateway denial (real run):

```
>>> run_query(conn, "SELECT * FROM campaigns, v_campaign_roas")
GatewayError: SEC-SELECT-03: only published views may be queried
```

## How this differs from coldchain/retail

Coldchain and retail are **logistics** showcases (telemetry, compliance,
slotting). This repo is a **media-monetization** showcase: the scarce
resource is ad spend, the optimization is ROAS-weighted reallocation, and
the decay signal is creative fatigue — a time-series pattern with no
logistics analogue. The gateway here ships the strict view-aware SQLite
authorizer from the start (see `docs/adr/0001-sqlite-authorizer-backstop.md`).

## How to run

```bash
python3 -m pytest tests/ -q          # 65 tests, stdlib only
python3 scripts/count_tests.py       # prints the real total
pip install streamlit && streamlit run demo/app.py
```

## Guardrails and security controls

- **SELECT-only gateway** (SEC-SELECT-01/02/03): first-keyword check,
  literal-aware write-keyword scan, comment/stacked-statement rejection,
  FROM/JOIN view allowlist.
- **Strict SQLite authorizer backstop** (`mediaops/authz.py`): base-table
  reads allowed only on behalf of an allowed view (via the authorizer's
  `source` argument); schema tables, writes, PRAGMA, ATTACH denied.
  See `docs/adr/0001-sqlite-authorizer-backstop.md`.
- **Fetch-time row cap**: `fetchmany(ROW_CAP + 1)`; never `fetchall()` on
  the planner path; no LIMIT rewriting.
- **Confirmation gates**: budget shifts >20% (T3) and campaign pauses (T4)
  are fail-closed without a human approver.
- **PII scrubbing** before feedback storage: `(555) 123-4567`,
  `+1 (555) 123-4567`, `555.123.4567`, SSNs; dates untouched.
- **Hash-chained audit** with tamper detection on every turn.

## Limitations and known failures

- Synthetic 14-day dataset; ROAS uses a fixed $50 average order value.
- TF-IDF retrieval has no stemming — queries must use SOP vocabulary.
- The fake policy feed is seeded; the live feed raises an explicit gap.
- Reallocation is heuristic (ROAS-ranked), not a true optimizer.
- See `docs/threat-model.md` for the STRIDE-lite analysis.

## Built / Written-not-run / Planned

| Item | Status |
|---|---|
| Telemetry, views, hardened gateway, text-to-SQL (5 intents) | Built |
| Budget-reallocation engine, fatigue detector | Built |
| SOP RAG, policy signal, orchestrator, escalation, audit | Built |
| PII-scrubbed feedback, Streamlit demo | Built |
| knowledge/ docs, ADRs, threat model | Built |
| Live policy-feed connector | Planned |
| CI workflows (`ci.yml` present, runs on push) | Written-not-run |

## Docs

- [knowledge/domain-notes.md](knowledge/domain-notes.md) · [knowledge/architecture.md](knowledge/architecture.md)
- [docs/implementation-guide.md](docs/implementation-guide.md) ·
  [docs/interview-points.md](docs/interview-points.md) ·
  [docs/threat-model.md](docs/threat-model.md)
- [docs/adr/0001-sqlite-authorizer-backstop.md](docs/adr/0001-sqlite-authorizer-backstop.md)

## Related repos

- Sibling FDE domains: `Jagadish-coldchain-logistics-agents`,
  `Jagadish-retail-ops-agents`, and the 12-domain expansion repos.
- `Jagadish-agent-feedback-loop` — the feedback-capture pattern reused here.
- `Jagadish-text2sql-data-agent` — the text-to-SQL spine.
