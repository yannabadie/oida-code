# Case `f2p_p2p_regression`

Family: code_outcome. Expected delta: `improves`.

Pytest reports a P2P-style failure: an existing behaviour broke even though the F2P candidate test passes. The aggregator's tool-contradiction rule rejects the LLM `C.fix` claim. Baseline (no gateway) accepts the claim because no tool signal is present. Phase 5.4 keeps the SWE-bench F2P/P2P discipline semantically — the canned `executor.json` simulates the harness signal without invoking real pytest.
