# Implementation guide

## Setup

Python 3.10+, stdlib only. No dependencies to install for the core.

```bash
python3 -m pytest tests/ -q
python3 scripts/count_tests.py
```

## Wiring the gateway

```python
from mediaops.telemetry import build_db
from mediaops.views import create_views, run_query

conn = build_db()
create_views(conn)
cols, rows = run_query(conn, "SELECT * FROM v_campaign_roas")
```

`run_query` applies text checks, then the authorizer backstop, then the
fetch cap. Anything denied raises `GatewayError` with a cited rule ID.

## Running the engines directly

```python
from mediaops import reallocate, fatigue
plan = reallocate.plan_reallocation(conn)   # engines read views directly
flags = fatigue.detect_fatigue(conn)
```

## Demo

```bash
pip install streamlit
streamlit run demo/app.py
```

## Adapting to a new domain

1. Replace `telemetry.py` seed tables and the four views in `views.py`.
2. Keep `authz.py` unchanged — it is domain-agnostic.
3. Rewrite the five intents in `text2sql.py` for the new views.
4. Swap `reallocate.py`/`fatigue.py` for the domain's differentiators.
5. Write four SOPs under `docs/sops/` in your own words.
