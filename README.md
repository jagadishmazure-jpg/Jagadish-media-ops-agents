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
- **Proof:** all tests green (real total below); real run: CMP-001 at
  **5.73 ROAS**, CMP-002 **overspending** (pacing 1.36), CRT-007 flagged
  fatigued at **34.4% CTR decay**, reallocation plan moves **$2,000** from
  CMP-002 (ROAS 1.33) to CMP-003 and CMP-001, each move gated by its real size.

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

Pacing, ROAS and budget reallocation (rendered from a fresh run in CI):

<!-- run: python scripts/show_differentiator.py -->
```text
pacing CMP-002 ratio=1.36 overspending
pacing CMP-001 ratio=1.01 on_track
pacing CMP-003 ratio=0.46 underspending
pacing CMP-004 ratio=None paused
roas   CMP-001 5.73
roas   CMP-003 3.27
roas   CMP-002 1.33
roas   CMP-004 None
move   CMP-002 -> CMP-003 $726.67
move   CMP-002 -> CMP-001 $1,273.33
```
<!-- /run -->

CMP-004 is paused, so it is reported as `paused` and has no ROAS (no spend
in the window). Each move above is 7.3% and 12.7% of the larger affected
budget, so both go through the T2 gate; a move above 20% needs a human (T3).

Fatigue scan (real run):

```
CRT-007 Hero Video v3 — fatigued (decay 34.4%)
  -> CTR decayed 34.4% (> 25.0%): rotate in fresh creative (FATIGUE-01).
```

Gateway denial (real run):

```
>>> run_query(conn, "SELECT * FROM campaigns, v_campaign_roas")
GatewayError: SEC-SELECT-03: only published views may be queried, blocked: campaigns
```

## How this differs from the marketplace and retail repos

| Repo | Scarce resource / core logic | Media concepts present? |
|---|---|---|
| `Jagadish-marketplace-seller-agents` | Listing quality scores, dispute triage, seller policy compliance | No campaigns, spend, ROAS or creatives |
| `Jagadish-retail-ops-agents` | Store inventory, replenishment, slotting | No ad spend or pacing |
| `Jagadish-coldchain-logistics-agents` | Temperature telemetry and shipment compliance | None |
| **this repo** | **Ad spend**: pacing against flight dates, ROAS-ranked reallocation, creative-fatigue decay | — |

I checked the code of the marketplace and retail repos for campaign, ROAS,
pacing and creative logic: there is none, so the overlap is only the shared
spine (gateway, audit, orchestrator pattern). The gateway uses the
portfolio's strict view-aware SQLite authorizer (see
`docs/adr/0001-sqlite-authorizer-backstop.md`).

## How to run

```bash
python3 -m pytest tests/ -q          # stdlib only
python3 scripts/count_tests.py       # prints the real total
pip install streamlit && streamlit run demo/app.py
```

<!-- run: python scripts/count_tests.py -->
```text
94 tests collected
```
<!-- /run -->

## Guardrails and security controls

- **SELECT-only gateway** (SEC-SELECT-01/02/03): first-keyword check,
  literal-aware write-keyword scan, comment/stacked-statement rejection,
  FROM/JOIN view allowlist.
- **Strict SQLite authorizer backstop** (`mediaops/authz.py`): base-table
  reads allowed only on behalf of an allowed view (via the authorizer's
  `source` argument); schema tables, `load_extension`, writes, PRAGMA,
  ATTACH denied. `tests/test_authorizer_strict.py` proves it with the text
  check switched off. Known residual: a column-free `count(*)` on a base
  table can reveal a row count, never values; the text check blocks the
  plain form. See `docs/adr/0001-sqlite-authorizer-backstop.md`.
- **Fetch-time row cap**: `fetchmany(ROW_CAP + 1)`; never `fetchall()` on
  the planner path; no LIMIT rewriting.
- **Confirmation gates**: budget shifts >20% of the affected budget (T3)
  and campaign pauses (T4) are fail-closed: no approver, an approver that
  times out, or any answer other than `True` means denied.
- **PII scrubbing** before feedback storage: `(555) 123-4567`,
  `+1 (555) 123-4567`, `555.123.4567`, SSNs, card numbers (grouped or
  not); dates and counts untouched.
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
| CI (tests, ruff, docs check, brand check, CodeQL) | Built, runs on push |

## Standardization review (2026-10-18)

Bugs found in review and fixed, each with a regression test in
`tests/test_mediaops.py` (section "review fixes"):

| ID | Bug | Fix |
|---|---|---|
| MEDIA-SEED-01 | Seed data had spend before a campaign's start day, and budgets were scaled so every campaign was flagged as an anomaly | Delivery starts on the start day; budgets match the 14-day plan |
| PACE-01 | Paused CMP-004 was reported as overspending with a negative expected spend | Expected spend clamped to the flight window; `paused` and `not_started` statuses |
| ANOM-01 | "Spend anomalies" listed on-track campaigns | Only over- and under-spending |
| GATE-SIZE-01 | The gate always used a hard-coded 25% move size, so every move was T3 | Real move size: amount / the larger affected budget |
| GATE-TIMEOUT-01 | The documented approver timeout was not implemented; a hung approver hung the agent | Approver runs with a timeout; timeout means denied |
| GATE-TRUE-01 | Any truthy answer approved, so the string `"no"` approved a pause | Only `True` approves |
| REALLOC-GAIN-01 | Money could move to a campaign with equal or lower ROAS | Such moves are skipped |
| PII-CARD-01 | Grouped card numbers (`4111 1111 1111 1111`) passed unredacted | Card pattern applied before the phone pattern |
| SEC-PAREN-01 | The text check missed `FROM (campaigns)`; the authorizer still blocked it | Text check sees through parentheses and still allows subqueries |

The "fictional" company name turned out to belong to real agencies and was
replaced with an invented one (now Velquist Media).

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
