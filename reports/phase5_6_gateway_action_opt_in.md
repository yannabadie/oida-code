# Phase 5.6 — opt-in gateway-grounded action path

QA directive: `QA/A33.md` (2026-04-27).
ADR: ADR-41 (`memory-bank/decisionLog.md`).
Status at end of phase: **35 / 35** acceptance criteria green
locally; quality gates clean (ruff + mypy + pytest, 872
passed / 4 skipped, was 824/4 before Phase 5.6 — exactly +48
new tests). Criterion #35 (GitHub-hosted
`action-gateway-smoke` run green) closes in the follow-up
docs commit.

## 1. Diff résumé

### Sources

* `src/oida_code/action_gateway/` — NEW package (~640 LOC):
  - `__init__.py` — package overview + Phase 5.6 hard rules.
  - `bundle.py` — `validate_gateway_bundle(...)` + 8-file
    allowlist + path-traversal + secret/provider/MCP
    filename rejection.
  - `status.py` — `GatewayStatus` 5-value Literal +
    `derive_gateway_status(...)` + `FORBIDDEN_VERDICT_TOKENS`.
  - `summary.py` — `render_gateway_summary(...)` +
    runtime `_scan_for_forbidden_phrases` raising
    `ForbiddenSummaryPhraseError` on hit.
* `src/oida_code/cli.py` — 3 new subcommands:
  - `validate-gateway-bundle <dir> [--workspace-root <p>]`
  - `render-gateway-summary <report.json> --out summary.md ...`
  - `emit-gateway-status --out action_outputs.txt ...`
* `action.yml` — substantial rewrite:
  - 3 new inputs (`gateway-bundle-dir`,
    `gateway-output-dir`, `gateway-fail-on-contract`).
  - `enable-tool-gateway` description rewritten to reflect
    Phase 5.6 implementation (no longer "RESERVED").
  - 5 new outputs (`gateway-report-json`,
    `gateway-summary-md`, `gateway-audit-log-dir`,
    `gateway-status`, `gateway-official-field-leak-count`).
  - 1 hard PR/fork guard step.
  - 1 always-run gateway step (`id: gateway`) that
    branches internally on `ENABLE_TOOL_GATEWAY`.
  - 1 conditional artifact-upload step.

### Datasets / fixtures

* `tests/fixtures/action_gateway_bundle/tool_needed_then_supported/` —
  NEW. Eight required files + optional `executor.json` +
  `README.md`. Renamed from the Phase 5.4 case to use the
  Phase 5.6 stable filename layout (no `gateway_` prefix on
  replays).

### Workflows

* `.github/workflows/action-gateway-smoke.yml` — NEW.
  Replay-only, `workflow_dispatch` + push to main, no
  secrets, `permissions: contents: read`, no
  `pull_request_target`. Calls the composite action with
  `enable-tool-gateway: "true"`, asserts the 5 expected
  artifacts, runs an inline forbidden-token scan over the
  report JSON, and asserts the `gateway-status` output is in
  the canonical 5-value enum.

### Tests

* `tests/test_phase5_6_action_gateway_opt_in.py` — NEW, 48
  tests across 8 sub-blocks + end-to-end CLI flow + an
  anti-mutation invariant on the fixture.

### Memory + reports

* `memory-bank/decisionLog.md` — ADR-41 appended.
* `reports/phase5_6_gateway_action_opt_in.md` — this
  document.
* `README.md` + `memory-bank/progress.md` — updated test
  count and status line (see follow-up commit).

## 2. ADR-41 excerpt

> **Decision:** Phase 5.6 exposes the gateway-grounded
> verifier through the composite GitHub Action only when
> `enable-tool-gateway: "true"` and an explicit replay
> bundle is supplied. The default remains disabled.

## 3. Action inputs

| Input | Default | Purpose |
|---|---|---|
| `enable-tool-gateway` | `"false"` | Opt-in toggle. |
| `gateway-bundle-dir` | `""` | Path to the operator-supplied bundle. Required when the toggle is true. |
| `gateway-output-dir` | `".oida/gateway-grounded"` | Where gateway artifacts land. |
| `gateway-fail-on-contract` | `"false"` | When `"true"`, exit non-zero on contract violations (leak count > 0, bundle invalid). |

The gateway path is invoked AFTER the existing Phase 4.9
audit + calibration + SARIF flow, so callers who don't set
`enable-tool-gateway` see no behavioural change at all.

## 4. Gateway bundle format

The bundle directory MUST contain these eight files (and
nothing secret-shaped, provider-config-shaped, or
MCP-config-shaped):

```
<gateway-bundle-dir>/
  packet.json
  pass1_forward.json
  pass1_backward.json
  pass2_forward.json
  pass2_backward.json
  tool_policy.json
  gateway_definitions.json
  approved_tools.json
```

