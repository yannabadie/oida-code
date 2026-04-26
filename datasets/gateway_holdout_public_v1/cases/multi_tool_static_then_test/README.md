# Case `multi_tool_static_then_test`

Family: gateway_grounded. Expected delta: `improves`.

Phase 5.5 §5.5-A. Pass-1 requests three tools (ruff + mypy + pytest) inside the per-case `max_tool_calls=5` budget. The Phase 5.5 ``by_tool`` executor schema returns ok for the static checkers and rc=1 with a FAILED line for pytest. The aggregator's tool-contradiction rule rejects the LLM's `C.fix` claim because the pytest deterministic negative estimate dominates the green static signals. Baseline accepts on event evidence alone.
