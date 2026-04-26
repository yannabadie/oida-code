# Case `negative_path_missing`

Family: claim_contract. Expected delta: `improves`.

Baseline accepts an `observability_sufficient` claim even though only a positive-path test exists. Gateway pass-2 demotes the claim because the tool evidence shows no negative-path coverage.
