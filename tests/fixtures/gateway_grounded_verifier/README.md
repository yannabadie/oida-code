# Phase 5.2 — gateway-grounded verifier fixtures

Each subdirectory is a hermetic scenario that exercises one
behaviour of the two-pass gateway-grounded verifier loop. The
fixtures are consumed by
`tests/test_phase5_2_gateway_grounded_verifier.py`.

| Directory | Expected outcome |
|---|---|
| `no_tool_needed_claim_supported` | pass1 requests no tools, pass2 accepts the claim |
| `tool_needed_then_supported` | pass1 requests pytest; gateway runs ok; pass2 cites tool evidence; claim accepted |
| `tool_needed_but_unapproved` | pass1 requests pytest; admission empty → blocked; claim unsupported |
| `tool_hash_drift` | served definition's description differs from the approved fingerprint → quarantine |
| `tool_failed_contradicts_claim` | pytest returncode != 0 → deterministic negative estimate; aggregator rejects claim |
| `tool_error_uncertainty` | adapter classifies as `error` (not `failed`); diagnostic_only |
| `path_traversal_blocked` | request.scope contains `../etc/passwd`; sandbox blocks before the adapter |
| `prompt_injection_in_tool_output` | tool stdout contains `IGNORE PRIOR INSTRUCTIONS`; output becomes EvidenceItem data, never instruction |

These fixtures use replay providers and a fake executor — no
live LLM, no real tool subprocess, no external network.

Phase 5.2 does NOT enable MCP, JSON-RPC, provider tool-calling,
or any official `total_v_net` / `debt_final` /
`corrupt_success` field.
