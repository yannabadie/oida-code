"""Phase 6.1'b (ADR-55) — bundle skeleton generator implementation.

The generator consumes a Tier-3-complete seed-corpus inclusion
record (see ADR-54) and emits a directory containing the eight
files the verifier requires plus a README.md.

NO NETWORK CALLS. NO PROVIDER CALLS. NO MCP RUNTIME.
Stdlib only. The generator stays under ``src/oida_code/`` because
it is local composition; per ADR-53 frontière rule 1, scripts
that need network credentials live under ``scripts/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_TIER_3_FIELDS: tuple[str, ...] = (
    "claim_id",
    "claim_type",
    "claim_text",
    "test_scope",
    "evidence_items",
)
"""ADR-54 Tier-3 fields. The generator refuses if any is missing
or null. The skeleton refusal is deliberate — partial seed
records produce ill-formed bundles downstream."""

_REQUIRED_TIER_2_FIELDS: tuple[str, ...] = (
    "expected_grounding_outcome",
    "label_source",
)

_TIER_1_REQUIRED: tuple[str, ...] = (
    "case_id",
    "repo_url",
    "pr_number",
    "head_sha",
    "base_sha",
)

_SKELETON_NOTE: str = (
    "phase6.1.b skeleton — verifier replays are operator/"
    "Phase-6.1'd responsibility (deterministic stubs would be theatre)"
)

_EVIDENCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "id", "kind", "summary", "source", "confidence",
)

_ALLOWED_EVIDENCE_KINDS: frozenset[str] = frozenset({
    "intent", "event", "precondition", "tool_finding",
    "test_result", "graph_edge", "trajectory", "repair_signal",
})

_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "v_net", "total_v_net", "debt_final", "debt-final",
    "corrupt_success", "corrupt-success", "verdict",
    "merge-safe", "merge_safe", "production-safe",
    "production_safe", "bug-free", "bug_free",
    "security-verified", "security_verified",
)


class BundleGenerationError(Exception):
    """Raised when the seed record is not Tier-3-complete or
    the generator's input violates a structural invariant."""


@dataclass(frozen=True)
class GeneratedBundle:
    """Result of a successful bundle generation."""

    out_dir: Path
    files: tuple[Path, ...]


def generate_bundle(
    seed_record: dict[str, Any], out_dir: Path,
) -> GeneratedBundle:
    """Emit the 8 required bundle files plus a README.

    Returns a :class:`GeneratedBundle` listing the produced
    files. Raises :class:`BundleGenerationError` if the input
    record is partial or malformed.
    """
    _validate_seed_record(seed_record)
    out_dir.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    files.append(_write_packet(seed_record, out_dir))
    files.append(_write_tool_policy(out_dir))
    files.append(_write_gateway_definitions(out_dir))
    files.append(_write_approved_tools(out_dir))
    files.append(_write_pass1_forward_stub(seed_record, out_dir))
    files.append(_write_pass1_backward_stub(seed_record, out_dir))
    files.append(_write_pass2_forward_stub(seed_record, out_dir))
    files.append(_write_pass2_backward_stub(seed_record, out_dir))
    files.append(_write_bundle_readme(seed_record, out_dir))
    return GeneratedBundle(out_dir=out_dir, files=tuple(files))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_seed_record(seed_record: dict[str, Any]) -> None:
    if not isinstance(seed_record, dict):
        raise BundleGenerationError(
            f"seed_record must be a dict; got "
            f"{type(seed_record).__name__}",
        )

    for field_ in _TIER_1_REQUIRED:
        if not seed_record.get(field_):
            raise BundleGenerationError(
                f"seed_record missing Tier-1 field {field_!r}",
            )

    for field_ in _REQUIRED_TIER_2_FIELDS:
        if not seed_record.get(field_):
            raise BundleGenerationError(
                f"seed_record missing Tier-2 field {field_!r}",
            )
    if seed_record.get("expected_grounding_outcome") == "not_run":
        raise BundleGenerationError(
            "seed_record has expected_grounding_outcome='not_run'; "
            "the generator refuses partial records (per ADR-55).",
        )

    missing_tier_3: list[str] = []
    for field_ in REQUIRED_TIER_3_FIELDS:
        v = seed_record.get(field_)
        if v is None:
            missing_tier_3.append(field_)
            continue
        if isinstance(v, list) and not v:
            missing_tier_3.append(field_)
    if missing_tier_3:
        raise BundleGenerationError(
            "seed_record is not Tier-3-complete (per ADR-54). "
            f"missing/empty fields: {missing_tier_3}. The bundle "
            "generator refuses partial records.",
        )

    if seed_record.get("human_review_required", True) is True:
        raise BundleGenerationError(
            "seed_record has human_review_required=true; the "
            "generator only consumes reviewed records.",
        )

    for i, item in enumerate(seed_record["evidence_items"]):
        if not isinstance(item, dict):
            raise BundleGenerationError(
                f"evidence_items[{i}] is not a dict",
            )
        for f in _EVIDENCE_REQUIRED_FIELDS:
            if f not in item:
                raise BundleGenerationError(
                    f"evidence_items[{i}] missing field {f!r}",
                )
        kind = item["kind"]
        if kind not in _ALLOWED_EVIDENCE_KINDS:
            raise BundleGenerationError(
                f"evidence_items[{i}].kind={kind!r} is not in "
                f"{sorted(_ALLOWED_EVIDENCE_KINDS)}",
            )
        conf = item["confidence"]
        if not isinstance(conf, (int, float)):
            raise BundleGenerationError(
                f"evidence_items[{i}].confidence is not numeric",
            )
        if not 0.0 <= float(conf) <= 1.0:
            raise BundleGenerationError(
                f"evidence_items[{i}].confidence={conf} not in "
                "[0.0, 1.0]",
            )
        summary = item.get("summary", "")
        if len(summary) > 400:
            raise BundleGenerationError(
                f"evidence_items[{i}].summary exceeds 400 chars",
            )

    _check_forbidden_phrases(seed_record)


