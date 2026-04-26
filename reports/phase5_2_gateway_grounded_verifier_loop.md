# Phase 5.2 — gateway-grounded verifier loop

QA directive: `QA/A29.md` (2026-04-26).
ADR: ADR-37 (`memory-bank/decisionLog.md`).
Status at end of phase: **27 / 27** acceptance criteria green;
quality gates clean (ruff + mypy + pytest, 730 passed / 4
skipped, was 685/4 before Phase 5.2 — exactly +45 new tests);
all four GitHub-hosted runs green on commit `6b741ee`:

| Workflow | Run ID | Wall time |
|---|---|---|
| ci | 24959872919 | 1m15s |
| action-smoke | 24959872926 | 1m01s |
| provider-baseline-node24-smoke | 24959872917 | 19s |
| gateway-grounded-smoke | 24959872936 | 22s |

## 1. Diff résumé

### Sources

* `src/oida_code/verifier/gateway_loop.py` — NEW (~340 LOC). Hosts
  `tool_request_from_spec`,
  `deterministic_estimates_from_tool_result`,
  `GatewayGroundedVerifierRun`, `run_gateway_grounded_verifier`,
  and the pass-2 citation-enforcement helper.
* `src/oida_code/verifier/contracts.py` — `ForwardVerificationResult`
  gains `requested_tools: tuple[VerifierToolCallSpec, ...] = ()`.
* `src/oida_code/verifier/tool_gateway/gateway.py` — 5.1.1
  hardening: new Stage-0 mismatch check; `_blocked_result` populates
  both `warnings` and `blockers`.
* `src/oida_code/cli.py` — `oida-code verify-grounded` subcommand.
* `action.yml` — `enable-tool-gateway` reserved input (default
  `"false"`).
* `.github/workflows/gateway-grounded-smoke.yml` — NEW replay-only
  smoke job.

### Tests + fixtures

* `tests/test_phase5_2_gateway_grounded_verifier.py` — NEW, 45
  tests across the 9 sub-blocks below.
* `tests/fixtures/gateway_grounded_verifier/` — NEW, 8 hermetic
  fixture directories.

### Memory + reports

* `memory-bank/decisionLog.md` — ADR-37 appended.
* `reports/phase5_2_gateway_grounded_verifier_loop.md` — this
  document.
* `README.md` + `memory-bank/progress.md` — updated test count and
  status line (see follow-up commit).

## 2. 5.1.1 gateway hardening

Per QA/A29 §5.1.1, two changes inside
`src/oida_code/verifier/tool_gateway/gateway.py`:

1. **Stage 0 — request/definition tool-name lock.** Before the
   existing registry lookup, the gateway now checks
   `request.tool == gateway_definition.tool_name` and otherwise
   emits one audit event with `policy_decision="block"` and a
   reason that names both fields verbatim. The corresponding
   `VerifierToolResult` is `status="blocked"`. This blocks a
   class of mis-wired calls where a caller would fingerprint a
   ruff definition while the engine ran pytest because
   `request.tool` said so.
2. **`_blocked_result` populates `blockers`.** Every blocked path
   (registry miss, hash drift, sandbox violation, mismatch,
   adapter exception) now produces a `VerifierToolResult` with
   the failure reason in BOTH `warnings` and `blockers`. The
   loop integrator (this phase) treats `blockers` as a hard
   claim blocker, while `warnings` remains the operator-facing
   text.

The four required tests (`test_gateway_blocks_request_tool_definition_mismatch`,
`test_gateway_mismatch_writes_audit_event`,
`test_gateway_blocked_result_sets_blockers`,
`test_gateway_adapter_exception_sets_blockers`) all pass.

## 3. ADR-37 excerpt

> **Decision:** Phase 5.2 routes verifier-requested tool specs
> through the local deterministic tool gateway. Tool results
> become citable evidence for a second forward/backward pass.
> This integrates Phase 5.1's gateway into the verifier loop
> without enabling MCP or provider tool-calling.

The full ADR (with Accepted / Rejected / Outcome sections) lives
at the bottom of `memory-bank/decisionLog.md`.