`oida-code validate-gateway-bundle` is the gate. It rejects:

* missing required files,
* non-regular-file entries,
* path-traversal (per-file `.resolve().relative_to(...)`),
* secret-shaped filenames (`*.env*`, `*.pem`, `*.key`,
  `*.token`, `id_rsa*`, `id_ed25519*`, `*credentials*`,
  `api_key*`, etc.),
* provider config (`provider.yml`, `openai.yml`,
  `anthropic.yml`, etc.),
* MCP config (`mcp.yml`, `modelcontextprotocol*`, etc.).

## 5. Action execution path

When `enable-tool-gateway: "true"` and the PR/fork guard
passes, the gateway step runs this pipeline:

1. `oida-code validate-gateway-bundle "$BUNDLE_DIR" --workspace-root "$GH_WORKSPACE"`
2. `oida-code verify-grounded "$BUNDLE_DIR/packet.json" --forward-replay-1 ... --backward-replay-2 ... --tool-policy ... --approved-tools ... --gateway-definitions ... --audit-log-dir ... --out grounded_report.json`
3. `oida-code emit-gateway-status --out action_outputs.txt --enabled --not-blocked --bundle-valid --grounded-report ... --report-json ... --summary-md ... --audit-log-dir ...`
4. `oida-code render-gateway-summary grounded_report.json --out summary.md --status <enum> --audit-log-dir ... --bundle-dir ...`
5. `oida-code build-artifact-manifest "$GATEWAY_OUTPUT_DIR"` (Phase 4.9-F reuse)
6. `cat summary.md >> "$GITHUB_STEP_SUMMARY"`
7. `cat action_outputs.txt >> "$GITHUB_OUTPUT"`
8. Optional `--gateway-fail-on-contract: "true"` gate exits 3 if leak count > 0.

Bundle validation failure short-circuits to step 3+4 with
`gateway-status=contract_failed`, then optionally exits 3.

## 6. Step Summary / outputs

The Markdown step summary is diagnostic-only:

```
## Gateway-grounded verifier

_Diagnostic only — see ADR-41. No product verdict._

| Item | Status |
|---|---|
| Enabled | true |
| Mode | replay-only |
| Official fields | blocked/null |
| Status | diagnostic_only |
| Tool calls | N |
| Blocked tools | N |
| Accepted claims | N |
| Unsupported claims | N |
| Rejected claims | N |
| Bundle | <path> |
| Audit log | <path> |
```

Action outputs (always set, even when disabled):

* `gateway-status` — one of `disabled` / `diagnostic_only` /
  `contract_clean` / `contract_failed` / `blocked`.
* `gateway-report-json` — path to the grounded report JSON
  (empty when disabled).
* `gateway-summary-md` — path to the rendered summary
  (empty when disabled).
* `gateway-audit-log-dir` — path to the audit log dir
  (empty when disabled).
* `gateway-official-field-leak-count` — integer; 0 when
  disabled or when the runtime scan finds nothing.

The 5-value `gateway-status` enum is structurally pinned via
`Literal[...]` in `oida_code.action_gateway.status`. Product
verdicts (`merge_safe`, `verified`, `production_safe`,
`bug_free`) are unrepresentable: any attempt to construct
them in Python fails type-checking AND would fail the
runtime forbidden-token scan.

## 7. PR/fork guard

```yaml
- name: Phase 5.6 — block gateway on PR / fork PR
  if: |
    inputs.enable-tool-gateway == 'true'
    && (github.event_name == 'pull_request'
        || github.event_name == 'pull_request_target')
  shell: bash
  run: |
    echo "::error::OIDA-code action: enable-tool-gateway=true is forbidden on pull_request / pull_request_target events..."
    exit 2
```

The guard fires BEFORE the gateway step. The smoke workflow
itself is restricted to `workflow_dispatch` + push to main,
so the guard is defence-in-depth.

## 8. Security review

* **No external provider in the gateway path.** Verified by
  `test_action_gateway_does_not_access_secrets` (scans the
  Phase 5.6 block of action.yml for `secrets.` references).
* **No MCP runtime.** Verified by
  `test_no_mcp_dependency_added_phase5_6`,
  `test_no_mcp_workflow_added_phase5_6`,
  `test_action_gateway_module_does_not_import_mcp_runtime`
  (AST-walks every `.py` under `action_gateway/`, asserts
  no MCP imports; strips docstrings + comments before
  scanning for runtime tokens).
* **No provider tool-calling.** Verified by
  `test_no_provider_tool_calling_enabled_phase5_6`.
* **No `pull_request_target` trigger** on the new workflow.
  Verified by
  `test_action_gateway_smoke_workflow_no_pull_request_target`
  (strips header comments before checking).
