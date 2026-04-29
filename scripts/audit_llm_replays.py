"""Phase 6.a / G-6a static audit for LLM-authored verifier replays.

This script audits archived ``round_trip_outputs/<case_id>/`` directories
without calling providers, touching network, mutating bundles, or claiming
semantic truth. It checks whether the LLM-authored replay files are internally
consistent with the seed record, packet, and grounded report.

The audit scope is deliberately narrow:

* ``semantic_truth_validated`` is always false.
* A passing case means "no static content inconsistency detected" only.
* Second-provider reauthoring or manual upstream-output review remain separate
  work if stronger replay validation is required.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "phase6_a_replay_audit_v1"
AUDIT_SCOPE = "static_content_consistency"
SEMANTIC_TRUTH_VALIDATED = False

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_INDEX = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
_DEFAULT_OUT_DIR = _REPO_ROOT / "reports" / "phase6_a_replay_audit"

_REQUIRED_FILES = (
    "packet.json",
    "pass1_forward.json",
    "pass1_backward.json",
    "pass2_forward.json",
    "pass2_backward.json",
    "grounded_report.json",
)

_STOPWORDS = frozenset(
    {
        "after",
        "also",
        "assert",
        "class",
        "correctly",
        "from",
        "function",
        "into",
        "must",
        "returns",
        "that",
        "this",
        "type",
        "when",
        "with",
    },
)


@dataclass(frozen=True)
class Finding:
    severity: str
    invariant_id: str
    path: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "invariant_id": self.invariant_id,
            "path": self.path,
            "message": self.message,
        }


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _finding(
    findings: list[Finding],
    severity: str,
    invariant_id: str,
    path: Path,
    message: str,
) -> None:
    findings.append(
        Finding(
            severity=severity,
            invariant_id=invariant_id,
            path=_rel(path),
            message=message,
        ),
    )


def _load_json(path: Path, findings: list[Finding]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        _finding(findings, "error", "FILE-READ", path, str(exc))
    except json.JSONDecodeError as exc:
        _finding(findings, "error", "JSON-PARSE", path, str(exc))
    return None


def _load_seed_records(index_path: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit(f"{_rel(index_path)} must be a JSON array")
    records: dict[str, dict[str, Any]] = {}
    for entry in raw:
        if isinstance(entry, dict) and isinstance(entry.get("case_id"), str):
            records[entry["case_id"]] = entry
    return records


def _validate_contracts(
    data: dict[str, Any],
    paths: dict[str, Path],
    findings: list[Finding],
) -> None:
    from pydantic import ValidationError

    from oida_code.estimators.llm_prompt import LLMEvidencePacket
    from oida_code.verifier.contracts import (
        BackwardVerificationResult,
        ForwardVerificationResult,
    )

    try:
        LLMEvidencePacket.model_validate(data["packet"])
    except ValidationError as exc:
        _finding(
            findings,
            "error",
            "CONTRACT-PACKET",
            paths["packet"],
            str(exc),
        )
    for key in ("pass1_forward", "pass2_forward"):
        try:
            ForwardVerificationResult.model_validate(data[key])
        except ValidationError as exc:
            _finding(findings, "error", f"CONTRACT-{key}", paths[key], str(exc))
    for key in ("pass1_backward", "pass2_backward"):
        value = data[key]
        if not isinstance(value, list):
            _finding(
                findings,
                "error",
                f"CONTRACT-{key}",
                paths[key],
                f"{key}.json must be a JSON list",
            )
            continue
        for idx, entry in enumerate(value):
            try:
                BackwardVerificationResult.model_validate(entry)
            except ValidationError as exc:
                _finding(
                    findings,
                    "error",
                    f"CONTRACT-{key}",
                    paths[key],
                    f"entry {idx}: {exc}",
                )


def _evidence_kind_map(packet: dict[str, Any], grounded: dict[str, Any]) -> dict[str, str]:
    kinds: dict[str, str] = {}
    for item in packet.get("evidence_items", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            kind = item.get("kind")
            kinds[item["id"]] = kind if isinstance(kind, str) else "unknown"
    for result in grounded.get("tool_results", []):
        if not isinstance(result, dict):
            continue
        for item in result.get("evidence_items", []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                kind = item.get("kind")
                kinds[item["id"]] = kind if isinstance(kind, str) else "unknown"
    for ref in grounded.get("enriched_evidence_refs", []):
        if isinstance(ref, str) and ref not in kinds:
            kinds[ref] = "test_result" if ref.startswith("[E.tool.") else "unknown"
    return kinds


def _claim_ids(claims: Any) -> set[str]:
    if not isinstance(claims, list):
        return set()
    return {c["claim_id"] for c in claims if isinstance(c, dict) and "claim_id" in c}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]{4,}", text.lower())
        if token not in _STOPWORDS
    }


def _statement_matches_seed(statement: str, seed_claim_text: str) -> bool:
    statement_tokens = _tokens(statement)
    seed_tokens = _tokens(seed_claim_text)
    if not statement_tokens or not seed_tokens:
        return False
    overlap = statement_tokens & seed_tokens
    denominator = min(len(statement_tokens), len(seed_tokens))
    return (len(overlap) / denominator) >= 0.20


def _check_pass1(
    case_dir: Path,
    seed: dict[str, Any],
    pass1_forward: dict[str, Any],
    findings: list[Finding],
) -> None:
    tools = pass1_forward.get("requested_tools")
    if not isinstance(tools, list) or len(tools) != 1:
        _finding(
            findings,
            "error",
            "PASS1-TOOL-COUNT",
            case_dir / "pass1_forward.json",
            "pass1_forward must request exactly one tool",
        )
        return
    spec = tools[0]
    if not isinstance(spec, dict):
        _finding(
            findings,
            "error",
            "PASS1-TOOL-SHAPE",
            case_dir / "pass1_forward.json",
            "requested tool spec must be an object",
        )
        return
    if spec.get("tool") != "pytest":
        _finding(
            findings,
            "error",
            "PASS1-TOOL",
            case_dir / "pass1_forward.json",
            "pass1_forward must request pytest",
        )
    if spec.get("expected_evidence_kind") != "test_result":
        _finding(
            findings,
            "error",
            "PASS1-EVIDENCE-KIND",
            case_dir / "pass1_forward.json",
            "pytest request must expect test_result evidence",
        )
    scope = spec.get("scope")
    if scope != [seed.get("test_scope")]:
        _finding(
            findings,
            "error",
            "PASS1-SCOPE",
            case_dir / "pass1_forward.json",
            f"pytest scope {scope!r} does not match seed test_scope "
            f"{seed.get('test_scope')!r}",
        )


def _check_claim_refs(
    case_dir: Path,
    file_name: str,
    claims: Any,
    known_refs: dict[str, str],
    findings: list[Finding],
) -> None:
    if not isinstance(claims, list):
        return
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        for ref in claim.get("evidence_refs", []):
            if ref not in known_refs:
                _finding(
                    findings,
                    "error",
                    "REF-UNKNOWN",
                    case_dir / file_name,
                    f"claim {claim.get('claim_id')!r} cites unknown ref {ref!r}",
                )


def _check_pass2_forward(
    case_dir: Path,
    seed: dict[str, Any],
    pass2_forward: dict[str, Any],
    known_refs: dict[str, str],
    findings: list[Finding],
) -> None:
    expected_claim_id = seed.get("claim_id")
    expected_claim_type = seed.get("claim_type")
    seed_claim_text = str(seed.get("claim_text") or "")
    supported = pass2_forward.get("supported_claims")
    if not isinstance(supported, list):
        _finding(
            findings,
            "error",
            "PASS2-SUPPORTED-SHAPE",
            case_dir / "pass2_forward.json",
            "supported_claims must be a list",
        )
        return
    for claim in supported:
        if not isinstance(claim, dict):
            continue
        claim_id = claim.get("claim_id")
        if claim_id != expected_claim_id:
            _finding(
                findings,
                "error",
                "CLAIM-ID",
                case_dir / "pass2_forward.json",
                f"supported claim_id {claim_id!r} does not match seed "
                f"{expected_claim_id!r}",
            )
        if claim.get("claim_type") != expected_claim_type:
            _finding(
                findings,
                "error",
                "CLAIM-TYPE",
                case_dir / "pass2_forward.json",
                f"supported claim_type {claim.get('claim_type')!r} does not "
                f"match seed {expected_claim_type!r}",
            )
        if claim.get("event_id") != f"evt-{seed.get('case_id')}":
            _finding(
                findings,
                "error",
                "CLAIM-EVENT",
                case_dir / "pass2_forward.json",
                f"claim event_id {claim.get('event_id')!r} does not match "
                f"evt-{seed.get('case_id')}",
            )
        refs = claim.get("evidence_refs", [])
        if not any(isinstance(ref, str) and ref.startswith("[E.tool.") for ref in refs):
            _finding(
                findings,
                "error",
                "CLAIM-TOOL-EVIDENCE",
                case_dir / "pass2_forward.json",
                f"supported claim {claim_id!r} does not cite tool evidence",
            )
        statement = str(claim.get("statement") or "")
        if not _statement_matches_seed(statement, seed_claim_text):
            _finding(
                findings,
                "error",
                "CLAIM-TEXT",
                case_dir / "pass2_forward.json",
                f"supported claim statement does not share enough domain tokens "
                f"with seed claim_text for {claim_id!r}",
            )
    _check_claim_refs(
        case_dir,
        "pass2_forward.json",
        pass2_forward.get("supported_claims"),
        known_refs,
        findings,
    )
    _check_claim_refs(
        case_dir,
        "pass2_forward.json",
        pass2_forward.get("rejected_claims"),
        known_refs,
        findings,
    )


def _check_pass2_backward(
    case_dir: Path,
    seed: dict[str, Any],
    pass2_backward: list[Any],
    known_refs: dict[str, str],
    findings: list[Finding],
) -> None:
    expected_claim_id = seed.get("claim_id")
    entries_for_claim = 0
    for entry in pass2_backward:
        if not isinstance(entry, dict):
            continue
        if entry.get("claim_id") != expected_claim_id:
            _finding(
                findings,
                "error",
                "BACKWARD-CLAIM",
                case_dir / "pass2_backward.json",
                f"backward claim_id {entry.get('claim_id')!r} does not match "
                f"seed {expected_claim_id!r}",
            )
        else:
            entries_for_claim += 1
        if entry.get("event_id") != f"evt-{seed.get('case_id')}":
            _finding(
                findings,
                "error",
                "BACKWARD-EVENT",
                case_dir / "pass2_backward.json",
                f"backward event_id {entry.get('event_id')!r} does not match "
                f"evt-{seed.get('case_id')}",
            )
        requirement = entry.get("requirement")
        if not isinstance(requirement, dict):
            continue
        kinds = requirement.get("required_evidence_kinds")
        if not isinstance(kinds, list) or "test_result" not in kinds:
            _finding(
                findings,
                "error",
                "BACKWARD-TEST-REQUIREMENT",
                case_dir / "pass2_backward.json",
                "backward requirement must include test_result evidence",
            )
        satisfied = requirement.get("satisfied_evidence_refs")
        if not isinstance(satisfied, list):
            satisfied = []
        for ref in satisfied:
            if ref not in known_refs:
                _finding(
                    findings,
                    "error",
                    "BACKWARD-UNKNOWN-REF",
                    case_dir / "pass2_backward.json",
                    f"backward satisfied_evidence_refs cites unknown ref {ref!r}",
                )
        if entry.get("necessary_conditions_met") is True:
            has_test_ref = any(known_refs.get(ref) == "test_result" for ref in satisfied)
            if not has_test_ref:
                _finding(
                    findings,
                    "error",
                    "BACKWARD-SATISFIED-TEST-REF",
                    case_dir / "pass2_backward.json",
                    "necessary_conditions_met=true but no satisfied ref has "
                    "kind test_result",
                )
    if entries_for_claim == 0:
        _finding(
            findings,
            "error",
            "BACKWARD-MISSING-CLAIM",
            case_dir / "pass2_backward.json",
            f"no pass2 backward entry for seed claim {expected_claim_id!r}",
        )


def _check_grounded_report(
    case_dir: Path,
    pass2_forward: dict[str, Any],
    grounded: dict[str, Any],
    findings: list[Finding],
) -> None:
    supported_ids = _claim_ids(pass2_forward.get("supported_claims"))
    report = grounded.get("report")
    if not isinstance(report, dict):
        _finding(
            findings,
            "error",
            "REPORT-SHAPE",
            case_dir / "grounded_report.json",
            "grounded_report.report must be an object",
        )
        return
    accepted_ids = _claim_ids(report.get("accepted_claims"))
    extra = accepted_ids - supported_ids
    if extra:
        _finding(
            findings,
            "error",
            "REPORT-ACCEPTED-SUBSET",
            case_dir / "grounded_report.json",
            "grounded_report accepted claims absent from pass2_forward "
            f"supported_claims: {sorted(extra)}",
        )


def audit_case_dir(case_dir: Path, seed_records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[Finding] = []
    case_id = case_dir.name
    paths = {name.removesuffix(".json"): case_dir / name for name in _REQUIRED_FILES}

    for name in _REQUIRED_FILES:
        if not (case_dir / name).is_file():
            _finding(
                findings,
                "error",
                "FILE-MISSING",
                case_dir / name,
                f"required file {name} is missing",
            )

    if any(f.invariant_id == "FILE-MISSING" for f in findings):
        return _case_result(case_id, case_dir, findings)

    data: dict[str, Any] = {}
    for name in _REQUIRED_FILES:
        key = name.removesuffix(".json")
        value = _load_json(case_dir / name, findings)
        if value is not None:
            data[key] = value

    if len(data) != len(_REQUIRED_FILES):
        return _case_result(case_id, case_dir, findings)

    _validate_contracts(data, paths, findings)

    seed = seed_records.get(case_id)
    if seed is None:
        _finding(
            findings,
            "error",
            "SEED-MISSING",
            case_dir,
            f"case_id {case_id!r} not found in calibration_seed index",
        )
        return _case_result(case_id, case_dir, findings)

    expected_event_id = f"evt-{case_id}"
    if data["packet"].get("event_id") != expected_event_id:
        _finding(
            findings,
            "error",
            "PACKET-EVENT",
            case_dir / "packet.json",
            f"packet event_id {data['packet'].get('event_id')!r} does not "
            f"match {expected_event_id!r}",
        )

    known_refs = _evidence_kind_map(data["packet"], data["grounded_report"])
    _check_pass1(case_dir, seed, data["pass1_forward"], findings)
    _check_pass2_forward(
        case_dir,
        seed,
        data["pass2_forward"],
        known_refs,
        findings,
    )
    pass2_backward = data["pass2_backward"]
    if isinstance(pass2_backward, list):
        _check_pass2_backward(case_dir, seed, pass2_backward, known_refs, findings)
    _check_grounded_report(
        case_dir,
        data["pass2_forward"],
        data["grounded_report"],
        findings,
    )

    return _case_result(case_id, case_dir, findings)


def _case_result(
    case_id: str,
    case_dir: Path,
    findings: list[Finding],
) -> dict[str, Any]:
    error_count = sum(1 for f in findings if f.severity == "error")
    warning_count = sum(1 for f in findings if f.severity == "warning")
    return {
        "case_id": case_id,
        "path": _rel(case_dir),
        "status": "fail" if error_count else "pass",
        "error_count": error_count,
        "warning_count": warning_count,
        "findings": [f.to_json() for f in findings],
    }


def audit_round_trip_dirs(
    round_trip_dirs: list[Path],
    *,
    index_path: Path = _DEFAULT_INDEX,
) -> dict[str, Any]:
    seed_records = _load_seed_records(index_path)
    cases = [audit_case_dir(path, seed_records) for path in round_trip_dirs]
    total_errors = sum(int(case["error_count"]) for case in cases)
    total_warnings = sum(int(case["warning_count"]) for case in cases)
    passed = sum(1 for case in cases if case["status"] == "pass")
    failed = len(cases) - passed
    return {
        "script_version": SCRIPT_VERSION,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "audit_scope": AUDIT_SCOPE,
        "semantic_truth_validated": SEMANTIC_TRUTH_VALIDATED,
        "index_path": _rel(index_path),
        "summary": {
            "case_count": len(cases),
            "passed": passed,
            "failed": failed,
            "error_count": total_errors,
            "warning_count": total_warnings,
        },
        "cases": cases,
    }


def write_report(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "audit.json"
    md_path = out_dir / "audit.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return json_path, md_path


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase 6.a replay-content static audit",
        "",
        f"Generated at: `{report['generated_at']}`.",
        f"Script version: `{report['script_version']}`.",
        f"Audit scope: `{report['audit_scope']}`.",
        f"Semantic truth validated: `{str(report['semantic_truth_validated']).lower()}`.",
        "",
        "This audit checks static content consistency only. A passing case",
        "does not prove provider-independent replay validity, upstream PR",
        "truth, product safety, or semantic correctness.",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Errors: {summary['error_count']}",
        f"- Warnings: {summary['warning_count']}",
        "",
        "## Cases",
        "",
    ]
    for case in report["cases"]:
        lines.extend(
            [
                f"### `{case['case_id']}`",
                "",
                f"- Path: `{case['path']}`",
                f"- Status: `{case['status']}`",
                f"- Errors: {case['error_count']}",
                f"- Warnings: {case['warning_count']}",
                "",
            ],
        )
        findings = case["findings"]
        if not findings:
            lines.extend(["No static inconsistency detected.", ""])
            continue
        lines.extend(["| Severity | Invariant | Path | Message |", "|---|---|---|---|"])
        for finding in findings:
            message = str(finding["message"]).replace("|", "\\|")
            lines.append(
                f"| {finding['severity']} | {finding['invariant_id']} | "
                f"`{finding['path']}` | {message} |",
            )
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline static audit for LLM-authored replay content.",
    )
    parser.add_argument(
        "round_trip_dirs",
        nargs="+",
        type=Path,
        help="Archived round_trip_outputs/<case_id> directories to audit.",
    )
    parser.add_argument("--index", type=Path, default=_DEFAULT_INDEX)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    report = audit_round_trip_dirs(args.round_trip_dirs, index_path=args.index)
    json_path, md_path = write_report(report, args.out_dir)
    summary = report["summary"]
    print(f"wrote {_rel(json_path)}")
    print(f"wrote {_rel(md_path)}")
    print(
        "static replay audit: "
        f"{summary['passed']} passed / {summary['failed']} failed; "
        f"errors={summary['error_count']} warnings={summary['warning_count']}",
    )
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
