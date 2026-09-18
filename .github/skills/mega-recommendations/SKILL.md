# Mega Recommendations

Create `data/private/recommendations.json` only after manual, agent-assisted review.

Follow the [repository verification and handoff policy](../../../CONTRIBUTING.md#verification-and-handoff-policy)
before execution and after review changes. Read-only QA reviews evidence; an
authorized execution owner performs sync and writes the artifact. Missing
permission or prerequisites means blocked, not permission to fetch live data.

1. Sync accounts and transactions.
2. Assign account roles: owner, income, savings, credit card.
3. Review best-practice recommendations and statistical evidence.
4. Write a local gitignored artifact with this exact schema:

```json
{
  "schema_version": "1",
  "generated_at": "2026-07-25T12:00:00Z",
  "period": {"start": "YYYY-MM", "end": "YYYY-MM"},
  "recommendations": [
    {"id": "string", "title": "string", "body": "string", "severity": "high", "evidence": ["string"]}
  ]
}
```

Severity: `high`, `medium`, or `low`.

Keep schema version `1` unchanged. Use each recommendation's `evidence` strings
to reference the local verification record: revision/dirty state, recommendation
artifact hash, input period and snapshot/config identity, environment, timestamp,
quoted observed values, and evidence provenance. Keep sensitive detail local.
Record static review, build/test, runtime, and user acceptance separately; do not
infer financial correctness or user acceptance from a successful report build.
After recommendation, input, calculation, or review-driven changes, reopen affected
evidence rows and repeat review before treating the artifact as accepted. Record
the current owner, check mode, blockers, and next stop condition at handoff.

Do not call an LLM API from report pipeline code. The mega build only reads this local artifact.