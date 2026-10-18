"""Thin Streamlit demo for media ad-operations (13th domain showcase).

Run:  pip install streamlit && streamlit run demo/app.py
All logic lives in mediaops.demo_helpers (stdlib, fully tested).
"""

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("pip install streamlit, then run: streamlit run demo/app.py") from None

from mediaops import demo_helpers

st.set_page_config(page_title="Velquist Media — Ad Ops Agents", layout="wide")
st.title("Velquist Media — Ad Operations Agents (synthetic demo)")

conn = demo_helpers.demo_db()
q = st.selectbox("Ask the ops agent", demo_helpers.DEFAULT_QUESTIONS)

if st.button("Run"):
    if "reallocate" in q.lower():
        plan = demo_helpers.reallocation_plan(conn)
        st.subheader(f"Reallocation plan — ${plan['total_shifted']:,.2f} to shift")
        for m in plan["moves"]:
            st.write(f"**${m['amount']:,.2f}**: {m['from_campaign']} → "
                     f"{m['to_campaign']}")
            st.caption(m["rationale"])
    elif "fatigue" in q.lower():
        rows = demo_helpers.fatigue_table(conn)
        st.subheader("Creative fatigue scan")
        for r in rows:
            st.write(f"**{r['creative_id']}** {r['name']} — {r['status']} "
                     f"(decay {r['decay_pct']}%)")
            st.caption(r["recommendation"])
    else:
        from mediaops import text2sql
        out = text2sql.answer(conn, q)
        st.subheader(f"Intent: {out['intent']}")
        st.code(out["sql"])
        st.table([dict(zip(out["columns"], row)) for row in out["rows"]])

st.caption("Synthetic data only. Nothing here is media-buying advice.")
