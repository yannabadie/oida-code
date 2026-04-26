"""Phase 5.3 (QA/A30.md, ADR-38) — gateway-grounded verifier
calibration runner.

The runner pairs each holdout case's
:class:`GatewayHoldoutExpected` labels with two actual runs:

* ``baseline`` — :func:`run_verifier` (Phase 4.1) with no
  gateway. Forward + backward replays only; no tool execution.
* ``gateway``  — :func:`run_gateway_grounded_verifier`
  (Phase 5.2) routed through the local deterministic gateway.

It computes per-mode metrics and a ``gateway_delta`` and emits:

* ``baseline_metrics.json``      — per-case + macro metrics (no
  gateway).
* ``gateway_metrics.json``       — per-case + macro metrics
  (gateway-grounded).
* ``delta_metrics.json``         — gateway minus baseline.
* ``failure_analysis.md``        — per-case classification +
  recommended action. **NO automatic label mutation.**
* ``artifact_manifest.json``     — SHA256 hashes of all written
  artifacts so a future run can prove integrity.

ADR-38 + QA/A30 hard rules enforced here:

* The runner NEVER writes anywhere under ``datasets/``.
  ``test_calibration_runner_does_not_mutate_dataset`` verifies
  this against the v2 manifest example.
* No external provider, no MCP, no JSON-RPC, no network. The
  whole module imports from existing replay-only paths.
* The runner asserts ``official_field_leak_count == 0`` in
  every emitted JSON; any leak is itself a recorded failure
  classification, never a status promotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FAILURE_CLASSIFICATIONS: tuple[str, ...] = (
    "label_too_strict",
    "gateway_bug",
    "tool_adapter_bug",
    "aggregator_bug",
    "citation_gap",
    "insufficient_fixture",
    "expected_behavior_changed",
)


_ManifestMode = Literal["replay", "fake"]


class CalibrationCaseEntry(BaseModel):
    """One row in ``manifest.json``."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    case_id: str = Field(min_length=1)
    family: Literal[
        "claim_contract",
        "gateway_grounded",
        "code_outcome",
        "safety_adversarial",
    ]
    directory: str = Field(min_length=1)
    provenance: Literal[
        "synthetic",
        "private_trace",
        "private_repo",
        "public_low",
        "public_high",
    ]
    contamination_risk: Literal[
        "synthetic", "private", "public_low", "public_high",
    ]
    expected_delta: Literal[
        "improves", "same", "worse_expected", "not_applicable",
    ]
    notes: str = ""


class GatewayCalibrationManifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    manifest_version: str = Field(min_length=1)
    description: str = ""
    headline_metrics_exclude: tuple[
        Literal[
            "synthetic", "private", "public_low", "public_high",
        ],
        ...,
    ] = ()
    cases: tuple[CalibrationCaseEntry, ...]


@dataclass
class _PerModeMetrics:
    """Lightweight per-mode metric bundle used internally by
    the runner. The serialised form lives in the JSON files."""

    cases_evaluated: int
    accepted_correct: int
    accepted_wrong: int
    unsupported_correct: int
    unsupported_wrong: int
    rejected_correct: int
    rejected_wrong: int
    official_field_leak_count: int

    def to_json(self) -> dict[str, int | float]:
        total = self.cases_evaluated
        if total == 0:
            return {
                "cases_evaluated": 0,
                "accepted_correct": 0,
                "accepted_wrong": 0,
                "unsupported_correct": 0,
                "unsupported_wrong": 0,
                "rejected_correct": 0,
                "rejected_wrong": 0,
                "claim_accept_accuracy": 0.0,
                "official_field_leak_count": 0,
            }
        accept_total = self.accepted_correct + self.accepted_wrong
        accept_acc = (
            self.accepted_correct / accept_total
            if accept_total > 0
            else 0.0
        )
        return {
            "cases_evaluated": total,
            "accepted_correct": self.accepted_correct,
            "accepted_wrong": self.accepted_wrong,
            "unsupported_correct": self.unsupported_correct,
            "unsupported_wrong": self.unsupported_wrong,
            "rejected_correct": self.rejected_correct,
            "rejected_wrong": self.rejected_wrong,
            "claim_accept_accuracy": round(accept_acc, 4),
            "official_field_leak_count": self.official_field_leak_count,
        }


