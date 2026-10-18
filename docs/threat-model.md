# Threat model (STRIDE-lite + OWASP LLM notes)

## Assets

Ad spend budgets, campaign performance data, operator feedback text.

## STRIDE

- **Spoofing:** no auth in this demo; production needs operator identity
  on gate approvals.
- **Tampering:** hash-chained audit detects log tampering (tested).
  Budget moves are proposed, never executed, without gate approval.
- **Repudiation:** every turn audited with actor + timestamp.
- **Information disclosure:** SELECT-only gateway + strict authorizer;
  feedback text PII-scrubbed before storage. Residual: `count(*)` on a
  view's backing table leaks a row count (documented in authz.py).
- **Denial of service:** fetchmany caps bound result sizes; no unbounded
  loops in engines.
- **Elevation of privilege:** the orchestrator cannot approve its own
  gate — approver is injected, default deny.

## OWASP LLM (relevant)

- **Prompt injection:** text-to-SQL uses fixed templates, never raw LLM
  SQL — injection in the question cannot become a query.
- **Excessive agency:** engines propose; gates dispose. No autonomous
  budget movement.
- **Sensitive information disclosure:** PII scrubber covers phone/SSN/
  email/card formats; dates preserved.

## Out of scope

Live ad-platform APIs, real money movement, multi-tenant isolation.