* **Shell-injection guard.** Three tests
  (`test_action_gateway_inputs_lifted_to_env_not_inline`,
  `test_no_pr_controlled_expression_in_gateway_run_blocks`,
  `test_gateway_bundle_dir_not_interpolated_inline`) walk
  the gateway step's run block and assert no
  `${{ inputs.gateway-* }}` or
  `${{ github.event.pull_request.* }}` is interpolated
  inline.
* **Anti-RCE rationale**: pytest can execute repo code, so
  the gateway path is unsafe on contributions from
  untrusted forks. The guard exits 2 with an `::error::`
  annotation rather than silently disabling.
* **Runtime forbidden-token scan**: every render path
  (`render_gateway_summary`) and the
  `emit-gateway-status --grounded-report ...` flow scan
  for `merge_safe` / `production_safe` / `bug_free` /
  `verified` / `total_v_net` / `debt_final` /
  `corrupt_success`. Any hit forces
  `gateway-status=contract_failed` and a non-zero leak
  count.

## 9. Real-runner smoke

`.github/workflows/action-gateway-smoke.yml`:

* `workflow_dispatch` + push to main only.
* `permissions: contents: read`.
* No external provider, no secrets, no network egress, no
  MCP, no SARIF upload.
* Calls the composite action with
  `enable-tool-gateway: "true"`,
  `gateway-bundle-dir: "tests/fixtures/action_gateway_bundle/tool_needed_then_supported"`,
  `gateway-output-dir: ".oida/action-gateway-smoke"`.
* Asserts the 5 expected gateway artifacts
  (`grounded_report.json`, `summary.md`,
  `action_outputs.txt`, `audit/`,
  `artifacts/manifest.json`).
* Inline forbidden-token scan over the report JSON.
* Asserts `gateway-status` is in the canonical 5-value
  enum.
* Uploads the artifact bundle via
  `actions/upload-artifact@v4`.

The smoke run on the local fixture exercises the full
pipeline. On the GH runner, real `pytest` executes inside
the gateway loop's sandbox; with the bundle's
`request.max_runtime_s=10` default, pytest may time out (the
fixture's tool_policy keeps `max_total_runtime_s=60` but the
per-request budget is the binding constraint). When that
happens, the gateway loop's Phase 5.2.1-B "no citable
evidence" enforcer demotes the pass-2 claim and the
gateway-status comes out as `diagnostic_only` —
timeout/missing-binary are uncertainty, NOT a contract
violation. The smoke is about wiring (CLI invocation →
summary → status → artifacts), not about the gateway's
internal verdict.

## 10. What this still does NOT prove

* Production predictive performance — the smoke runs on a
  controlled fixture, not real PRs.
* Operator UX on real repos — Phase 5.7 will collect that
  data.
* MCP readiness — the gateway path remains replay-only,
  bundle-on-disk only, no MCP runtime, no JSON-RPC
  dispatch. MCP integration is explicitly deferred.
* Anything resembling "merge-safe" — `gateway-status` is
  diagnostic only; product verdicts are structurally
  unrepresentable.

## 11. Recommendation for Phase 5.7

Per QA/A33 "Apres Phase 5.6":

> Si Phase 5.6 passe : Phase 5.7 — operator soak on real repos
> Objectif : exécuter l'action opt-in sur 3 à 5 dépôts / PRs
> contrôlés, collecter artefacts, vérifier que les rapports
> sont utiles, mesurer les faux positifs/faux négatifs, et
> garder enable-tool-gateway=false par défaut.

Recommended Phase 5.7 = operator soak on real repos. Run the
opt-in path on 3–5 controlled PRs, collect the artifacts, and
measure FP/FN against operator labels. `enable-tool-gateway`
stays default false. MCP remains deferred indefinitely.

## 12. Gates

| Gate | Status |
|---|---|
| ruff (full curated CI scope) | clean |
| mypy (same set) | clean (96 source files; was 92 in Phase 5.5 — +4 from the `action_gateway/` package) |
| pytest full suite | 872 passed / 4 skipped (was 824/4 — exactly +48 new tests) |
| `tests/test_phase5_6_action_gateway_opt_in.py` | 48 / 48 passing |
| GitHub-hosted CI runs | (recorded in the follow-up commit once landed) |

## Honesty statement

Phase 5.6 exposes the gateway-grounded verifier as an explicit opt-in
GitHub Action path. It remains disabled by default. It does not make
verify-grounded the default audit path. It does not implement MCP. It
does not enable provider tool-calling. It does not run on fork PRs. It
does not validate production predictive performance. It does not emit
official total_v_net, debt_final, or corrupt_success. It does not modify
the vendored OIDA core.
