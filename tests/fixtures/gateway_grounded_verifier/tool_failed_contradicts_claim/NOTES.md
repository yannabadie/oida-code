**Scenario:** pytest exits with `returncode=1` because at least
one test failed. The pytest adapter classifies that as
`status="failed"` and emits an `EvidenceItem` with
`kind="test_result"`. The gateway loop then synthesises a
deterministic `SignalEstimate(value=0.0, confidence=0.8,
source="tool", field="tests_pass")` for the claim's event,
which the aggregator treats as a tool-grounded contradiction
under the existing rule (ADR-26 §4). The LLM claim is rejected.