def _check_forbidden_phrases(seed_record: dict[str, Any]) -> None:
    haystacks: list[str] = []
    haystacks.append(str(seed_record.get("claim_id", "")))
    haystacks.append(str(seed_record.get("claim_text", "")))
    haystacks.append(str(seed_record.get("title", "")))
    for item in seed_record.get("evidence_items") or []:
        haystacks.append(str(item.get("summary", "")))
    blob = " ".join(haystacks).lower()
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in blob:
            raise BundleGenerationError(
                f"seed_record carries forbidden phrase {phrase!r}; "
                "ADR-22/24/25/26 hard wall preserved.",
            )


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------


def _event_id(seed_record: dict[str, Any]) -> str:
    return f"evt-{seed_record['case_id']}"


def _dump(path: Path, body: Any) -> Path:
    path.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _write_packet(
    seed_record: dict[str, Any], out_dir: Path,
) -> Path:
    intent = (
        f"Phase 6.1'b auto-generated bundle for case_id "
        f"{seed_record['case_id']} ({seed_record['repo_url']} "
        f"PR #{seed_record['pr_number']}, head_sha "
        f"{str(seed_record['head_sha'])[:8]}). Claim "
        f"{seed_record['claim_id']} (type "
        f"{seed_record['claim_type']}); test_scope "
        f"{seed_record['test_scope']}."
    )[:400]
    packet = {
        "event_id": _event_id(seed_record),
        "allowed_fields": [
            "capability", "tests_pass", "operator_accept",
        ],
        "intent_summary": intent,
        "evidence_items": list(seed_record["evidence_items"]),
        "deterministic_estimates": [],
    }
    return _dump(out_dir / "packet.json", packet)


def _write_tool_policy(out_dir: Path) -> Path:
    body = {
        "allowed_tools": ["pytest"],
        "repo_root": ".",
        "allowed_paths": [],
        "deny_patterns": [
            ".env", ".env.*", "*.key", "*.pem", "*secret*",
            "*.token", ".git/config", ".git/hooks/*",
            "id_rsa", "id_ed25519",
        ],
        "allow_network": False,
        "allow_write": False,
        "max_tool_calls": 5,
        "max_total_runtime_s": 60,
        "max_output_chars_per_tool": 8000,
    }
    return _dump(out_dir / "tool_policy.json", body)


def _write_gateway_definitions(out_dir: Path) -> Path:
    body = {
        "pytest": {
            "tool_id": "oida-code/pytest",
            "tool_name": "pytest",
            "adapter_version": "0.4.0",
            "description": "Run pytest (read-only).",
            "input_schema": {
                "type": "object",
                "properties": {"scope": {"type": "array"}},
            },
            "output_schema": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
            },
            "risk_level": "read_only",
            "allowed_scopes": ["repo:read"],
            "requires_network": False,
            "allows_write": False,
        },
    }
    return _dump(out_dir / "gateway_definitions.json", body)


def _write_approved_tools(out_dir: Path) -> Path:
    return _dump(out_dir / "approved_tools.json", ["pytest"])


def _write_pass1_forward_stub(
    seed_record: dict[str, Any], out_dir: Path,
) -> Path:
    purpose = (
        f"Run pytest scoped to {seed_record['test_scope']}; "
        f"clean pass grounds {seed_record['claim_id']}."
    )[:200]
    body = {
        "event_id": _event_id(seed_record),
        "supported_claims": [],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [_SKELETON_NOTE],
        "requested_tools": [
            {
                "tool": "pytest",
                "purpose": purpose,
                "expected_evidence_kind": "test_result",
                "scope": [seed_record["test_scope"]],
            },
        ],
    }
    return _dump(out_dir / "pass1_forward.json", body)


