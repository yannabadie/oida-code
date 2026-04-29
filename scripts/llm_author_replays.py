"""Phase 6.1'd (ADR-57) — manual-lane LLM-replay authoring helper.

Reads a calibration_seed inclusion record + the corresponding
generated bundle directory, calls a provider (DeepSeek by
default) to author the four ``pass*_*.json`` replays, validates
each against the verifier's Pydantic contracts, and overwrites
the skeleton stubs with the LLM output.

NOT in CI. NOT in the runtime path of ``oida-code``. Per
ADR-53 §"Frontière manual-vs-runtime" this is a manual-egress
script:

* Carries the ``MANUAL_EGRESS_SCRIPT = True`` module-level
  marker (disambiguator with runtime modules under
  ``src/oida_code/``).
* Refuses to run without ``--manual-egress-ok``.
* Reads its provider key from a single env var
  (``DEEPSEEK_API_KEY`` by default) — never from a config
  file checked into the repo.

The script does NOT auto-confirm the replays — per ADR-53
§"What provider API keys may / may not do", LLM output is
operator-suggested, never operator-decided. The script writes
the LLM output AND prints a one-line "operator must inspect"
banner; the operator's manual review is the actual decision
step.

Usage::

    export DEEPSEEK_API_KEY=...
    python scripts/llm_author_replays.py \\
        --case-id seed_008_pytest_dev_pytest_14407 \\
        --bundle-dir .tmp/probe_bundle/seed_008_pytest_dev_pytest_14407 \\
        --manual-egress-ok
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _ssl_context() -> ssl.SSLContext:
    """Build an SSL context tolerant of certs missing the
    Authority Key Identifier extension. Python 3.13 enabled
    ``VERIFY_X509_STRICT`` by default, which rejects some
    valid CAs in DeepSeek's chain. We relax that single flag
    while keeping hostname verification + cert-chain
    validation otherwise enabled."""
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx

# Module-level marker — see ADR-53. The structural test
# tests/test_phase6_1_manual_data_lane_isolation.py enforces
# that no src/oida_code/ module sets this.
MANUAL_EGRESS_SCRIPT = True

_REPO_ROOT = Path(__file__).resolve().parent.parent

_PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {
        "endpoint": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
        "env_var": "DEEPSEEK_API_KEY",
    },
}

_SYSTEM_PROMPT = """You are an OIDA-code verifier-pass author.

Given a calibration_seed inclusion record and a bundle's
packet.json, your job is to author four JSON files that match
the verifier's wire shapes EXACTLY (ForwardVerificationResult
for pass*_forward.json; a JSON LIST of BackwardVerificationResult
for pass*_backward.json).

Hard rules — rejection if violated:

1. Output ONLY a single JSON object with four keys:
   "pass1_forward", "pass1_backward", "pass2_forward",
   "pass2_backward". Each value must be valid against its
   target Pydantic shape (extra="forbid" — no extra keys).
2. Backward replays are JSON LISTS, not single objects:
   * pass1_backward is `[]` (empty).
   * pass2_backward is `[{...one entry per claim...}]`.
3. Forward replays are objects with the keys:
   event_id (required, min_length=1),
   supported_claims (list of VerifierClaim), rejected_claims,
   missing_evidence_refs, contradictions, warnings,
   requested_tools.
4. The pass1_forward MUST request pytest on the seed's
   test_scope (one entry in requested_tools with tool=pytest,
   purpose ≤ 200 chars, expected_evidence_kind="test_result",
   scope=[<test_scope>]).
5. The pass2_forward should accept the claim if the gateway
   tool result is expected to ground it. Each entry in
   supported_claims is a VerifierClaim with EXACTLY these
   fields (extra="forbid" rejects extras; missing fields
   reject too):
     * claim_id (str, min_length=1)
     * event_id (str, min_length=1) — copy from packet.event_id
     * claim_type (one of: capability_sufficient | benefit_aligned
       | observability_sufficient | precondition_supported |
       negative_path_covered | repair_needed |
       shadow_pressure_explained)
     * statement (str, max 400 chars)
     * confidence (float in [0.0, 1.0]). For VerifierClaim
       entries with source="forward" or source="backward",
       the verifier aggregator caps usable confidence at 0.6.
       Set confidence ≤ 0.6 unless source is "tool" or
       "aggregator". For "forward" claims, 0.55 is a safe
       default.
     * evidence_refs (list of str — cite [E.event.*] AND
       [E.tool.pytest.0])
     * source (one of: forward | backward | aggregator | tool
       | replay) — for pass2_forward use "forward".
   DO NOT include is_authoritative — it is auto-pinned to
   false; including the field is a Pydantic violation if
   set true and noise if set false.
