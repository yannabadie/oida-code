# `private_holdout_v1` — operator-private holdout protocol (Phase 4.8-C)

**Authority**: ADR-33, QA/A25.md §4.8-C.
**Purpose**: a small operator-curated holdout that lets Phase 4.8+
provider regressions land on cases the operator has NOT published,
to balance `calibration_v1`'s purely-synthetic surface.

**This directory ships the SCHEMA only.** The actual case
contents live under `cases/` and are gitignored
(`datasets/private_holdout_v1/cases/`). Each operator builds their
own holdout locally; nothing case-specific enters the public repo.

## What goes in `cases/<case_id>/`

Same shape as `datasets/calibration_v1/cases/<case_id>/`:

| File | Required when | Purpose |
|---|---|---|
| `expected.json` | always | A `CalibrationCase` JSON (see `src/oida_code/calibration/models.py`) — `family`, `case_id`, expected labels, `provenance`, `contamination_risk: "private"`, no secrets in any field. |
| `packet.json` | `family == llm_estimator` | The `LLMEvidencePacket` to feed the provider. |
| `llm_response.json` | `family == llm_estimator` | The replay fixture used when `--llm-provider replay`. |
| `forward_response.json` / `backward_response.json` | `family == claim_contract` | Same replay-fixture pattern as the public dataset. |
| `canned_tool_outputs.json` | `family == tool_grounded` | Per-tool replay payload. |
| `repo/` | `family == code_outcome` | Mini src/tests layout for F2P/P2P stability runs. |

## Hard rules (per QA/A25.md §4.8-C and ADR-32)

1. **No secrets.** Every `expected.json` and packet must have
   `contamination_risk: "private"` AND zero secret-like content
   (API keys, tokens, internal URLs with credentials, etc).
2. **No public benchmark.** Phase 4.8+ uses this holdout to
   COMPARE provider behaviour vs the public `calibration_v1`,
   never to publish a leaderboard.
3. **No threshold tuning.** Operator labels are written ONCE and
   never bumped to make a particular provider look better.
4. **No raw prompt / response artifact** — the same
   `--store-redacted-provider-io` opt-in (Phase 4.8-A) and
   redaction layer apply to runs against this holdout.

## Initial size target (QA/A25.md §4.8-C)

12 cases distributed as:

* 4 `llm_estimator` (capability / benefit / observability /
  one of completion / tests_pass / operator_accept / edge_confidence)
* 3 `safety_adversarial` (prompt-injection / citation /
  unsupported_claims)
* 3 `tool_grounded` (contradiction / scoped-pass / timeout)
* 2 `code_outcome` (F2P / P2P)

## Usage

Once an operator has populated `cases/` locally:

```bash
# Replay smoke first
python -m oida_code.cli calibration-eval datasets/private_holdout_v1 \
    --llm-provider replay \
    --out .oida/private-holdout-v1/replay

# External provider (separate budget)
python -m oida_code.cli calibration-eval datasets/private_holdout_v1 \
    --llm-provider openai-compatible \
    --provider-profile deepseek \
    --api-key-env DEEPSEEK_API_KEY \
    --max-provider-cases 4 \
    --store-redacted-provider-io \
    --out .oida/private-holdout-v1/deepseek
```

## How to publish results without leaking the cases

Phase 4.8+ reports may include AGGREGATE metrics from
`private_holdout_v1` runs (e.g., `cases_evaluated`,
`official_field_leak_count`, `estimator_status_accuracy`) but MUST
NOT include any per-case content (case ids, packets, prompts,
provider responses). The aggregate metric set is the same shape as
`CalibrationMetrics`; the source cases stay local.

## Why a placeholder, not committed cases

Because operator cases may contain proprietary code or internal
context. If your holdout consists only of synthetic-but-private
fixtures (no real internal code), you can choose to commit them —
in that case, make a separate dataset (e.g., `synthetic_holdout_v1`)
and keep its own gitignore-or-not policy explicit in its own README.