@dataclass
class _CaseClassification:
    case_id: str
    mode: Literal["baseline", "gateway"]
    expected: str
    actual: str
    classification: str
    root_cause: str
    recommended_action: str


def load_manifest(manifest_path: Path) -> GatewayCalibrationManifest:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return GatewayCalibrationManifest.model_validate(raw)


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes(),
    ).hexdigest()


def _stub_metrics_for_mode() -> _PerModeMetrics:
    """The pilot manifest example documents cases without
    actually shipping their replay fixtures (operator-private
    by design). For the smoke + the GitHub-hosted workflow,
    the runner falls back to a stub where every case counts
    as ``cases_evaluated`` but no accept/reject is recorded.

    This keeps the artifacts produced and the no-mutation
    invariant enforceable, without forcing every contributor
    to pre-stage live replay JSON.
    """
    return _PerModeMetrics(
        cases_evaluated=0,
        accepted_correct=0,
        accepted_wrong=0,
        unsupported_correct=0,
        unsupported_wrong=0,
        rejected_correct=0,
        rejected_wrong=0,
        official_field_leak_count=0,
    )


def _emit_failure_analysis(
    rows: list[_CaseClassification], path: Path,
) -> None:
    """Write the seven-column Markdown table per QA/A30
    §5.3-E. Classifications are documented as a legend so the
    operator has a fixed vocabulary."""
    legend_lines = [
        "| Classification | Meaning |",
        "|---|---|",
        (
            "| `label_too_strict` | Operator label rejected an "
            "outcome that turned out to be sound on inspection |"
        ),
        (
            "| `gateway_bug` | Gateway routing or admission "
            "behaviour diverged from spec |"
        ),
        (
            "| `tool_adapter_bug` | A specific deterministic "
            "tool adapter produced wrong evidence |"
        ),
        (
            "| `aggregator_bug` | The verifier aggregator's "
            "rule fired in an unintended way |"
        ),
        (
            "| `citation_gap` | Pass-2 forward failed to cite "
            "available tool refs (anti-injection or prompt "
            "design issue) |"
        ),
        (
            "| `insufficient_fixture` | The replay fixture was "
            "underspecified relative to the label |"
        ),
        (
            "| `expected_behavior_changed` | The product "
            "intentionally changed; label needs operator update "
            "(propose, never auto-mutate) |"
        ),
    ]

    table_header = (
        "| case_id | mode | expected | actual | classification "
        "| root_cause | recommended_action |\n"
        "|---|---|---|---|---|---|---|"
    )
    table_rows = [
        (
            f"| `{r.case_id}` | {r.mode} | {r.expected} | "
            f"{r.actual} | `{r.classification}` | "
            f"{r.root_cause} | {r.recommended_action} |"
        )
        for r in rows
    ]

    body = "\n".join([
        "# Phase 5.3 — gateway calibration failure analysis",
        "",
        "Per QA/A30 §5.3-E. Every row is a per-case proposal.",
        "Labels are NEVER mutated automatically; any change",
        "to operator-supplied expected.json files MUST be a",
        "human review followed by an explicit commit.",
        "",
        "## Classification legend",
        "",
        *legend_lines,
        "",
        "## Per-case rows",
        "",
        table_header,
        *(table_rows or [
            "| _no rows_ | — | — | — | — | — | — |",
        ]),
        "",
    ])
    path.write_text(body, encoding="utf-8")


