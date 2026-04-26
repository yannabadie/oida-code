"""Phase 4.8-B + 4.9-E (QA/A25.md + QA/A26.md, ADR-33 + ADR-34) —
provider/replay label audit.

Reads the redacted provider I/O captured by
``oida-code calibration-eval --store-redacted-provider-io`` and
the replay run's metrics, and produces a per-case classification
table to explain WHY the empirical accuracy delta exists between
the two paths.

Output: ``reports/provider_label_audit_l001_l008.md`` (default).

Classification per (case, expected_estimate label):

* ``match`` — provider observation matches the label.
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
* ``missing_capture`` — Phase 4.9-E: the redacted I/O for this
  case is absent OR carries ``failure_kind != "success"``. With
  Phase 4.9.0 every failure path now stashes redacted I/O, so a
  ``missing_capture`` row tells the operator which provider call
  failed and how.

Phase 4.9-E recommended-action column (one of):

* ``label_too_strict`` → "propose label revision, but do not apply
  automatically"
* ``provider_wrong`` → "keep label, mark provider behaviour"
* ``contract_gap`` → "improve prompt/contract or accept as
  provider behaviour"
* ``mapping_ambiguous`` → "review label semantics; possibly
  re-anchor expected_status"
* ``missing_capture`` → "rerun after Phase 4.9.0 failure-path
  capture (see <case>.json failure_kind)"
* ``match`` → "no action — the provider matches the label"

Hard rule (QA/A25 §4.8-B + QA/A26 §4.9-E): no label change in
this script. The output is documentation; any actual label edits
go through a separate diff with written justification per case.
The ``test_label_audit_never_changes_expected_labels_automatically``
+ ``test_label_audit_marks_label_changes_as_proposals`` invariants
in tests/test_phase4_9_label_audit.py lock that contract.
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
    """Return one row per expected_estimate label for ``case_id``.

    Phase 4.9-E: when the redacted_io capture is absent OR the
    captured file's ``failure_kind != "success"``, every label row
    is classified as ``missing_capture`` (for "absent") or has its
    ``observed`` field annotated with the failure_kind (for
    "non-success captured"). The operator can then act on the
    failure_kind directly without having to open each JSON file."""
    expected = _load_json(case_dir / "expected.json")
    expected_status = expected.get("expected_estimator_status")
    expected_estimates = expected.get("expected_estimates") or []
    provider_response: dict[str, Any] | None = None
    capture_status: str = "no-redacted-io-dir"
    failure_kind: str | None = None
    if redacted_io_dir is not None:
        captured_path = redacted_io_dir / f"{case_id}.json"
        if not captured_path.is_file():
            capture_status = "missing"
        else:
            captured = _load_json(captured_path)
            failure_kind = captured.get("failure_kind") or "success"
            body = captured.get("redacted_response_body")
            # Phase 4.9-E — annotate downstream rather than crash
            # when failure_kind != "success" (the response does NOT
            # decode into the expected contract).
            capture_status = (
                f"failure:{failure_kind}"
                if failure_kind != "success" else "success"
            )
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
        if capture_status == "missing":
            classification = "missing_capture"
            observed = (
                "no <case_id>.json under --redacted-io-dir; "
                "rerun with --store-redacted-provider-io"
            )
        elif capture_status.startswith("failure:"):
            classification = "missing_capture"
            observed = (
                f"provider call failed (failure_kind="
                f"{failure_kind!r}); inspect "
                f"{case_id}.json to see the redacted body"
            )
        else:
            classification, observed = _classify_estimate(
                case_id, label, provider_response,
            )
        provider_value = _extract_provider_value(
            provider_response, label.get("field"),
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
            "provider_value": provider_value,
            "observed": observed,
            "classification": classification,
            "action": _action_for_classification(classification),
        })
    return rows


def _extract_provider_value(
    provider_response: dict[str, Any] | None,
    field: object,
) -> str:
    """Return a short human-readable summary of what the provider
    returned for ``field`` (used in the new ``provider_value``
    column added by Phase 4.9-E)."""
    if provider_response is None or field is None:
        return "—"
    estimates = provider_response.get("estimates") or []
    matching = [
        e for e in estimates
        if isinstance(e, dict) and e.get("field") == field
    ]
    if matching:
        est = matching[0]
        value = est.get("value")
        confidence = est.get("confidence")
        return f"value={value!r} conf={confidence!r}"
    unsupported = provider_response.get("unsupported_claims") or []
    for u in unsupported:
        if isinstance(u, str) and isinstance(field, str) and field in u:
            return f"unsupported: {u}"
    return "(no estimate emitted)"


# Phase 4.9-E — action recommendation per classification (QA/A26
# §4.9-E lines 336-348). Locked by
# `test_label_audit_action_recommendations_are_documented`.
_ACTION_RECOMMENDATIONS: dict[str, str] = {
    "match": (
        "no action — the provider matches the label"
    ),
    "label_too_strict": (
        "propose label revision, but do not apply automatically"
    ),
    "provider_wrong": (
        "keep label, mark provider behaviour"
    ),
    "contract_gap": (
        "improve prompt/contract or accept as provider behaviour"
    ),
    "mapping_ambiguous": (
        "review label semantics; possibly re-anchor expected_status"
    ),
    "missing_capture": (
        "rerun after Phase 4.9.0 failure-path capture "
        "(see <case>.json failure_kind)"
    ),
}


def _action_for_classification(classification: str) -> str:
    return _ACTION_RECOMMENDATIONS.get(
        classification, "(unknown classification — no recommendation)",
    )


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
        "Phase 4.8-B + 4.9-E (QA/A25.md + QA/A26.md, ADR-33 + "
        "ADR-34). **Read-only diagnosis** — no label changes are "
        "made by this script. The ``action`` column carries a "
        "PROPOSED action; any actual label edit lands in a "
        "separate commit with written per-case justification."
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
        "asserts on.\n"
        "* `missing_capture` — Phase 4.9-E: redacted I/O for the "
        "case is absent OR ``failure_kind != \"success\"``."
    )
    lines.append("")
    lines.append("Recommended-action key:")
    lines.append("")
    for classification, action in _ACTION_RECOMMENDATIONS.items():
        lines.append(f"* `{classification}` → {action}")
    lines.append("")
    lines.append(
        "| case_id | field | expected | min/max | required_refs | "
        "provider_value | classification | action | observed |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
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
            f"{r['provider_value']} | "
            f"`{r['classification']}` | "
            f"{r['action']} | "
            f"{r['observed']} |"
        )
    lines.append("")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    lines.append("## Summary")
    lines.append("")
    for k in sorted(counts):
        lines.append(f"* `{k}`: {counts[k]}")
    lines.append("")
    lines.append(
        "**Hard rule**: every `action` listed above is a PROPOSAL "
        "for human review. This script never writes back to "
        "`expected.json` files."
    )
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
