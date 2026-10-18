# ADR 0001: SQLite authorizer backstop for the SELECT-only gateway

## Status

Accepted. Shipped from the start in this repo.

## Context

The text-to-SQL gateway restricts planner queries to SELECTs over four
published views. Text checks alone (regex on the query string) were
bypassed in sibling repos:

- `SELECT * FROM <view>, <base_table>` (comma join)
- `SELECT name, sql FROM "sqlite_master"` (quoted identifier)
- `SELECT * FROM/**/<base_table>` (comment as whitespace)
- `... LIMIT 100000 -- x` returning 36,864 rows (comment killed the cap)

## Decision

Two independent layers:

1. **Text checks** (SEC-SELECT-01/02/03): first-keyword SELECT, no
   write keywords outside literals, no comments/stacked statements,
   FROM/JOIN table names restricted to the published views.
2. **SQLite authorizer** (`mediaops/authz.py`): while a gateway query
   runs, SQLite authorizes every access. Reads are allowed on the views
   or on base tables *when the authorizer's `source` argument names an
   allowed view* (i.e. the read happens on the view's behalf during
   expansion). Direct base-table reads, schema tables, writes, PRAGMA,
   ATTACH and `load_extension` are denied. Denials raise
   `sqlite3.DatabaseError`, mapped to SEC-SELECT-03 with the denied
   names cited.

Row caps are enforced at fetch time (`fetchmany(ROW_CAP + 1)`), never by
rewriting LIMIT and never with `fetchall()` on the planner path. Engines
that need every row read the database directly, not through the gateway.

## Consequences

- Bypass-class queries are denied even with the text check disabled
  (regression-tested in `tests/test_gateway_backstop.py`).
- Legitimate view queries work: the authorizer sees base-table reads
  during view expansion and allows them via the `source` rule.
- The authorizer is registered only inside the `views_only` context and
  cleared on exit, so engine writes are unaffected.

## Revision (2026-10-18, standardization review)

- `mediaops/authz.py` is now the shared portfolio template (v3). It adds an
  explicit `load_extension` deny and always denies the schema tables, even
  if one is ever listed as allowed.
- `tests/test_authorizer_strict.py` repeats every bypass form with the text
  check switched off, alongside `tests/test_gateway_backstop.py`.
- The text check now also sees through parentheses (`FROM (campaigns)`);
  before, only the authorizer caught that form.
- Residual, accepted: a column-free `count(*)` on a base table can reveal a
  row count, never values. The text check blocks the plain form.