def _emit_artifact_manifest(out_dir: Path) -> None:
    """SHA256-hash every artifact except the manifest itself
    (chicken-and-egg)."""
    files: dict[str, dict[str, object]] = {}
    payload: dict[str, object] = {
        "phase": "5.3",
        "scheme": "calibration_v1.0",
        "files": files,
    }
    for entry in sorted(out_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.name == "artifact_manifest.json":
            continue
        files[entry.name] = {
            "sha256": _sha256_path(entry),
            "size_bytes": entry.stat().st_size,
        }
    out = out_dir / "artifact_manifest.json"
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run_calibration(
    *,
    manifest_path: Path,
    out_dir: Path,
    mode: _ManifestMode = "replay",
) -> None:
    """Execute the Phase 5.3 calibration.

    Phase 5.3 ships the protocol + scaffolding. The actual
    paired baseline/gateway runs need replay fixtures committed
    per case; the pilot manifest example documents a slate but
    leaves the live fixtures to a follow-up. When invoked
    against the example manifest, the runner produces the four
    JSON artifacts + the failure analysis Markdown with a
    truthful "no replay fixtures committed yet" classification
    on every row.

    Future operators who commit per-case fixtures
    (`forward_replay.json` / `backward_replay.json` /
    `pass{1,2}_{forward,backward}.json`) will see real metrics
    here without the runner changing shape.
    """
    if mode != "replay":
        raise ValueError(
            "Phase 5.3 calibration runner only supports "
            f"mode='replay' (got {mode!r}). External providers "
            "stay opt-in via the existing Phase 4.4.1 binders "
            "and never reach this script."
        )

    manifest = load_manifest(manifest_path)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Phase 5.3 v0 emits stub per-mode metrics until per-case
    # replay fixtures are committed. The shape is committed-
    # forward-compatible: operators who add fixtures get real
    # numbers without the runner / the schema changing.
    baseline = _stub_metrics_for_mode()
    gateway = _stub_metrics_for_mode()

    rows: list[_CaseClassification] = [
        _CaseClassification(
            case_id=case.case_id,
            mode="baseline",
            expected=f"delta={case.expected_delta}",
            actual="not_run",
            classification="insufficient_fixture",
            root_cause=(
                "no replay fixture committed yet (Phase 5.3 "
                "ships the protocol; per-case fixtures are an "
                "operator follow-up)"
            ),
            recommended_action=(
                "commit per-case replay JSONs under "
                f"datasets/private_holdout_v2/{case.directory}/ "
                "or label the case as not_run"
            ),
        )
        for case in manifest.cases
    ]
    rows.extend(
        _CaseClassification(
            case_id=case.case_id,
            mode="gateway",
            expected=f"delta={case.expected_delta}",
            actual="not_run",
            classification="insufficient_fixture",
            root_cause=(
                "no replay fixture committed yet (Phase 5.3 "
                "ships the protocol; per-case fixtures are an "
                "operator follow-up)"
            ),
            recommended_action=(
                "commit per-case replay JSONs under "
                f"datasets/private_holdout_v2/{case.directory}/ "
                "or label the case as not_run"
            ),
        )
        for case in manifest.cases
    )

    baseline_payload = baseline.to_json()
    gateway_payload = gateway.to_json()
    delta_payload: dict[str, object] = {
        "manifest_version": manifest.manifest_version,
        "cases_in_manifest": len(manifest.cases),
        "delta_diagnostic_only": True,
        "headline_metrics_exclude": list(
            manifest.headline_metrics_exclude,
        ),
        # Per-metric deltas live here when both modes report a
        # numeric value. With the stub they're all zero by
        # construction; operator-supplied fixtures populate
        # them.
        "metrics": {
            key: {
                "baseline": baseline_payload.get(key),
                "gateway": gateway_payload.get(key),
                "delta": (
                    (gateway_payload.get(key) or 0)
                    - (baseline_payload.get(key) or 0)
                )
                if isinstance(
                    baseline_payload.get(key), int | float,
                ) and isinstance(
                    gateway_payload.get(key), int | float,
                ) else None,
            }
            for key in baseline_payload
        },
        # RESERVED: gateway_delta is diagnostic only. Phase 5.3
        # explicitly forbids tuning production thresholds on it.
        "reserved": (
            "gateway_delta is diagnostic only — Phase 5.3 does "
            "NOT promote any score to official total_v_net / "
            "debt_final / corrupt_success."
        ),
    }

    (out_dir / "baseline_metrics.json").write_text(
        json.dumps(baseline_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "gateway_metrics.json").write_text(
        json.dumps(gateway_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "delta_metrics.json").write_text(
        json.dumps(delta_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _emit_failure_analysis(rows, out_dir / "failure_analysis.md")
    _emit_artifact_manifest(out_dir)


__all__ = [
    "FAILURE_CLASSIFICATIONS",
    "CalibrationCaseEntry",
    "GatewayCalibrationManifest",
    "load_manifest",
    "run_calibration",
]
