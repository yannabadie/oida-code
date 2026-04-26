# Case `tool_missing_uncertainty`

Family: gateway_grounded. Expected delta: `improves`.

Phase 5.5 §5.5-A. The executor returns `returncode=null` so the pytest binary is treated as missing on PATH. The adapter emits `status="tool_missing"` with no `[E.tool.pytest.*]` evidence; Phase 5.2.1-B's `_enforce_requested_tool_evidence` enforcer demotes the pass-2 accepted claim to `unsupported`. The case proves the gateway preserves uncertainty when a tool is unavailable — it does NOT reject the claim as if the code were broken. Baseline accepts on event evidence alone (no tool ever queried).
