"""Phase 4.9-A (QA/A26.md, ADR-34) — diagnostic-only Markdown report.

Renders the artifacts under ``<input-dir>`` (typically
``.oida/calibration_v1/`` or ``.oida/provider-baseline/<provider>/``)
into a PR-comment-ready Markdown summary that an operator can read
WITHOUT thinking the result is a merge verdict.

Hard rules (locked by tests in
``tests/test_phase4_9_diagnostic_report.py``):

* Every output starts with the diagnostic banner
  (``Diagnostic only — not a merge verdict.``).
* The status card explicitly shows ``total_v_net`` /
  ``debt_final`` / ``corrupt_success`` as ``blocked`` (ADR-22 hard
  wall — these are NEVER emitted by this renderer).
* The forbidden product-claim words ``merge_safe`` / ``merge-safe``
  / ``production_safe`` / ``production-safe`` / ``bug_free`` /
  ``bug-free`` MUST NEVER appear (4.9-A criterion #6).
* Redacted-I/O references list filenames + ``failure_kind`` values
  but NEVER the raw prompt body. The provider-side redaction is
  trusted; this module only references file paths and the
  per-file ``ProviderRedactedIO`` schema fields.
* No ``official_field_*`` value is rendered as a number greater
  than zero EXCEPT in the ``Official field leaks`` row of the
  status card (where 0 is the only acceptable value and any
  positive count flips the status to ``blocked``).

Diagnostic-status enum (also exported for the CLI's
``action_outputs.txt``, Phase 4.9-D):

* ``blocked`` — ``official_field_leak_count > 0`` (runtime gate fired)
* ``contract_failed`` — at least one contract metric below 1.0
  (citation precision / contradiction rejection / safety block /
  fenced injection)
* ``contract_clean`` — all contract metrics at 1.0
* ``diagnostic_only`` — fallback when contract metrics are
  inconclusive (some null / partial)

The four FORBIDDEN status values (rejected by Phase 4.9-D
criterion #12) are NEVER produced here:
``merge_safe`` / ``production_safe`` / ``verified``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from oida_code.calibration.metrics import CalibrationMetrics

DiagnosticStatus = Literal[
    "blocked", "contract_failed", "contract_clean", "diagnostic_only",
]
"""The four diagnostic-status enum values (Phase 4.9-D criterion 297).
Anything outside this set in ``action_outputs.txt`` is a regression."""

_DIAGNOSTIC_BANNER = "Diagnostic only — not a merge verdict."

_FORBIDDEN_PRODUCT_CLAIMS: tuple[str, ...] = (
    "merge_safe", "merge-safe",
    "production_safe", "production-safe",
    "bug_free", "bug-free",
)
"""Strings the renderer MUST NEVER produce (4.9-A criterion #6).
The locked test ``test_diagnostic_report_does_not_contain_merge_safe``
checks every variant case-insensitively."""

_FORBIDDEN_DIAGNOSTIC_STATUSES: tuple[str, ...] = (
    "merge_safe", "production_safe", "verified",
)
"""Status enum values rejected by Phase 4.9-D criterion #12. The
``derive_diagnostic_status`` function is statically constrained to
``DiagnosticStatus``; this tuple is the negative-list test backstop."""


def _load_optional_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _list_redacted_io(redacted_io_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(filename, parsed_dict)`` for each redacted-I/O JSON
    under ``redacted_io_dir``. Skips unreadable files silently — the
    diagnostic report is a presentation layer, not a validator."""
    if not redacted_io_dir.is_dir():
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(redacted_io_dir.iterdir()):
        if not path.is_file() or path.suffix != ".json":
            continue
        parsed = _load_optional_json(path)
        if isinstance(parsed, dict):
            out.append((path.name, parsed))
    return out


def derive_diagnostic_status(
    metrics: CalibrationMetrics,
) -> DiagnosticStatus:
    """Compute the diagnostic-status enum value from the run's
    metrics. Used by the CLI's ``action_outputs.txt`` writer (4.9-D).

    Order of precedence:

    1. Any official-field leak → ``blocked`` (ADR-22 hard wall).
    2. Any contract metric < 1.0 → ``contract_failed``.
    3. All contract metrics == 1.0 → ``contract_clean``.
    4. Otherwise → ``diagnostic_only``.

    Contract metrics: ``evidence_ref_precision`` /
    ``unknown_ref_rejection_rate`` / ``tool_contradiction_rejection_rate``
    / ``safety_block_rate`` / ``fenced_injection_rate``.
    """
    if metrics.official_field_leak_count > 0:
        return "blocked"
    contract_metrics = (
        metrics.evidence_ref_precision,
        metrics.unknown_ref_rejection_rate,
        metrics.tool_contradiction_rejection_rate,
        metrics.safety_block_rate,
        metrics.fenced_injection_rate,
    )
    if all(m >= 1.0 for m in contract_metrics):
        return "contract_clean"
    if all(m is not None for m in contract_metrics):
        return "contract_failed"
    return "diagnostic_only"


def _provider_label(metrics: CalibrationMetrics) -> str:
    """Best-effort provider label for the status card. The
    CalibrationMetrics shape doesn't carry a provider name itself —
    callers that want a more specific label can patch the rendered
    output, but for a diagnostic dump this surfaces ``replay`` vs
    ``provider-driven`` based on whether any LLM-estimator cases
    were evaluated."""
    if metrics.estimator_cases_evaluated > 0:
        return "provider-driven (see redacted_io/ for details)"
    return "replay (no external provider call)"


def _format_optional_pct(value: float | None) -> str:
    if value is None:
        return "_not computed_"
    return f"`{value:.3f}`"


def _format_count(value: int) -> str:
    return f"`{value}`"


def render_status_card(metrics: CalibrationMetrics) -> str:
    """Section 1 — status card. Always shows official fields as
    ``blocked``; any other rendering would violate ADR-22."""
    status = derive_diagnostic_status(metrics)
    leak_count = metrics.official_field_leak_count
    return "\n".join([
        "## 1. Status card",
        "",
        "- Mode: `diagnostic-only`",
        f"- Diagnostic status: `{status}`",
        "- Official `total_v_net`: **blocked** (ADR-22)",
        "- Official `debt_final`: **blocked** (ADR-22)",
        "- Official `corrupt_success`: **blocked** (ADR-22)",
        f"- Provider: {_provider_label(metrics)}",
        f"- Evidence integrity: "
        f"{'pass' if metrics.evidence_ref_precision >= 1.0 else 'fail'}",
        f"- Official field leaks: {_format_count(leak_count)}",
    ])


def render_what_was_measured(
    metrics: CalibrationMetrics,
    per_case: list[dict[str, Any]] | None,
) -> str:
    """Section 2 — what was measured. Tells the reader the SHAPE of
    the run, not predictive performance."""
    families: dict[str, int] = {}
    if per_case is not None:
        for entry in per_case:
            fam = str(entry.get("family", "unknown"))
            families[fam] = families.get(fam, 0) + 1
    family_lines = (
        [f"  - `{name}`: {count}" for name, count in sorted(families.items())]
        if families else ["  - (per-case breakdown not present in this run)"]
    )
    return "\n".join([
        "## 2. What was measured",
        "",
        f"- Total cases: {_format_count(metrics.cases_total)}",
        f"- Cases evaluated: {_format_count(metrics.cases_evaluated)}",
        f"- Cases excluded for contamination: "
        f"{_format_count(metrics.cases_excluded_for_contamination)}",
        f"- Cases excluded for flakiness: "
        f"{_format_count(metrics.cases_excluded_for_flakiness)}",
        f"- LLM-estimator cases evaluated: "
        f"{_format_count(metrics.estimator_cases_evaluated)}",
        f"- LLM-estimator cases skipped: "
        f"{_format_count(metrics.estimator_cases_skipped)}",
        "- Calibration families:",
        *family_lines,
    ])


def render_key_findings(metrics: CalibrationMetrics) -> str:
    """Section 3 — key findings. Lists the contract-side rates so a
    reader can spot a degradation without reading the raw JSON."""
    return "\n".join([
        "## 3. Key findings",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Claim accept accuracy | {_format_optional_pct(metrics.claim_accept_accuracy)} |",
        f"| Claim accept macro-F1 | {_format_optional_pct(metrics.claim_accept_macro_f1)} |",
        f"| Citation precision | {_format_optional_pct(metrics.evidence_ref_precision)} |",
        f"| Citation recall | {_format_optional_pct(metrics.evidence_ref_recall)} |",
        f"| Unknown-ref rejection rate | "
        f"{_format_optional_pct(metrics.unknown_ref_rejection_rate)} |",
        f"| Tool-contradiction rejection rate | "
        f"{_format_optional_pct(metrics.tool_contradiction_rejection_rate)} |",
        f"| Safety block rate | {_format_optional_pct(metrics.safety_block_rate)} |",
        f"| Fenced-injection rate | {_format_optional_pct(metrics.fenced_injection_rate)} |",
        f"| Estimator status accuracy | "
        f"{_format_optional_pct(metrics.estimator_status_accuracy)} |",
        f"| Estimator estimate accuracy | "
        f"{_format_optional_pct(metrics.estimator_estimate_accuracy)} |",
    ])


def render_provider_matrix(
    redacted_io_files: list[tuple[str, dict[str, Any]]],
) -> str:
    """Section 3b — provider failure matrix. ONE row per redacted-I/O
    file. ``failure_kind`` makes the V4 Pro 6/8 invalid_shape gap
    visible at a glance. Linked filenames let the operator open the
    file from a PR comment WITHOUT exposing raw prompts (only the
    SHA256 lives inside)."""
    if not redacted_io_files:
        return "\n".join([
            "## 3b. Provider failure matrix",
            "",
            "_No redacted-I/O captures present (replay run, or "
            "`--store-redacted-provider-io` not set)._",
        ])
    lines = [
        "## 3b. Provider failure matrix",
        "",
        "Each row is one provider call. ``failure_kind`` records why "
        "the call did or did not produce a usable response. The "
        "linked file carries the prompt SHA256, NOT the raw prompt; "
        "API keys are redacted before the file is written.",
        "",
        "| File | `failure_kind` | `http_status` | `model` | `wall_clock_ms` |",
        "|---|---|---|---|---|",
    ]
    for filename, payload in redacted_io_files:
        failure_kind = str(payload.get("failure_kind", "success"))
        http_status = payload.get("http_status")
        model = payload.get("model")
        wall_clock = payload.get("wall_clock_ms", 0)
        lines.append(
            f"| `redacted_io/{filename}` "
            f"| `{failure_kind}` "
            f"| {http_status if http_status is not None else '—'} "
            f"| `{model}` "
            f"| {wall_clock} |"
        )
    return "\n".join(lines)


def render_what_this_does_not_prove() -> str:
    """Section 4 — explicit non-claims. Locked by
    ``test_diagnostic_report_does_not_contain_merge_safe``."""
    return "\n".join([
        "## 4. What this does NOT prove",
        "",
        "This run is a measurement of pipeline behaviour on "
        "controlled cases. It does NOT make any of the following "
        "claims (ADR-22 + ADR-28):",
        "",
        "- This change is **not** asserted to be ready to merge.",
        "- This change is **not** asserted to be production-ready.",
        "- This change is **not** asserted to be free of bugs.",
        "- This change is **not** asserted to be free of security defects.",
        "- This run does **not** emit `total_v_net`, `debt_final`, "
        "or `corrupt_success` — those fields remain blocked at v0.4.x.",
    ])


def render_next_actions(
    metrics: CalibrationMetrics,
    redacted_io_files: list[tuple[str, dict[str, Any]]],
) -> str:
    """Section 5 — next actions. Suggests inspecting the redacted
    failure paths when any provider call did NOT succeed."""
    failure_kinds = {
        str(payload.get("failure_kind", "success"))
        for _filename, payload in redacted_io_files
    }
    actions: list[str] = []
    if "invalid_shape" in failure_kinds:
        actions.append(
            "- Inspect provider failures with `failure_kind=invalid_shape` "
            "(see Section 3b). The redacted body in each file shows what "
            "the provider returned instead of a valid `choices` array."
        )
    if "invalid_json" in failure_kinds:
        actions.append(
            "- Inspect provider failures with `failure_kind=invalid_json`. "
            "The redacted body shows the malformed payload."
        )
    if (
        "transport_error" in failure_kinds
        or "timeout" in failure_kinds
    ):
        actions.append(
            "- Network-level failures recorded; rerun once "
            "transient conditions clear."
        )
    if "provider_unavailable" in failure_kinds:
        actions.append(
            "- One or more cases skipped because the provider env "
            "var was missing. Verify the credential is present in "
            "the runner environment."
        )
    if metrics.evidence_ref_precision < 1.0:
        actions.append(
            "- Citation precision below 1.0 — at least one provider "
            "response cited evidence the packet did not carry. "
            "Rerun on the private holdout to confirm."
        )
    if not actions:
        actions.append(
            "- No provider-level failures detected. Optionally rerun "
            "with `--store-redacted-provider-io` to capture deeper "
            "diagnostics on the next batch."
        )
    return "\n".join([
        "## 5. Next actions",
        "",
        *actions,
    ])


def _render_markdown(
    *,
    input_dir: Path,
    metrics: CalibrationMetrics,
    per_case: list[dict[str, Any]] | None,
    redacted_io_files: list[tuple[str, dict[str, Any]]],
    stability: Mapping[str, Any] | None,
) -> str:
    """Assemble the full diagnostic Markdown from already-loaded
    inputs. Kept separate from the directory-loading wrapper for
    unit-testability."""
    sections: list[str] = [
        "# OIDA-code Diagnostic Report",
        "",
        f"> {_DIAGNOSTIC_BANNER}",
        "",
        f"_Source: `{input_dir.as_posix()}`_",
        "",
        render_status_card(metrics),
        "",
        render_what_was_measured(metrics, per_case),
        "",
        render_key_findings(metrics),
        "",
        render_provider_matrix(redacted_io_files),
        "",
        render_what_this_does_not_prove(),
        "",
        render_next_actions(metrics, redacted_io_files),
        "",
    ]
    if stability is not None:
        sections.extend([
            "## 6. Stability across repeat runs",
            "",
            "```json",
            json.dumps(dict(stability), indent=2, sort_keys=True),
            "```",
            "",
        ])
    sections.extend([
        "---",
        "_Generated by `oida-code render-artifacts` (Phase 4.9-A, "
        "ADR-34). Mode: diagnostic-only. Official `total_v_net` / "
        "`debt_final` / `corrupt_success` remain blocked._",
    ])
    return "\n".join(sections).rstrip() + "\n"


def render_diagnostic_markdown_from_dir(input_dir: Path) -> str:
    """Render the diagnostic Markdown from the artifacts under
    ``input_dir``. Reads:

    * ``metrics.json`` (required) — :class:`CalibrationMetrics`
    * ``per_case.json`` (optional) — list of per-case dicts
    * ``redacted_io/*.json`` (optional) — :class:`ProviderRedactedIO`
    * ``stability_summary.json`` (optional) — repeat-run summary

    Raises :class:`FileNotFoundError` when ``metrics.json`` is
    missing — the diagnostic report needs at least one source of
    truth and the metrics file is the canonical one.
    """
    metrics_path = input_dir / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(
            f"diagnostic report needs metrics.json at {metrics_path}",
        )
    metrics = CalibrationMetrics.model_validate_json(
        metrics_path.read_text(encoding="utf-8"),
    )
    raw_per_case = _load_optional_json(input_dir / "per_case.json")
    per_case: list[dict[str, Any]] | None = None
    if isinstance(raw_per_case, list):
        per_case = [r for r in raw_per_case if isinstance(r, dict)]
    redacted_io_files = _list_redacted_io(input_dir / "redacted_io")
    raw_stability = _load_optional_json(input_dir / "stability_summary.json")
    stability: Mapping[str, Any] | None = (
        raw_stability if isinstance(raw_stability, dict) else None
    )

    rendered = _render_markdown(
        input_dir=input_dir,
        metrics=metrics,
        per_case=per_case,
        redacted_io_files=redacted_io_files,
        stability=stability,
    )

    # Negative-list backstop: any forbidden product claim slipping
    # into the rendered output is a fatal regression (the assertion
    # also lives in tests, but defence-in-depth here means a stale
    # template can never reach disk).
    lower = rendered.lower()
    for forbidden in _FORBIDDEN_PRODUCT_CLAIMS:
        if forbidden.lower() in lower:
            raise RuntimeError(
                f"diagnostic report regression — forbidden product "
                f"claim {forbidden!r} appeared in rendered output "
                "(Phase 4.9-A criterion #6 violated).",
            )
    return rendered


def write_diagnostic_markdown(input_dir: Path, out_path: Path) -> Path:
    """Render and write the diagnostic Markdown. Returns the path."""
    rendered = render_diagnostic_markdown_from_dir(input_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


__all__ = [
    "DiagnosticStatus",
    "derive_diagnostic_status",
    "render_diagnostic_markdown_from_dir",
    "render_key_findings",
    "render_next_actions",
    "render_provider_matrix",
    "render_status_card",
    "render_what_this_does_not_prove",
    "render_what_was_measured",
    "write_diagnostic_markdown",
]
