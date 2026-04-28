"""Phase 6.0.y (ADR-51) — AI adversarial cold-reader critique.

Standalone, manual-invocation review tool. NOT in CI. NOT in the
`oida-code` runtime path. Reads provider env vars directly via
``os.environ`` — does NOT touch
``src/oida_code/estimators/provider_config.py`` (which stays pinned at
the Phase 4.7+ regression baseline).

Three providers, three independent provider families (DeepSeek + xAI
Grok + Moonshot Kimi) for cognitive diversity. Each agent reads the
``docs/beta/`` pack + supporting docs and produces a structured
markdown critique under ``reports/ai_adversarial/critique_<provider>.md``.

Usage::

    python scripts/run_ai_adversarial_review.py
    python scripts/run_ai_adversarial_review.py --providers deepseek,kimi
    python scripts/run_ai_adversarial_review.py --model deepseek=deepseek-v4-pro

The script does NOT count toward the human-beta aggregate. The
path-isolation guard added in Phase 6.0.x (in
``scripts/run_beta_feedback_eval.py:_iter_feedback_files``) skips the
``ai_adversarial/`` segment, so AI output is structurally separate.

Per ADR-51 + QA/A42 condition 3:
* AI agents NEVER fill the human-beta feedback form.
* AI critiques use ``agent_label`` (free-form prose), NOT
  ``operator_label``.
* Output is markdown, NOT YAML feedback forms.
* No score axes, no usefulness rate, no programmatic aggregation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Pin date 2026-04-28 — verified via cgpro web turn before this script
# landed. Future operators MUST re-verify before re-running. Override
# per-call via --model <provider>=<id>.
_DEFAULT_PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-v4-pro",
    },
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "api_key_env": "GROK_API_KEY",
        "default_model": "grok-4.20-reasoning",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "KIMI_API_KEY",
        "default_model": "kimi-k2.6",
    },
    "minimax": {
        "base_url": "https://api.minimax.io/v1",
        "api_key_env": "MINIMAX_API_KEY",
        "default_model": "MiniMax-Text-01",
    },
}

_DOC_PATHS_TO_REVIEW: tuple[Path, ...] = (
    _REPO_ROOT / "docs" / "beta" / "README.md",
    _REPO_ROOT / "docs" / "beta" / "beta_known_limits.md",
    _REPO_ROOT / "docs" / "beta" / "beta_operator_quickstart.md",
    _REPO_ROOT / "docs" / "beta" / "beta_case_template.md",
    _REPO_ROOT / "docs" / "beta" / "beta_feedback_form.md",
    _REPO_ROOT / "docs" / "concepts" / "oida_code_plain_language.md",
    _REPO_ROOT / "docs" / "project_status.md",
    _REPO_ROOT / "BACKLOG.md",
)

_SYSTEM_PROMPT = """\
You are a Python developer with 5+ years experience, fluent in GitHub \
PRs, pytest, mypy, and ruff. You have just been invited to a closed \
beta of "oida-code" — an experimental tool that produces diagnostic \
reports about AI code claims grounded in tool output. You have NEVER \
seen this project before. You will read the attached beta operator \
pack and produce an adversarial cold-reader critique.

YOUR TASK:
Identify, with line-quoted evidence, places where the docs:
1. Use confusing terms or load-bearing jargon that lacks a clear definition.
2. Contradict each other or have inconsistencies across files.
3. Could be misread as a product verdict (the project explicitly forbids \
"merge-safe", "production-safe", "bug-free", "verified", "security-verified" \
as product-verdict claims — flag if any wording sneaks in despite the policy).
4. Block a cold reader from running their first beta case.
5. Make the bundle authoring requirements feel disproportionate to the value.

