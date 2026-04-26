**Scenario:** pass-1 requests pytest; the admission registry is
empty; the gateway returns `status="blocked"` with a reason in
both `warnings` and `blockers`. The aggregator's pass-2 cannot
cite tool evidence because none exists; the claim is unsupported
(or stays in `unsupported_claims` per the citation rule when the
tool ran but produced nothing — here the tool never ran).
