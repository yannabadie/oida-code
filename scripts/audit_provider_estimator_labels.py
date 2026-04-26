"""Phase 4.8-B (QA/A25.md, ADR-33) — provider/replay label audit.

Reads the redacted provider I/O captured by
``oida-code calibration-eval --store-redacted-provider-io`` and
the replay run's metrics, and produces a per-case classification
table to explain WHY the empirical accuracy delta exists between
the two paths.

Output: ``reports/provider_label_audit_l001_l008.md`` (default).

Classification per (case, expected_estimate label):

* ``label_too_strict`` — the provider returned a value/status the
  current label rejects, but the value is plausibly correct
  (operator should consider widening the label).
* ``provider_wrong`` — the provider returned an outcome that
  contradicts the case's intent / evidence (no label change
  justified).
* ``mapping_ambiguous`` — the response shape (e.g.,
  ``unsupported_claims`` vs an actual estimate) maps to a status
  the runner derives differently than the case expects.
* ``contract_gap`` — the provider response lacks a field the case
  asserts on (missing estimate, missing evidence ref).
* ``match`` — provider observation matches the label.

Hard rule (QA/A25 §4.8-B): no label change in this script. The
output is documentation; any actual label edits go through a
separate diff with written justification per case.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _classify_estimate(
    case_id: str,
    label: dict[str, Any],
    provider_response: dict[str, Any] | None,
) -> tuple[str, str]:
    """Return ``(classification, observed_summary)`` for one
    expected_estimate label vs the provider's response."""
    field = label.get("field")
    expected_status = label.get("expected_status")
    min_value = label.get("min_value")
    max_value = label.get("max_value")
    required_evidence = list(label.get("required_evidence_refs") or ())
    if provider_response is None:
        return ("contract_gap", "no provider response captured")
    estimates = provider_response.get("estimates") or []
    matching = [
        e for e in estimates
        if isinstance(e, dict) and e.get("field") == field
    ]
    unsupported = provider_response.get("unsupported_claims") or []
    if expected_status == "unsupported":
        # Either an entry in unsupported_claims with the field name OR
        # an estimate with confidence == 0 counts as a match.
        for u in unsupported:
            if isinstance(u, str) and field is not None and field in u:
                return ("match", f"in unsupported_claims: {u!r}")
        for est in matching:
            if est.get("confidence") in (0, 0.0):
                return (
                    "match",
                    f"estimate present with confidence=0 (value={est.get('value')!r})",
                )
        if not matching:
            return (
                "provider_wrong",
                "no estimate AND no entry in unsupported_claims for this field",
            )
        # Estimate with non-zero confidence when expected unsupported.
        return (
            "provider_wrong",
            f"estimate has confidence={matching[0].get('confidence')!r}, expected unsupported",
        )
    if expected_status == "missing":
        if not matching and field is not None and not any(
            isinstance(u, str) and field in u for u in unsupported
        ):
            return ("match", "no estimate, no unsupported entry — missing as expected")
        return ("provider_wrong", "field present when expected missing")
    if expected_status == "rejected":
        # Rejected cases shouldn't have an estimate at all.
        if not matching:
            return ("match", "no estimate, as expected for rejected")
        return ("provider_wrong", f"estimate present for rejected case: {matching[0]!r}")
    # expected_status == "accepted" — value range + evidence checks.
    if not matching:
        return ("contract_gap", "no estimate emitted for the field")
    est = matching[0]
    value = est.get("value")
    refs = list(est.get("evidence_refs") or [])
    if min_value is not None and value is not None and value < min_value:
        return (
            "label_too_strict",
            f"value {value!r} < min_value {min_value!r}",
        )
    if max_value is not None and value is not None and value > max_value:
        return (
            "label_too_strict",
            f"value {value!r} > max_value {max_value!r}",
        )
    missing_refs = [r for r in required_evidence if r not in refs]
    if missing_refs:
        return (
            "contract_gap",
            f"missing required evidence refs: {missing_refs!r}",
        )
    return ("match", f"value={value!r}, refs={refs!r}")