6. The pass2_backward entry is a BackwardVerificationResult
   with EXACTLY these fields:
     * event_id (str, min_length=1)
     * claim_id (str, min_length=1)
     * requirement (BackwardRequirement object with: claim_id,
       required_evidence_kinds list of allowed kinds, optional
       satisfied_evidence_refs list of str, optional
       missing_requirements list of str)
     * necessary_conditions_met (bool — set true if operator
       expects the bundle to ground the claim, false otherwise)
     * warnings (list of str, optional)
   `required_evidence_kinds` MUST include "test_result" since
   pytest is the gateway tool. Each kind value must be one of:
   intent | event | precondition | tool_finding | test_result
   | graph_edge | trajectory | repair_signal.
7. NEVER use the phrases V_net, total_v_net, debt_final,
   corrupt_success, verdict, merge-safe, production-safe,
   bug-free, security-verified, or any inflection thereof.
   ADR-22/24/25/26 hard wall — these are forbidden.
8. NEVER claim is_authoritative=true. The default Literal[False]
   pin will reject it, but don't write the field at all.

Return ONLY the JSON. No prose. No code fence. No commentary.
"""


def _read_seed_record(case_id: str) -> dict[str, Any]:
    path = _REPO_ROOT / "reports" / "calibration_seed" / "index.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        r for r in records
        if isinstance(r, dict) and r.get("case_id") == case_id
    ]
    if not matches:
        raise SystemExit(
            f"case_id {case_id!r} not found in {path}",
        )
    if len(matches) > 1:
        raise SystemExit(
            f"case_id {case_id!r} matched {len(matches)} records",
        )
    return matches[0]


def _read_bundle_packet(bundle_dir: Path) -> dict[str, Any]:
    return json.loads(
        (bundle_dir / "packet.json").read_text(encoding="utf-8"),
    )


def _build_user_prompt(
    seed_record: dict[str, Any], packet: dict[str, Any],
) -> str:
    claim_summary = (
        f"claim_id: {seed_record['claim_id']}\n"
        f"claim_type: {seed_record['claim_type']}\n"
        f"event_id: {packet['event_id']}\n"
        f"test_scope: {seed_record['test_scope']}\n"
        f"expected_grounding_outcome: {seed_record['expected_grounding_outcome']}"
    )
    evidence = json.dumps(seed_record["evidence_items"], indent=2)
    return (
        f"=== seed record summary ===\n{claim_summary}\n\n"
        f"=== seed evidence_items ===\n{evidence}\n\n"
        f"=== bundle packet.json ===\n{json.dumps(packet, indent=2)}\n\n"
        "Author the four replay JSONs. Output ONLY one JSON "
        "object with keys pass1_forward / pass1_backward / "
        "pass2_forward / pass2_backward."
    )


def _call_deepseek(
    system_prompt: str, user_prompt: str, *, timeout_s: int = 120,
) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit(
            "DEEPSEEK_API_KEY not set; refusing.",
        )
    payload = {
        "model": _PROVIDERS["deepseek"]["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        _PROVIDERS["deepseek"]["endpoint"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "oida-code-llm-author-replays",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            req, timeout=timeout_s, context=_ssl_context(),
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(
            f"DeepSeek HTTP {exc.code}: {body[:400]}",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"DeepSeek transport error: {exc}") from exc
    return data["choices"][0]["message"]["content"]


def _validate_replays(
    payload: dict[str, Any],
) -> None:
    """Validate the LLM output against the verifier Pydantic
    contracts before writing it to disk."""
    from oida_code.verifier.contracts import (
        BackwardVerificationResult,
        ForwardVerificationResult,
    )

    expected_keys = {
        "pass1_forward", "pass1_backward",
        "pass2_forward", "pass2_backward",
    }
    if set(payload) != expected_keys:
        raise SystemExit(
            f"LLM payload keys mismatch. Expected "
            f"{sorted(expected_keys)}, got "
            f"{sorted(payload)}",
        )
    ForwardVerificationResult.model_validate(payload["pass1_forward"])
    ForwardVerificationResult.model_validate(payload["pass2_forward"])
    bwd1 = payload["pass1_backward"]
    bwd2 = payload["pass2_backward"]
    if not isinstance(bwd1, list):
        raise SystemExit(
            "pass1_backward must be a JSON list (got "
            f"{type(bwd1).__name__})",
        )
    if not isinstance(bwd2, list):
        raise SystemExit(
            "pass2_backward must be a JSON list (got "
            f"{type(bwd2).__name__})",
        )
    for entry in bwd1:
        BackwardVerificationResult.model_validate(entry)
    for entry in bwd2:
        BackwardVerificationResult.model_validate(entry)


def _write_replays(
    bundle_dir: Path, payload: dict[str, Any],
) -> list[Path]:
    written: list[Path] = []
    for key in (
        "pass1_forward", "pass1_backward",
        "pass2_forward", "pass2_backward",
    ):
        path = bundle_dir / f"{key}.json"
        path.write_text(
            json.dumps(payload[key], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def _archive_skeleton(bundle_dir: Path) -> Path:
    """Save the four pre-LLM skeleton stubs into a sibling
    directory so the operator can compare. Idempotent:
    re-running overwrites the archive."""
    archive = bundle_dir.parent / (bundle_dir.name + "_skeleton")
    archive.mkdir(exist_ok=True)
    for key in (
        "pass1_forward", "pass1_backward",
        "pass2_forward", "pass2_backward",
    ):
        src = bundle_dir / f"{key}.json"
        if src.is_file():
            (archive / f"{key}.json").write_bytes(src.read_bytes())
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 6.1'd manual LLM-replay authoring. Reads a "
            "calibration_seed record + bundle, calls a provider "
            "to author the four pass*_*.json replays, validates "
            "Pydantic, and overwrites the skeleton stubs."
        ),
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--bundle-dir", type=Path, required=True,
    )
    parser.add_argument(
        "--provider", default="deepseek",
        choices=tuple(_PROVIDERS),
    )
    parser.add_argument(
        "--manual-egress-ok", action="store_true", default=False,
    )
    parser.add_argument(
        "--archive-skeleton", action="store_true", default=True,
    )
    args = parser.parse_args()

    if not args.manual_egress_ok:
        print(
            "refusing: --manual-egress-ok required to call a "
            "provider (per ADR-53 frontière rule 4).",
            file=sys.stderr,
        )
        return 2

    if not args.bundle_dir.is_dir():
        print(
            f"bundle dir not found: {args.bundle_dir}",
            file=sys.stderr,
        )
        return 2

    seed_record = _read_seed_record(args.case_id)
    packet = _read_bundle_packet(args.bundle_dir)

    user_prompt = _build_user_prompt(seed_record, packet)

    if args.archive_skeleton:
        archive = _archive_skeleton(args.bundle_dir)
        print(f"archived skeleton stubs under {archive}")

    provider = args.provider
    print(
        f"calling provider={provider} model="
        f"{_PROVIDERS[provider]['model']} ...",
    )
    started = dt.datetime.now(dt.UTC)
    raw = _call_deepseek(_SYSTEM_PROMPT, user_prompt)
    elapsed = (dt.datetime.now(dt.UTC) - started).total_seconds()
    print(f"provider call returned in {elapsed:.1f}s")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            f"LLM output was not valid JSON: {exc}",
            file=sys.stderr,
        )
        print(f"raw output (first 600 chars):\n{raw[:600]}")
        return 2

    try:
        _validate_replays(payload)
    except SystemExit as exc:
        print(
            f"LLM output failed Pydantic validation: {exc}",
            file=sys.stderr,
        )
        return 2

    written = _write_replays(args.bundle_dir, payload)
    print(f"wrote {len(written)} replay files to {args.bundle_dir}")
    for p in written:
        print(f"  {p.name}")
    print()
    print(
        "operator must inspect the LLM output before relying on it. "
        "Per ADR-53, LLM output is operator-suggested, never "
        "operator-decided.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
