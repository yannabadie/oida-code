# `tool_needed_then_supported` — Phase 5.6 action gateway bundle

Used by `.github/workflows/action-gateway-smoke.yml` and by
`tests/test_phase5_6_action_gateway_opt_in.py`.

The bundle uses the Phase 5.6 stable filename layout (no
`gateway_` prefix on replays) so the composite GitHub Action
can call `oida-code verify-grounded` directly:

```
packet.json
pass1_forward.json
pass1_backward.json
pass2_forward.json
pass2_backward.json
tool_policy.json
gateway_definitions.json
approved_tools.json
```

The optional `executor.json` carries a canned ok pytest
outcome so the fingerprint check can run without invoking
real pytest. The case mirrors the Phase 5.4
`datasets/gateway_holdout_public_v1/cases/tool_needed_then_supported/`
fixture but with renamed replay files; both sides stay
hermetic.