## 4. Contract extension — `requested_tools`

`ForwardVerificationResult` (verifier contract schema) gains:

```python
requested_tools: tuple[VerifierToolCallSpec, ...] = ()
```

The default empty tuple keeps Phase 4.1 replay fixtures valid
without modification (`test_legacy_forward_replay_without_requested_tools_still_validates`).
`VerifierToolCallSpec` is the existing Phase 4.1 schema —
forward intent only — and the schema reserves `tool` to the
`Literal["ruff", "mypy", "pytest", "semgrep", "codeql"]`
allowlist.

`BackwardVerificationResult` is **not** extended in Phase 5.2.
QA/A29 §5.2-A line 100: "I prefer to start forward only".
Backward agents stay the necessity guardian; if Phase 5.3 needs
a backward-side request, an additional ADR will follow.

## 5. ToolCallSpec → VerifierToolRequest mapping

`tool_request_from_spec()` enforces:

* `tool` stays inside `ToolName` (the schema enforces this; the
  helper does not widen it).
* `purpose` is copied verbatim, then truncated at the schema's
  200-char limit.
* `scope` is copied exactly. No expansion, no normalisation —
  the existing sandbox is the path-traversal guard.
* No `argv` field exists on either schema (`test_tool_call_spec_never_contains_argv`
  asserts neither model exposes `argv` / `command` / `shell` /
  `shell_command`). The adapter builds the argv from
  `request.tool` and the policy's `repo_root`.
* `requested_by_claim_id` is preserved when supplied.

## 6. Two-pass gateway-grounded loop

`run_gateway_grounded_verifier()` flow, with budget
`max_passes=2` (implicit) and `max_tool_calls=5` (default,
overridable):

```
Pass 1
  forward_pass1 + backward_pass1 (run_verifier on original packet)
  → first_pass_report
  → forward.requested_tools

Tool phase
  for each spec[: max_tool_calls]:
    request = tool_request_from_spec(spec)
    result = gateway.run(
      request, policy=..., admission_registry=...,
      audit_log_dir=..., gateway_definition=...,
    )
    accumulate result.evidence_items
    accumulate deterministic_estimates_from_tool_result(result)
    accumulate result.warnings + result.blockers

Evidence enrichment
  enriched_packet = packet.model_copy(update={
    "evidence_items": packet.evidence_items + new_evidence,
    "deterministic_estimates": packet.deterministic_estimates
                             + new_estimates,
  })

Pass 2
  forward_pass2 + backward_pass2 (run_verifier on enriched packet)
  → pass2.report

Citation enforcement (Phase 5.2 §5.2-C criterion #10)
  if enriched_evidence_refs:
    for accepted_claim in pass2.report.accepted_claims:
      if no overlap with enriched_evidence_refs:
        demote to unsupported_claims, record warning

Result: GatewayGroundedVerifierRun(
  report=citation_enforced,
  first_pass_report=pass1.report,
  tool_results=...,
  audit_log_paths=...,
  enriched_evidence_refs=...,
  warnings=tool_phase.warnings,
  blockers=tool_phase.blockers,
)
```

There is no third pass and no retry loop. `LLMEvidencePacket` is
frozen, so enrichment goes through `model_copy(update=...)` —
the original packet is never mutated.

## 7. Tool evidence enrichment

The pytest adapter emits one `EvidenceItem` per failure (kind
`test_result`) and an additional positive item when the run
exits cleanly with non-empty stdout. The ruff / mypy / semgrep /
codeql adapters emit `EvidenceItem(kind="tool_finding")` per
issue. The gateway loop appends those items to a NEW packet
(the original is frozen) so pass-2's prompt renders them
inside the named per-item fences introduced in Phase 4.0.1 —
explicitly `<<<OIDA_EVIDENCE id="..." kind="...">>>` ... `<<<END_OIDA_EVIDENCE id="...">>>`,
where the fence name is the `FENCE_NAME` constant exported
from `oida_code.estimators.llm_prompt` and each tool item's
id matches the `[E.tool_output.N]` shape. Tool stdout never
appears as instruction text.