def _audit_case(
    case_id: str,
    case_dir: Path,
    redacted_io_dir: Path | None,
) -> list[dict[str, Any]]:
    """Return one row per expected_estimate label for ``case_id``."""
    expected = _load_json(case_dir / "expected.json")
    expected_status = expected.get("expected_estimator_status")
    expected_estimates = expected.get("expected_estimates") or []
    provider_response: dict[str, Any] | None = None
    if redacted_io_dir is not None:
        captured_path = redacted_io_dir / f"{case_id}.json"
        if captured_path.is_file():
            captured = _load_json(captured_path)
            body = captured.get("redacted_response_body")
            if isinstance(body, str):
                try:
                    full = json.loads(body)
                    if isinstance(full, dict):
                        choices = full.get("choices") or []
                        if choices and isinstance(choices[0], dict):
                            content = choices[0].get("message", {}).get(
                                "content",
                            )
                            if isinstance(content, str):
                                provider_response = json.loads(content)
                except (json.JSONDecodeError, KeyError, TypeError):
                    provider_response = None
    rows: list[dict[str, Any]] = []
    for label in expected_estimates:
        if not isinstance(label, dict):
            continue
        classification, observed = _classify_estimate(
            case_id, label, provider_response,
        )
        rows.append({
            "case_id": case_id,
            "expected_estimator_status": expected_status,
            "field": label.get("field"),
            "expected_status": label.get("expected_status"),
            "min_value": label.get("min_value"),
            "max_value": label.get("max_value"),
            "required_evidence_refs": list(
                label.get("required_evidence_refs") or (),
            ),
            "observed": observed,
            "classification": classification,
        })
    return rows


def _render_report(
    rows: list[dict[str, Any]],
    *,
    provider_label: str,
    out_path: Path,
) -> None:
    lines: list[str] = []
    lines.append(
        f"# Provider/replay label audit — L001-L008 ({provider_label})",
    )
    lines.append("")
    lines.append(
        "Phase 4.8-B (QA/A25.md, ADR-33). Read-only diagnosis — no "
        "label changes are made by this script. Any actual label "
        "edits land in a separate commit with written justification "
        "per case."
    )
    lines.append("")
    lines.append("Classification key:")
    lines.append("")
    lines.append(
        "* `match` — provider observation matches the label.\n"
        "* `label_too_strict` — provider value within plausible "
        "range but outside the current min/max.\n"
        "* `provider_wrong` — provider contradicts the case's intent.\n"
        "* `mapping_ambiguous` — response shape maps to a different "
        "status than the case expects.\n"
        "* `contract_gap` — provider response lacks a field the case "
        "asserts on."
    )
    lines.append("")
    lines.append(
        "| case_id | field | expected_status | min/max | "
        "required_refs | classification | observed |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        cap = (
            f"[{r['min_value']}, {r['max_value']}]"
            if r["min_value"] is not None or r["max_value"] is not None
            else "—"
        )
        refs = ", ".join(r["required_evidence_refs"]) or "—"
        lines.append(
            f"| {r['case_id']} | {r['field']} | "
            f"{r['expected_status']} | {cap} | {refs} | "
            f"`{r['classification']}` | {r['observed']} |"
        )
    lines.append("")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    lines.append("## Summary")
    lines.append("")
    for k in sorted(counts):
        lines.append(f"* `{k}`: {counts[k]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=_REPO_ROOT / "datasets" / "calibration_v1",
        help="Path to calibration_v1 (or another dataset).",
    )
    parser.add_argument(
        "--redacted-io-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing per-case <case_id>.json captured "
            "by `--store-redacted-provider-io`. When omitted, the "
            "audit produces only `contract_gap` rows for the "
            "provider side (replay-only audit)."
        ),
    )
    parser.add_argument(
        "--provider-label",
        default="provider",
        help="Label for the provider in the report header (e.g. 'deepseek-v4-pro').",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_REPO_ROOT / "reports" / "provider_label_audit_l001_l008.md",
        help="Output Markdown report path.",
    )
    args = parser.parse_args()

    cases_dir = args.dataset / "cases"
    if not cases_dir.is_dir():
        print(f"ERROR: dataset cases dir missing: {cases_dir}")
        return 2

    rows: list[dict[str, Any]] = []
    for case_dir in sorted(cases_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        # Phase 4.8 audit scope: llm_estimator family only.
        try:
            expected = _load_json(case_dir / "expected.json")
        except (OSError, json.JSONDecodeError):
            continue
        if expected.get("family") != "llm_estimator":
            continue
        case_id = expected.get("case_id") or case_dir.name
        rows.extend(_audit_case(case_id, case_dir, args.redacted_io_dir))

    _render_report(
        rows, provider_label=args.provider_label, out_path=args.out,
    )
    print(f"wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
