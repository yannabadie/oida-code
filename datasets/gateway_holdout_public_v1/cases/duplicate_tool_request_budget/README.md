# Case `duplicate_tool_request_budget`

Family: gateway_grounded. Expected delta: `same`.

Phase 5.5 §5.5-A. Pass-1 requests pytest three times with identical scope. The case's tool_policy carries `max_tool_calls=2` so the gateway loop runs at most two of them. The audit log demonstrates the cap is honoured (no autonomous loop) and pass-2 accepts with a citation to the resulting `[E.tool.pytest.0]`. Baseline accepts on event evidence alone — both modes converge, so the discriminator here is the budget audit, not the verdict.
