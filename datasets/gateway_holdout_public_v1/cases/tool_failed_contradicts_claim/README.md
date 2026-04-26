# Case `tool_failed_contradicts_claim`

Family: gateway_grounded. Expected delta: `improves`.

Pytest exits rc=1; the adapter classifies the result as `status="failed"` and emits a deterministic negative tests_pass estimate. The aggregator's tool-contradiction rule rejects the LLM's `C.tests_pass` claim. Baseline (no gateway) accepts the claim because no tool signal contradicts it. Gateway strictly improves rejection precision.
