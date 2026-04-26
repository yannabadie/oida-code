"""Phase 5.5 (QA/A32.md, ADR-40) — fixture builder for the
four mandatory new cases that bring the public synthetic
gateway holdout from 8 to 12 cases.

Usage::

    python scripts/_build_phase5_5_cases.py

Writes under ``datasets/gateway_holdout_public_v1/cases/``.
The four cases are:

* ``tool_missing_uncertainty`` — gateway requests pytest;
  executor returns ``returncode: null`` (binary missing);
  adapter emits ``status="tool_missing"``; Phase 5.2.1-B
  enforcer demotes the pass-2 accepted claim to unsupported.
  ``tool_missing != code failure`` — uncertainty preserved.

* ``tool_timeout_uncertainty`` — gateway requests pytest;
  executor returns ``timed_out: true``; adapter emits
  ``status="timeout"``; Phase 5.2.1-B enforcer demotes the
  pass-2 accepted claim. ``timeout != deterministic
  contradiction``.

* ``multi_tool_static_then_test`` — pass-1 requests ruff +
  mypy + pytest; executor returns ok/ok/failed via the
  ``by_tool`` schema; aggregator's tool-contradiction rule
  rejects the LLM's ``C.fix`` claim because pytest reported
  ``status="failed"``. Static checks alone do not promote
  past a deterministic test failure.

* ``duplicate_tool_request_budget`` — pass-1 requests pytest
  three times (all identical); the gateway loop's
  ``max_tool_calls`` cap leaves only the budgeted N
  invocations in the audit log. No autonomous loop.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_HOLDOUT = REPO_ROOT / "datasets" / "gateway_holdout_public_v1"


PYTEST_DEF = {
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
}

RUFF_DEF = {
    **PYTEST_DEF,
    "tool_id": "oida-code/ruff",
    "tool_name": "ruff",
    "description": "Run ruff (read-only).",
}

MYPY_DEF = {
    **PYTEST_DEF,
    "tool_id": "oida-code/mypy",
    "tool_name": "mypy",
    "description": "Run mypy (read-only).",
}


PYTEST_FP = {
    "tool_id": "oida-code/pytest",
    "tool_name": "pytest",
    "adapter_version": "0.4.0",
    "description_sha256": (
        "7f0121e7d91d3779beff6cedfa218a97e60032f50cd5e807873c1417f839d990"
    ),
    "input_schema_sha256": (
        "670153ef31c426139cc4234280dff172579a136b187dabb67064670a1503f793"
    ),
    "output_schema_sha256": (
        "c0c2eeb06783383e6eadec2cdd682ce2f33468051952b39d94ef352e629a1698"
    ),
    "combined_sha256": (
        "6d3fa08a9f7be722f8911282e0829b8baaf332866dd0f495f3339d95c1bb2140"
    ),
}

RUFF_FP = {
    "tool_id": "oida-code/ruff",
    "tool_name": "ruff",
    "adapter_version": "0.4.0",
    "description_sha256": (
        "43138b55d35c960ee25fd625faac198c380cf05dcf67d61f585330de2c3a12bf"
    ),
    "input_schema_sha256": (
        "670153ef31c426139cc4234280dff172579a136b187dabb67064670a1503f793"
    ),
    "output_schema_sha256": (
        "c0c2eeb06783383e6eadec2cdd682ce2f33468051952b39d94ef352e629a1698"
    ),
    "combined_sha256": (
        "c946883d396e82119b8699a23964712b50ce62e1a1d13dcfae68a7d09a415301"
    ),
}

MYPY_FP = {
    "tool_id": "oida-code/mypy",
    "tool_name": "mypy",
    "adapter_version": "0.4.0",
    "description_sha256": (
        "015551a200cdd40107a8c3153953541cab5c412dfe51b457ac83754e73009eef"
    ),
    "input_schema_sha256": (
        "670153ef31c426139cc4234280dff172579a136b187dabb67064670a1503f793"
    ),
    "output_schema_sha256": (
        "c0c2eeb06783383e6eadec2cdd682ce2f33468051952b39d94ef352e629a1698"
    ),
    "combined_sha256": (
        "3e5e6172e267f6a443aa6d4c1ecb34ab760e21490baa5a00793f1b59b374db3e"
    ),
}

DEFAULT_TOOL_POLICY = {
    "allowed_tools": ["ruff", "mypy", "pytest"],
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

DEFAULT_PACKET = {
    "event_id": "evt-1",
    "allowed_fields": ["capability", "benefit", "observability"],
    "intent_summary": "ship feature with passing tests",
    "evidence_items": [
        {
            "id": "[E.event.1]",
            "kind": "event",
            "summary": "feature event captured from intent doc",
            "source": "ticket",
            "confidence": 0.9,
        },
    ],
    "deterministic_estimates": [],
}


_FP_BY_NAME: dict[str, dict[str, str]] = {
    "pytest": PYTEST_FP,
    "ruff": RUFF_FP,
    "mypy": MYPY_FP,
}


def _w(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )


def _approved(
    definitions: list[dict[str, object]],
) -> dict[str, object]:
    approved = []
    for d in definitions:
        name = d["tool_name"]
        fingerprint = _FP_BY_NAME.get(str(name))
        if fingerprint is None:
            raise ValueError(
                f"unhandled tool_name {name!r}; extend the builder"
            )
        approved.append({
            "tool_id": d["tool_id"],
            "status": "approved_read_only",
            "reason": "synthetic public holdout approval (Phase 5.5)",
            "fingerprint": fingerprint,
        })
    return {
        "approved": approved,
        "quarantined": [],
        "rejected": [],
    }


def _claim_accepted(claim_id: str = "C.cap") -> dict[str, object]:
    return {
        "event_id": "evt-1",
        "supported_claims": [
            {
                "claim_id": claim_id,
                "event_id": "evt-1",
                "claim_type": "capability_sufficient",
                "statement": "claim accepted on event evidence",
                "confidence": 0.55,
                "evidence_refs": ["[E.event.1]"],
                "source": "forward",
            },
        ],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [],
    }


def _backward_met(
    claim_id: str = "C.cap",
) -> list[dict[str, object]]:
    return [
        {
            "event_id": "evt-1",
            "claim_id": claim_id,
            "requirement": {
                "claim_id": claim_id,
                "required_evidence_kinds": ["event"],
                "satisfied_evidence_refs": ["[E.event.1]"],
                "missing_requirements": [],
            },
            "necessary_conditions_met": True,
        },
    ]


def _request_pytest_forward() -> dict[str, object]:
    return {
        "event_id": "evt-1",
        "supported_claims": [],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [],
        "requested_tools": [
            {
                "tool": "pytest",
                "purpose": "re-run pytest scoped to tests/",
                "expected_evidence_kind": "test_result",
                "scope": ["tests"],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Case 9 — tool_missing_uncertainty
# ---------------------------------------------------------------------------


def build_tool_missing_uncertainty() -> None:
    case_dir = PUBLIC_HOLDOUT / "cases" / "tool_missing_uncertainty"
    _w(case_dir / "packet.json", DEFAULT_PACKET)
    _w(case_dir / "baseline_forward.json", _claim_accepted("C.cap"))
    _w(case_dir / "baseline_backward.json", _backward_met("C.cap"))
    _w(case_dir / "gateway_pass1_forward.json",
       _request_pytest_forward())
    _w(case_dir / "gateway_pass1_backward.json", [])
    # Pass-2 forward keeps accepting on event evidence — but
    # because the tool was requested AND no [E.tool.*] evidence
    # made it back into the packet (binary missing), the Phase
    # 5.2.1-B enforcer demotes the claim to unsupported.
    _w(case_dir / "gateway_pass2_forward.json", _claim_accepted("C.cap"))
    _w(case_dir / "gateway_pass2_backward.json", _backward_met("C.cap"))
    _w(case_dir / "tool_policy.json", DEFAULT_TOOL_POLICY)
    _w(case_dir / "gateway_definitions.json", {"pytest": PYTEST_DEF})
    _w(case_dir / "approved_tools.json", _approved([PYTEST_DEF]))
    # Executor: returncode=None → status="tool_missing" → no
    # evidence emitted by the adapter.
    _w(case_dir / "executor.json", {
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "timed_out": False,
        "runtime_ms": 0,
    })
    _w(case_dir / "expected.json", {
        "case_id": "tool_missing_uncertainty",
        "expected_baseline": {
            "accepted_claim_ids": ["C.cap"],
            "unsupported_claim_ids": [],
            "rejected_claim_ids": [],
            "blockers_expected": [],
            "warnings_expected": [],
        },
        "expected_gateway": {
            "accepted_claim_ids": [],
            "unsupported_claim_ids": ["C.cap"],
            "rejected_claim_ids": [],
            "blockers_expected": [
                "requested tool ran but emitted no citable evidence",
            ],
            "warnings_expected": [],
        },
        "expected_delta": "improves",
        "required_tool_evidence_refs": [],
        "forbidden_acceptance_reasons": [
            "tool_missing must not be treated as code failure",
        ],
    })
    _w(case_dir / "README.md", (
        "# Case `tool_missing_uncertainty`\n\n"
        "Family: gateway_grounded. Expected delta: `improves`.\n\n"
        "Phase 5.5 §5.5-A. The executor returns "
        "`returncode=null` so the pytest binary is treated as "
        "missing on PATH. The adapter emits "
        "`status=\"tool_missing\"` with no `[E.tool.pytest.*]` "
        "evidence; Phase 5.2.1-B's `_enforce_requested_tool_"
        "evidence` enforcer demotes the pass-2 accepted claim "
        "to `unsupported`. The case proves the gateway "
        "preserves uncertainty when a tool is unavailable — it "
        "does NOT reject the claim as if the code were broken. "
        "Baseline accepts on event evidence alone (no tool "
        "ever queried).\n"
    ))


# ---------------------------------------------------------------------------
# Case 10 — tool_timeout_uncertainty
# ---------------------------------------------------------------------------


def build_tool_timeout_uncertainty() -> None:
    case_dir = PUBLIC_HOLDOUT / "cases" / "tool_timeout_uncertainty"
    _w(case_dir / "packet.json", DEFAULT_PACKET)
    _w(case_dir / "baseline_forward.json", _claim_accepted("C.cap"))
    _w(case_dir / "baseline_backward.json", _backward_met("C.cap"))
    _w(case_dir / "gateway_pass1_forward.json",
       _request_pytest_forward())
    _w(case_dir / "gateway_pass1_backward.json", [])
    _w(case_dir / "gateway_pass2_forward.json", _claim_accepted("C.cap"))
    _w(case_dir / "gateway_pass2_backward.json", _backward_met("C.cap"))
    _w(case_dir / "tool_policy.json", DEFAULT_TOOL_POLICY)
    _w(case_dir / "gateway_definitions.json", {"pytest": PYTEST_DEF})
    _w(case_dir / "approved_tools.json", _approved([PYTEST_DEF]))
    # Executor: timed_out=True → status="timeout" → no evidence.
    _w(case_dir / "executor.json", {
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "timed_out": True,
        "runtime_ms": 60000,
    })
    _w(case_dir / "expected.json", {
        "case_id": "tool_timeout_uncertainty",
        "expected_baseline": {
            "accepted_claim_ids": ["C.cap"],
            "unsupported_claim_ids": [],
            "rejected_claim_ids": [],
            "blockers_expected": [],
            "warnings_expected": [],
        },
        "expected_gateway": {
            "accepted_claim_ids": [],
            "unsupported_claim_ids": ["C.cap"],
            "rejected_claim_ids": [],
            "blockers_expected": [
                "requested tool ran but emitted no citable evidence",
            ],
            "warnings_expected": [
                "pytest exceeded budget",
            ],
        },
        "expected_delta": "improves",
        "required_tool_evidence_refs": [],
        "forbidden_acceptance_reasons": [
            "timeout must not be a deterministic contradiction",
        ],
    })
    _w(case_dir / "README.md", (
        "# Case `tool_timeout_uncertainty`\n\n"
        "Family: gateway_grounded. Expected delta: `improves`.\n\n"
        "Phase 5.5 §5.5-A. The executor returns "
        "`timed_out=true`; the adapter emits "
        "`status=\"timeout\"` with no `[E.tool.*]` evidence. "
        "Phase 5.2.1-B's enforcer demotes the pass-2 accepted "
        "claim to `unsupported` AND emits a budget warning. "
        "The case proves a timeout is uncertainty, not a "
        "deterministic negative tests_pass signal — the claim "
        "must NOT be rejected as if the code were broken. "
        "Baseline accepts on event evidence alone.\n"
    ))


# ---------------------------------------------------------------------------
# Case 11 — multi_tool_static_then_test
# ---------------------------------------------------------------------------


def build_multi_tool_static_then_test() -> None:
    case_dir = PUBLIC_HOLDOUT / "cases" / "multi_tool_static_then_test"
    _w(case_dir / "packet.json", DEFAULT_PACKET)
    _w(case_dir / "baseline_forward.json", _claim_accepted("C.fix"))
    _w(case_dir / "baseline_backward.json", _backward_met("C.fix"))
    # Pass-1 requests three tools; the budget cap is 5 so all
    # three run.
    _w(case_dir / "gateway_pass1_forward.json", {
        "event_id": "evt-1",
        "supported_claims": [],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [],
        "requested_tools": [
            {
                "tool": "ruff",
                "purpose": "static lint",
                "expected_evidence_kind": "lint_finding",
                "scope": ["src"],
            },
            {
                "tool": "mypy",
                "purpose": "static type check",
                "expected_evidence_kind": "type_finding",
                "scope": ["src"],
            },
            {
                "tool": "pytest",
                "purpose": "test scope",
                "expected_evidence_kind": "test_result",
                "scope": ["tests"],
            },
        ],
    })
    _w(case_dir / "gateway_pass1_backward.json", [])
    # Pass-2 forward attempts to support the fix despite the
    # pytest failure. The aggregator rejects the claim because
    # the deterministic negative tests_pass estimate from
    # pytest contradicts it.
    _w(case_dir / "gateway_pass2_forward.json", {
        "event_id": "evt-1",
        "supported_claims": [
            {
                "claim_id": "C.fix",
                "event_id": "evt-1",
                "claim_type": "capability_sufficient",
                "statement": "fix lands; static checks clean",
                "confidence": 0.55,
                "evidence_refs": [
                    "[E.event.1]", "[E.tool.pytest.0]",
                ],
                "source": "forward",
            },
        ],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [],
        "requested_tools": [],
    })
    _w(case_dir / "gateway_pass2_backward.json", _backward_met("C.fix"))
    _w(case_dir / "tool_policy.json", DEFAULT_TOOL_POLICY)
    _w(case_dir / "gateway_definitions.json", {
        "ruff": RUFF_DEF, "mypy": MYPY_DEF, "pytest": PYTEST_DEF,
    })
    _w(case_dir / "approved_tools.json",
       _approved([RUFF_DEF, MYPY_DEF, PYTEST_DEF]))
    # Per-tool executor outcomes via the Phase 5.5 ``by_tool``
    # schema. Ruff & mypy come back ok (no findings); pytest
    # comes back rc=1 with a FAILED line.
    _w(case_dir / "executor.json", {
        "by_tool": {
            "ruff": {
                "returncode": 0,
                "stdout": "[]",
                "stderr": "",
                "timed_out": False,
                "runtime_ms": 8,
            },
            "mypy": {
                "returncode": 0,
                "stdout": "Success: no issues found in 1 source file\n",
                "stderr": "",
                "timed_out": False,
                "runtime_ms": 11,
            },
            "pytest": {
                "returncode": 1,
                "stdout": (
                    "FAILED tests/test_feature.py::test_critical_fix\n"
                    "=== 1 failed, 4 passed in 0.4s ==="
                ),
                "stderr": "",
                "timed_out": False,
                "runtime_ms": 14,
            },
        },
    })
    _w(case_dir / "expected.json", {
        "case_id": "multi_tool_static_then_test",
        "expected_baseline": {
            "accepted_claim_ids": ["C.fix"],
            "unsupported_claim_ids": [],
            "rejected_claim_ids": [],
            "blockers_expected": [],
            "warnings_expected": [],
        },
        "expected_gateway": {
            "accepted_claim_ids": [],
            "unsupported_claim_ids": [],
            "rejected_claim_ids": ["C.fix"],
            "blockers_expected": [],
            "warnings_expected": [],
        },
        "expected_delta": "improves",
        "required_tool_evidence_refs": ["[E.tool.pytest.0]"],
        "forbidden_acceptance_reasons": [
            "pytest reported a deterministic test failure; "
            "static checks alone cannot promote past it",
        ],
    })
    _w(case_dir / "README.md", (
        "# Case `multi_tool_static_then_test`\n\n"
        "Family: gateway_grounded. Expected delta: "
        "`improves`.\n\n"
        "Phase 5.5 §5.5-A. Pass-1 requests three tools (ruff "
        "+ mypy + pytest) inside the per-case "
        "`max_tool_calls=5` budget. The Phase 5.5 ``by_tool`` "
        "executor schema returns ok for the static checkers "
        "and rc=1 with a FAILED line for pytest. The "
        "aggregator's tool-contradiction rule rejects the "
        "LLM's `C.fix` claim because the pytest deterministic "
        "negative estimate dominates the green static signals. "
        "Baseline accepts on event evidence alone.\n"
    ))


# ---------------------------------------------------------------------------
# Case 12 — duplicate_tool_request_budget
# ---------------------------------------------------------------------------


def build_duplicate_tool_request_budget() -> None:
    case_dir = PUBLIC_HOLDOUT / "cases" / "duplicate_tool_request_budget"
    _w(case_dir / "packet.json", DEFAULT_PACKET)
    _w(case_dir / "baseline_forward.json", _claim_accepted("C.cap"))
    _w(case_dir / "baseline_backward.json", _backward_met("C.cap"))
    # Forward asks for pytest THREE times. The gateway loop's
    # max_tool_calls budget caps invocations; the audit log
    # carries up to ``max_tool_calls`` rows even though forward
    # asked more times. The advisor confirmed: cap-only
    # behaviour is the right semantics — no dedupe needed.
    _w(case_dir / "gateway_pass1_forward.json", {
        "event_id": "evt-1",
        "supported_claims": [],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [],
        "requested_tools": [
            {
                "tool": "pytest",
                "purpose": "first request",
                "expected_evidence_kind": "test_result",
                "scope": ["tests"],
            },
            {
                "tool": "pytest",
                "purpose": "duplicate request (no new info)",
                "expected_evidence_kind": "test_result",
                "scope": ["tests"],
            },
            {
                "tool": "pytest",
                "purpose": "duplicate request (no new info)",
                "expected_evidence_kind": "test_result",
                "scope": ["tests"],
            },
        ],
    })
    _w(case_dir / "gateway_pass1_backward.json", [])
    # Pass-2 cites the resulting evidence (gateway emits
    # [E.tool.pytest.0] etc.) and accepts the claim.
    _w(case_dir / "gateway_pass2_forward.json", {
        "event_id": "evt-1",
        "supported_claims": [
            {
                "claim_id": "C.cap",
                "event_id": "evt-1",
                "claim_type": "capability_sufficient",
                "statement": "feature X passes pytest scope",
                "confidence": 0.55,
                "evidence_refs": [
                    "[E.event.1]", "[E.tool.pytest.0]",
                ],
                "source": "forward",
            },
        ],
        "rejected_claims": [],
        "missing_evidence_refs": [],
        "contradictions": [],
        "warnings": [],
        "requested_tools": [],
    })
    _w(case_dir / "gateway_pass2_backward.json", _backward_met("C.cap"))
    # Tool policy: low budget so the cap is observable.
    tool_policy = {**DEFAULT_TOOL_POLICY, "max_tool_calls": 2}
    _w(case_dir / "tool_policy.json", tool_policy)
    _w(case_dir / "gateway_definitions.json", {"pytest": PYTEST_DEF})
    _w(case_dir / "approved_tools.json", _approved([PYTEST_DEF]))
    # Executor: pytest passes — every duplicate call returns
    # the same ok outcome. The point of the case is the budget
    # cap, not the test result.
    _w(case_dir / "executor.json", {
        "returncode": 0,
        "stdout": "===== 3 passed in 0.1s =====",
        "stderr": "",
        "timed_out": False,
        "runtime_ms": 9,
    })
    _w(case_dir / "expected.json", {
        "case_id": "duplicate_tool_request_budget",
        "expected_baseline": {
            "accepted_claim_ids": ["C.cap"],
            "unsupported_claim_ids": [],
            "rejected_claim_ids": [],
            "blockers_expected": [],
            "warnings_expected": [],
        },
        "expected_gateway": {
            "accepted_claim_ids": ["C.cap"],
            "unsupported_claim_ids": [],
            "rejected_claim_ids": [],
            "blockers_expected": [],
            "warnings_expected": [],
        },
        "expected_delta": "same",
        "required_tool_evidence_refs": ["[E.tool.pytest.0]"],
        "forbidden_acceptance_reasons": [],
    })
    _w(case_dir / "README.md", (
        "# Case `duplicate_tool_request_budget`\n\n"
        "Family: gateway_grounded. Expected delta: `same`.\n\n"
        "Phase 5.5 §5.5-A. Pass-1 requests pytest three times "
        "with identical scope. The case's tool_policy carries "
        "`max_tool_calls=2` so the gateway loop runs at most "
        "two of them. The audit log demonstrates the cap is "
        "honoured (no autonomous loop) and pass-2 accepts "
        "with a citation to the resulting `[E.tool.pytest.0]`. "
        "Baseline accepts on event evidence alone — both "
        "modes converge, so the discriminator here is the "
        "budget audit, not the verdict.\n"
    ))


def main() -> None:
    build_tool_missing_uncertainty()
    build_tool_timeout_uncertainty()
    build_multi_tool_static_then_test()
    build_duplicate_tool_request_budget()
    print(
        f"wrote 4 Phase 5.5 case directories under "
        f"{PUBLIC_HOLDOUT}/cases/"
    )


if __name__ == "__main__":
    main()