## 8. Deterministic contradiction handling (5.2-D)

Mapping table consumed by
`deterministic_estimates_from_tool_result()`:

| Tool status | Estimate emitted | Aggregator effect |
|---|---|---|
| `failed` (pytest) | `field=tests_pass`, value=0.0, conf=0.8, source=tool | claim with `event_id` match is rejected (Rule 4) |
| `failed` (ruff/mypy/semgrep/codeql) | `field=operator_accept`, same params | same |
| `ok` | none | weak positive; aggregator stays at backward gating |
| `error` / `timeout` / `tool_missing` / `blocked` | none | warning/blocker, NOT a code-failure proof |

The mapping aligns with the Phase 4.2 contract documented in
`VerifierToolResult` itself: `failed` is real negative signal,
the others are uncertainty.

## 9. CLI `verify-grounded`

Required flags: `--forward-replay-1`, `--backward-replay-1`,
`--forward-replay-2`, `--backward-replay-2`, `--tool-policy`,
`--approved-tools`, `--gateway-definitions`. Defaults:
`--audit-log-dir=.oida/tool-gateway/audit`,
`--out=.oida/verifier/grounded_report.json`,
`--max-tool-calls=5`.

The CLI is **not** wired into `oida-code audit` and is **not**
the default `action.yml` flow. `action.yml` exposes a reserved
input `enable-tool-gateway: { default: "false" }` so operators
who experiment with gateway-grounded auditing have a forward-
compatible knob, but Phase 5.2 does not turn it on.

## 10. Fixtures

Eight hermetic scenarios under
`tests/fixtures/gateway_grounded_verifier/`:

| Fixture | Expected verdict |
|---|---|
| `no_tool_needed_claim_supported` | gateway never called; claim accepted on event evidence |
| `tool_needed_then_supported` | pytest ok; pass-2 cites `[E.tool_output.0]`; claim accepted |
| `tool_needed_but_unapproved` | empty admission registry; gateway blocks; claim unsupported |
| `tool_hash_drift` | served description differs from approved fingerprint; quarantine |
| `tool_failed_contradicts_claim` | pytest rc=1; deterministic negative estimate; aggregator rejects |
| `tool_error_uncertainty` | pytest rc=2 (collection error); status=error; uncertainty |
| `path_traversal_blocked` | scope=`../etc/passwd`; sandbox blocks before adapter |
| `prompt_injection_in_tool_output` | stdout contains `IGNORE PRIOR INSTRUCTIONS` + forged close fence; fenced as data |

The five required tests
(`test_fixture_tool_needed_then_supported`,
`test_fixture_tool_hash_drift_quarantines`,
`test_fixture_tool_failed_contradicts_claim`,
`test_fixture_tool_error_uncertainty`,
`test_fixture_prompt_injection_tool_output_is_data`) all pass.

## 11. No-MCP regression locks

* `test_no_mcp_dependency_added` — scans `pyproject.toml` for
  `modelcontextprotocol` / `mcp-server` / `mcp_server`.
* `test_no_mcp_workflow_added` — scans every workflow file for
  the JSON-RPC discovery + dispatch verbs.
* `test_no_jsonrpc_tools_list_or_tools_call_runtime` — scans
  every Python source under `src/oida_code/`; the literal
  strings are forbidden unless inside a quoted forbidden list.
* `test_no_provider_tool_calling_enabled` — regex check that no
  source file enables provider-side tool-calling against
  OpenAI / Anthropic SDKs.
* `test_gateway_loop_is_not_mcp` — `gateway_loop.py` body must
  not reference `modelcontextprotocol`, `mcp.server`,
  `stdio_server`, `json_rpc`, `jsonrpc`.

The Phase 4.7 / Phase 5.0 / Phase 5.1 anti-MCP locks remain
active. Phase 5.2 adds the new test above to the chain.

## 12. Security review

Layered defences carried by Phase 5.2:

