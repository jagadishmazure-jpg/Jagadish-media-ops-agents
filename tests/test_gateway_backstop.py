"""Regression tests for the SQLite gateway backstop (one per bypass shape)."""

import sqlite3

import pytest

from mediaops.authz import views_only
from mediaops.telemetry import build_db
from mediaops.views import ALLOWED_VIEWS, GatewayError, create_views, run_query


@pytest.fixture()
def conn():
    c = build_db()
    create_views(c)
    return c


def test_backstop_rejects_comma_join(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-03"):
        run_query(conn, "SELECT * FROM campaigns, v_campaign_roas")


def test_backstop_rejects_quoted_sqlite_master(conn):
    with pytest.raises(GatewayError):
        run_query(conn, 'SELECT name, sql FROM "sqlite_master"')


def test_backstop_rejects_comment_whitespace(conn):
    with pytest.raises(GatewayError):
        run_query(conn, "SELECT * FROM/**/campaigns")


def test_backstop_caps_large_result_at_fetch_time(conn):
    # Even a legitimate wide query never returns more than ROW_CAP rows:
    # the cap is enforced by fetchmany, not by trusting LIMIT.
    cols, rows = run_query(conn, "SELECT * FROM v_creative_fatigue")
    assert len(rows) <= 100
    # A cross-join-shaped query over views is capped, not exploded.
    cols, rows = run_query(
        conn, "SELECT a.campaign_id, b.creative_id FROM v_campaign_roas a "
              "JOIN v_creative_fatigue b ON 1=1")
    assert len(rows) <= 100


def test_backstop_limit_trick_denied_by_comment_rule(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-02"):
        run_query(conn, "SELECT * FROM v_creative_fatigue LIMIT 100000 -- x")


def test_backstop_rejects_raw_table(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-03"):
        run_query(conn, "SELECT * FROM campaigns")


def test_backstop_rejects_raw_table_in_subquery(conn):
    with pytest.raises(GatewayError, match="SEC-SELECT-03"):
        run_query(conn,
                  "SELECT * FROM v_campaign_roas WHERE campaign_id IN "
                  "(SELECT campaign_id FROM campaigns)")


def test_backstop_rejects_write(conn):
    with pytest.raises(GatewayError):
        run_query(conn, "DELETE FROM campaigns")


def test_backstop_rejects_pragma(conn):
    with pytest.raises(GatewayError):
        run_query(conn, "PRAGMA table_info(campaigns)")


def test_backstop_allows_view_with_aggregates(conn):
    cols, rows = run_query(
        conn, "SELECT COUNT(*) c, AVG(roas) a FROM v_campaign_roas")
    assert len(rows) == 1


def test_backstop_authorizer_clears_on_exit(conn):
    with views_only(conn, ALLOWED_VIEWS):
        pass
    # Direct write works again outside the context (engines need it).
    conn.execute("CREATE TABLE IF NOT EXISTS _t (x INT)")
    conn.execute("DROP TABLE _t")


def test_backstop_strict_authorizer_denies_raw_table_without_text_check(conn):
    # Strict view-aware rule: with the text check bypassed, the authorizer
    # alone must deny a raw base-table read (source has no view name).
    with views_only(conn, ALLOWED_VIEWS) as denied:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("SELECT * FROM campaigns").fetchall()
    assert denied


def test_backstop_strict_authorizer_allows_view_expansion(conn):
    # ...but the same authorizer allows a view query whose expansion
    # reads base tables on the view's behalf.
    with views_only(conn, ALLOWED_VIEWS) as denied:
        rows = conn.execute("SELECT * FROM v_campaign_roas").fetchall()
    assert not denied
    assert len(rows) == 4


def test_backstop_denial_maps_to_rule_id(conn):
    try:
        run_query(conn, "SELECT * FROM sqlite_master")
    except GatewayError as e:
        assert "SEC-SELECT-03" in str(e)
    else:
        raise AssertionError("expected GatewayError")