HARD RULES (non-negotiable):
- DO NOT fill any operator feedback form. The human-beta lane is for \
actual humans only; you are in a strictly separate adversarial lane.
- DO NOT label any case useful_true_positive / useful_true_negative / \
false_positive / false_negative / unclear / insufficient_fixture — \
those labels are reserved for human operators.
- DO NOT recommend enabling enable-tool-gateway as default-true.
- DO NOT propose emitting total_v_net / debt_final / corrupt_success.
- Quote SPECIFIC LINES from the docs — copy at least the doc filename \
and the relevant phrase. "The documentation could be clearer" is \
useless; "in beta_known_limits.md the phrase 'verification_candidate \
is the strongest positive signal' could be misread as endorsement \
because it sits one paragraph above the pinned `Literal[False]` \
explanation" is useful.

OUTPUT FORMAT (mandatory; reply with exactly this skeleton, in markdown):

# Critique by <PROVIDER>/<MODEL>

## Summary
2-3 sentences. The single most important friction you observed.

## Confusion points (jargon, undefined terms)
- `<docfile.md>`: "<exact quoted phrase>" — why a cold reader would not \
understand this.
- (3-7 items max)

## Contradictions / inconsistencies
- `<docfile.md>` vs `<otherfile.md>`: "<phrase A>" vs "<phrase B>" — \
why these read as conflicting.
- (0-5 items)

## Verdict-leak risk
- `<docfile.md>`: "<exact quoted phrase>" — why this could be misread \
as a product verdict despite the no-product-verdict policy.
- (0-5 items; OK if the answer is "none observed")

## Bundle authoring blockers
- "<specific blocker>" — what would stop a cold reader from preparing \
the 8-file bundle.
- (1-5 items)

## What would stop you from running a beta case
- (1-3 items)

## What would make you actually use this on a real PR
- (1-3 items)