def _backward_body(
    seed_record: dict[str, Any], pass_label: str,
) -> dict[str, Any]:
    return {
        "event_id": _event_id(seed_record),
        "claim_id": seed_record["claim_id"],
        "requirement": {
            "claim_id": seed_record["claim_id"],
            "required_evidence_kinds": ["test_result"],
            "satisfied_evidence_refs": [],
            "missing_requirements": [
                f"{pass_label} backward replay is operator/"
                "Phase-6.1'd responsibility",
            ],
        },
        "necessary_conditions_met": False,
        "warnings": [_SKELETON_NOTE],
    }


def _write_pass1_backward_stub(
    seed_record: dict[str, Any], out_dir: Path,
) -> Path:
    return _dump(
        out_dir / "pass1_backward.json",
        _backward_body(seed_record, "pass-1"),
    )


def _write_pass2_forward_stub(
    seed_record: dict[str, Any], out_dir: Path,
) -> Path:
    body = {
        "event_id": _event_id(seed_record),
        "supported_claims": [],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [_SKELETON_NOTE],
        "requested_tools": [],
    }
    return _dump(out_dir / "pass2_forward.json", body)


def _write_pass2_backward_stub(
    seed_record: dict[str, Any], out_dir: Path,
) -> Path:
    return _dump(
        out_dir / "pass2_backward.json",
        _backward_body(seed_record, "pass-2"),
    )


def _write_bundle_readme(
    seed_record: dict[str, Any], out_dir: Path,
) -> Path:
    body = (
        f"# Bundle for `{seed_record['case_id']}` (Phase 6.1'b skeleton)\n\n"
        f"This bundle was auto-generated by `oida-code "
        f"prepare-gateway-bundle` from a Tier-3-complete record in "
        f"`reports/calibration_seed/index.json`.\n\n"
        f"**Source:** {seed_record['repo_url']} PR #"
        f"{seed_record['pr_number']}\n\n"
        f"**Claim:** `{seed_record['claim_id']}` "
        f"(type=`{seed_record['claim_type']}`)\n\n"
        f"**Base SHA:** `{seed_record['base_sha']}`\n\n"
        f"**Head SHA:** `{seed_record['head_sha']}`\n\n"
        f"**Test scope:** `{seed_record['test_scope']}`\n\n"
        f"**Expected grounding outcome:** "
        f"`{seed_record['expected_grounding_outcome']}`\n\n"
        f"## What this bundle is\n\n"
        f"A skeleton — the four input files "
        f"(`packet.json`, `tool_policy.json`, "
        f"`gateway_definitions.json`, `approved_tools.json`) are "
        f"complete and Pydantic-valid against the verifier "
        f"contracts. The four `pass*_*.json` files are "
        f"minimal-schema-valid stubs whose `warnings` array "
        f"explicitly says the verifier replays are operator / "
        f"Phase-6.1'd responsibility. The skeleton bundle is "
        f"structurally valid against `validate-gateway-bundle` but "
        f"is NOT a runnable verifier round-trip. That is "
        f"Phase 6.1'd's job.\n\n"
        f"## What this bundle is NOT\n\n"
        f"* It is NOT proof that the upstream change is correct.\n"
        f"* It is NOT a product verdict (no merge-safe / "
        f"production-safe / bug-free / verified language).\n"
        f"* It is NOT external-human beta evidence (per ADR-52 "
        f"the human-beta lane is `not_run`).\n"
        f"* It is NOT runnable through verify-grounded without "
        f"hand-authored or LLM-authored replay JSONs replacing "
        f"the four `pass*_*.json` skeleton stubs.\n\n"
        f"## How to use it (Phase 6.1'd preview)\n\n"
        f"In Phase 6.1'd, the operator OR an LLM-as-replayer "
        f"will overwrite the four `pass*_*.json` stubs with "
        f"meaningful verifier replies, then invoke "
        f"`oida-code verify-grounded` with this directory. The "
        f"`warnings` array in each stub names the deferred "
        f"responsibility explicitly.\n\n"
        f"## Cross-references\n\n"
        f"* Seed record: `reports/calibration_seed/index.json::"
        f"{seed_record['case_id']}`\n"
        f"* Worked-example walk-through: "
        f"`reports/calibration_seed/worked_example_phase6_1_a.md`\n"
        f"* ADR-55: `memory-bank/decisionLog.md`\n"
        f"* Generator: `src/oida_code/bundle/generator.py`\n"
    )
    p = out_dir / "README.md"
    p.write_text(body, encoding="utf-8")
    return p