1. **5.1.1 mismatch lock** — Stage 0 of the gateway refuses any
   request whose `tool` field disagrees with the supplied
   `gateway_definition.tool_name`.
2. **Admission registry** — only operator-signed `tool_id`s with
   `status="approved_read_only"` reach Stage 3.
3. **Hash drift quarantine** — fingerprint mismatch ⇒
   `policy_decision="quarantine"`; the request is never
   executed.
4. **Sandbox** — existing Phase 4.2-C path-traversal +
   deny-pattern checks reject `../etc/passwd`, `*.env`, `*.key`,
   `id_rsa`, `.git/config` etc. before the adapter binary is
   located.
5. **Adapter exception envelope** — adapter raises ⇒
   `status="blocked"` with the exception class in BOTH
   `warnings` and `blockers`. No Python traceback ever appears
   in the audit log or the run output.
6. **Forbidden phrase scan** — pre-existing renderer guard in
   `oida_code.estimators.llm_prompt`: any provider response
   touching `total_v_net` / `debt_final` / `corrupt_success` /
   `verdict` / `merge_safe` / `production_safe` / `bug_free` /
   `security_verified` is rejected.
7. **Citation rule** — pass-2 accepted claims that don't cite
   the new tool refs (when tools ran) are demoted to
   unsupported. The aggregator already enforced "every
   evidence_ref must exist in the packet"; the citation rule
   adds "must overlap with the freshly-enriched refs".
8. **No write / no network** — `GatewayToolDefinition.allows_write`
   and `requires_network` are pinned `Literal[False]`;
   `ToolPolicy.allow_write` and `allow_network` default to
   False; the loop never enables either.

## 13. What this still does not implement

* MCP runtime code.
* JSON-RPC over stdio or HTTP.
* Discovery + dispatch verbs (`tools/list`, `tools/call`).
* Provider tool-calling on OpenAI / Anthropic / etc.
* Remote tools, write tools, network egress.
* Official `total_v_net` / `debt_final` / `corrupt_success`
  emission. ADR-22 still holds; the schemas still don't expose
  those fields; the runners still scan responses for the
  forbidden phrases.
* GitHub App / custom Checks API integration.
* PyPI stable release; the project remains alpha while official
  fields are blocked.

## 14. Recommendation for Phase 5.3

QA/A29 lists two options:

* **Option recommended** — Phase 5.3 private holdout + verifier
  loop calibration. Measure whether the gateway-grounded
  verifier actually improves citation fidelity, claim
  acceptance correctness, tool contradiction rejection, and
  unsupported claim detection. Still no MCP.
* **Option alternative** — Phase 5.3 local stdio MCP mock
  prototype, contingent on the Phase 5.2 gateway loop +
  audit log + hash drift quarantine + path traversal/secret/
  network/write blocks all being operational AND GitHub-hosted
  CI staying green.

QA/A29's preference: holdout/calibration before MCP. The
project has just made tools locally admitted, fingerprinted,
and auditable; the next useful proof is to MEASURE the
verifier's improvement on a closed corpus, not to open a new
protocol surface.

## 15. Gates

| Gate | Status |
|---|---|
| ruff (`src/`, `tests/`, `scripts/evaluate_shadow_formula.py`, `scripts/real_repo_shadow_smoke.py`) | clean |
| mypy (same set) | clean |
| pytest full suite | green; new file contributes 45 passing tests |
| `tests/test_phase5_2_gateway_grounded_verifier.py` | 45 / 45 passing |
| GitHub-hosted CI runs | all four green on commit `6b741ee` — ci (24959872919, 1m15s), action-smoke (24959872926, 1m01s), provider-baseline-node24-smoke (24959872917, 19s), gateway-grounded-smoke (24959872936, 22s) |

## Honesty statement

Phase 5.2 integrates the local deterministic tool gateway into the verifier loop.
It does not implement MCP.
It does not enable provider tool-calling.
It does not execute remote tools.
It does not allow write tools or network egress.
It does not validate production predictive performance.
It does not emit official total_v_net, debt_final, or corrupt_success.
It does not modify the vendored OIDA core.