## Honest uncertainty
- (0-3 items where you genuinely don't know if your reading is correct)

End the critique here. No closing pleasantries.
"""

_REVIEW_TIMEOUT_S = 240


@dataclass(frozen=True)
class ProviderCall:
    """One provider call configuration."""

    name: str
    base_url: str
    api_key_env: str
    model: str


def _read_doc_pack() -> str:
    """Read the docs/beta/ pack + supporting docs into a single
    user-prompt blob with file headers so the agent can cite by
    filename.
    """
    chunks: list[str] = []
    for path in _DOC_PATHS_TO_REVIEW:
        rel = path.relative_to(_REPO_ROOT).as_posix()
        chunks.append(f"--- BEGIN FILE: {rel} ---")
        chunks.append(path.read_text(encoding="utf-8"))
        chunks.append(f"--- END FILE: {rel} ---")
        chunks.append("")
    return "\n".join(chunks)


def _post_chat_completions(
    call: ProviderCall, system_prompt: str, user_prompt: str,
) -> str:
    """POST one OpenAI-Chat-Completions-compatible request and return
    the assistant message content as a string. Raises ``RuntimeError``
    on HTTP / parse failure with provider name in the message so the
    caller can record per-provider failures without halting the run.
    """
    api_key = os.environ.get(call.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"{call.name}: env var {call.api_key_env} is not set",
        )
    payload = {
        "model": call.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"{call.base_url}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(
            req, timeout=_REVIEW_TIMEOUT_S,
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover
            err_body = "<no body>"
        raise RuntimeError(
            f"{call.name} HTTP {exc.code}: {err_body[:500]}",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"{call.name} URL error: {exc}") from exc
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"{call.name}: unexpected response shape: {data!r}",
        ) from exc


def _parse_model_overrides(raw: tuple[str, ...]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            raise ValueError(
                f"--model entry {entry!r} must be 'provider=model_id'",
            )
        provider, model_id = entry.split("=", 1)
        provider = provider.strip()
        model_id = model_id.strip()
        if not provider or not model_id:
            raise ValueError(
                f"--model entry {entry!r} must have non-empty provider and id",
            )
        overrides[provider] = model_id
    return overrides


def _build_calls(
    providers: tuple[str, ...], overrides: dict[str, str],
) -> list[ProviderCall]:
    calls: list[ProviderCall] = []
    for provider in providers:
        if provider not in _DEFAULT_PROVIDERS:
            raise ValueError(
                f"unknown provider {provider!r}; known: "
                f"{sorted(_DEFAULT_PROVIDERS.keys())}",
            )
        cfg = _DEFAULT_PROVIDERS[provider]
        calls.append(
            ProviderCall(
                name=provider,
                base_url=cfg["base_url"],
                api_key_env=cfg["api_key_env"],
                model=overrides.get(provider, cfg["default_model"]),
            ),
        )
    return calls


def _write_critique(
    out_dir: Path, call: ProviderCall, content: str,
) -> Path:
    out_path = out_dir / f"critique_{call.name}.md"
    header = (
        f"<!-- ai_adversarial lane (ADR-51). Provider: {call.name} / "
        f"model: {call.model}. Pin date: 2026-04-28. NOT operator "
        f"feedback. NEVER ingested by the human-beta aggregator. -->\n\n"
    )
    out_path.write_text(header + content + "\n", encoding="utf-8")
    return out_path


def _write_failure_record(
    out_dir: Path, call: ProviderCall, error: str,
) -> Path:
    out_path = out_dir / f"critique_{call.name}.md"
    out_path.write_text(
        f"<!-- ai_adversarial lane (ADR-51). Provider: {call.name} / "
        f"model: {call.model}. Pin date: 2026-04-28. -->\n\n"
        f"# Critique by {call.name}/{call.model} — FAILED\n\n"
        f"This provider call did not produce a critique. Recorded "
        f"failure for transparency.\n\n"
        f"```\n{error}\n```\n\n"
        f"Possible causes: stale model id (re-verify before "
        f"re-running), missing env var, network egress blocked, "
        f"provider rate limit, malformed prompt.\n",
        encoding="utf-8",
    )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run AI adversarial cold-reader critique of the docs/beta/ "
            "pack across 3 providers. Manual-invocation only; NOT in "
            "CI; NOT in the runtime path of oida-code. Output goes to "
            "reports/ai_adversarial/, which is path-isolated from the "
            "human-beta aggregate."
        ),
    )
    parser.add_argument(
        "--providers",
        type=str,
        default="deepseek,grok,kimi",
        help=(
            "Comma-separated list of providers to run. Known: "
            f"{','.join(sorted(_DEFAULT_PROVIDERS.keys()))}"
        ),
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help=(
            "Per-provider model override. Repeatable. "
            "E.g. --model deepseek=deepseek-v4-pro"
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_REPO_ROOT / "reports" / "ai_adversarial",
        help="Output directory for critique markdown files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Print the resolved provider calls + prompt sizes without "
            "actually contacting any provider."
        ),
    )
    args = parser.parse_args()

    providers = tuple(
        p.strip() for p in args.providers.split(",") if p.strip()
    )
    overrides = _parse_model_overrides(tuple(args.model))
    calls = _build_calls(providers, overrides)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    user_prompt = _read_doc_pack()

    print(f"docs pack size: {len(user_prompt)} chars")
    for call in calls:
        print(f"  {call.name}: {call.model} (env: {call.api_key_env})")

    if args.dry_run:
        print("--dry-run; not contacting any provider")
        return 0

    failures: list[str] = []
    for call in calls:
        print(f"calling {call.name}/{call.model} ...", flush=True)
        try:
            content = _post_chat_completions(
                call, _SYSTEM_PROMPT, user_prompt,
            )
            out_path = _write_critique(args.out_dir, call, content)
            print(f"  wrote {out_path.relative_to(_REPO_ROOT)}")
        except RuntimeError as exc:
            err_str = str(exc)
            print(f"  FAILED: {err_str}", file=sys.stderr)
            _write_failure_record(args.out_dir, call, err_str)
            failures.append(f"{call.name}: {err_str}")

    if failures:
        print("", file=sys.stderr)
        print(f"{len(failures)} of {len(calls)} providers failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
