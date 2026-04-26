# Case `tool_timeout_uncertainty`

Family: gateway_grounded. Expected delta: `improves`.

Phase 5.5 §5.5-A. The executor returns `timed_out=true`; the adapter emits `status="timeout"` with no `[E.tool.*]` evidence. Phase 5.2.1-B's enforcer demotes the pass-2 accepted claim to `unsupported` AND emits a budget warning. The case proves a timeout is uncertainty, not a deterministic negative tests_pass signal — the claim must NOT be rejected as if the code were broken. Baseline accepts on event evidence alone.
