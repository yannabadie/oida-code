"""Phase 4.5 (QA/A21.md, ADR-30) — workflow / action security validator.

Static checks the operator can run before pushing; the CI invokes it
in the ``security-smoke`` job. ADR-30 hard rules:

* ``permissions:`` MUST be present at workflow level.
* ``permissions:`` default MUST be ``contents: read`` (no escalation
  by default).
* No workflow may use ``pull_request_target`` (would let untrusted
  PRs read repo secrets — see GitHub's own pwn-vulnerability
  advisory).
* No job may set a non-``read`` permission unless it's the dedicated
  SARIF upload job (``security-events: write`` is allowed there).
* No raw API key value appears anywhere in the workflow body.
* The composite action's ``llm-provider`` default MUST be ``replay``.
* The composite action MUST refuse external providers on fork PRs.
* No ``secrets.<NAME>`` is referenced outside an ``env:`` map.

Exits non-zero (1) if any check fails; 0 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover — yaml ships with most envs
    yaml = None


_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"
_ACTION_FILE = _REPO_ROOT / "action.yml"

_FORBIDDEN_TRIGGERS = ("pull_request_target",)
_ALLOWED_NON_READ_JOB_PERMS = {"security-events"}

_API_KEY_PATTERN = re.compile(
    r"\b(sk-[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,}|"
    r"xoxb-[A-Za-z0-9\-]+)",
)

# PR-controlled context expressions that must NEVER be interpolated
# straight into a `run:` block. GitHub's own security advisory
# documents this as a shell-injection escalation surface; the
# canonical mitigation is the intermediate-env-var pattern.
_PR_CONTROLLED_EXPR = re.compile(
    r"\$\{\{\s*("
    r"inputs\.[A-Za-z0-9_\-]+"
    r"|github\.head_ref"
    r"|github\.event\.(?:pull_request|issue|comment|review|"
    r"discussion|workflow_run|push|head_commit)\."
    r"[A-Za-z0-9_.\-]*"
    r"|github\.actor"
    r"|github\.triggering_actor"
    r"|github\.event\.head_commit\.message"
    r")\s*\}\}",
)


def _iter_run_blocks(payload: dict[str, object]) -> list[tuple[str, str]]:
    """Yield ``(location, run_block_body)`` for every ``run:`` field.

    Handles both workflow shape (``jobs.<name>.steps[*].run``) and
    composite-action shape (``runs.steps[*].run``).
    """
    out: list[tuple[str, str]] = []

    def _walk_steps(prefix: str, steps: object) -> None:
        if not isinstance(steps, list):
            return
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if isinstance(run, str):
                name = step.get("name") if isinstance(
                    step.get("name"), str,
                ) else f"step[{idx}]"
                out.append((f"{prefix}.{name}", run))

    runs = payload.get("runs")
    if isinstance(runs, dict):
        _walk_steps("runs", runs.get("steps"))

    jobs = payload.get("jobs")
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            _walk_steps(f"jobs.{job_name}", job.get("steps"))
    return out


def _load_yaml(path: Path) -> dict[str, object]:
    if yaml is None:
        raise RuntimeError("PyYAML required to parse workflow YAML")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"workflow {path} did not parse to a mapping")
    return payload


def _check_workflow(path: Path) -> list[str]:
    errors: list[str] = []
    body = path.read_text(encoding="utf-8")

    # 1. No raw API key value anywhere in the file.
    if _API_KEY_PATTERN.search(body):
        errors.append(f"{path}: matches a known API-key prefix pattern")

    # 2. No `pull_request_target`.
    for trigger in _FORBIDDEN_TRIGGERS:
        if re.search(rf"^\s*{trigger}\s*:", body, re.MULTILINE):
            errors.append(f"{path}: forbidden trigger {trigger!r}")

    payload = _load_yaml(path)

    # 3. Workflow-level `permissions:` present and read-only by
    # default (or absent — but explicit is better).
    perms = payload.get("permissions")
    if perms is None:
        errors.append(
            f"{path}: missing top-level `permissions:` (ADR-30 §A); "
            "set `permissions: { contents: read }` at minimum"
        )
    elif isinstance(perms, dict):
        for scope, value in perms.items():
            if scope == "contents" and value != "read":
                errors.append(
                    f"{path}: workflow-level permissions.contents must be "
                    f"`read`, got {value!r}"
                )
            if scope not in _ALLOWED_NON_READ_JOB_PERMS and value not in (
                "read", "none",
            ):
                errors.append(
                    f"{path}: workflow-level permissions.{scope} must be "
                    f"`read` or `none`, got {value!r}"
                )

    # 4. Per-job permissions: writes restricted to the SARIF case.
    jobs = payload.get("jobs", {})
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            job_perms = job.get("permissions")
            if not isinstance(job_perms, dict):
                continue
            for scope, value in job_perms.items():
                if value in ("read", "none"):
                    continue
                if scope == "security-events" and value == "write":
                    # Allowed — SARIF upload.
                    continue
                errors.append(
                    f"{path}: job {job_name!r} grants "
                    f"permissions.{scope}={value}; only "
                    "security-events: write is allowed (ADR-30)"
                )

    # 5. No `secrets.X` in run blocks (the secret should live in an
    # `env:` map, not inline). Inline `${{ secrets.* }}` in `run:`
    # ends up echoed by `set -x` traces and tools like add-mask only
    # mask values that have been explicitly registered.
    for line in body.splitlines():
        stripped = line.strip()
        if (
            (stripped.startswith("run:") or stripped.startswith("- run:"))
            and "${{ secrets." in stripped
        ):
            errors.append(
                f"{path}: `${{{{ secrets.* }}}}` referenced inside a "
                "run block; pass it through env: instead"
            )

    # 6. No PR-controlled expression inside a `run:` block. A
    # `${{ inputs.X }}` / `${{ github.head_ref }}` / etc. expanded
    # into bash gets the substitution at YAML-eval time; a value
    # like `a"; whoami; #` breaks out of quoting and runs arbitrary
    # commands on the runner. Mitigation: lift the expression into
    # an `env:` map and reference it as `$VAR` in bash.
    for location, run_body in _iter_run_blocks(payload):
        m = _PR_CONTROLLED_EXPR.search(run_body)
        if m:
            errors.append(
                f"{path}: PR-controlled expression `{m.group(0)}` "
                f"interpolated inside a run block at {location}; "
                "lift it into the step's env: map and use $VAR"
            )
    return errors


def _check_action(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"{path}: missing"]
    body = path.read_text(encoding="utf-8")

    if _API_KEY_PATTERN.search(body):
        errors.append(f"{path}: matches a known API-key prefix pattern")

    payload = _load_yaml(path)

    # The action MUST be a composite action.
    runs = payload.get("runs")
    if not isinstance(runs, dict) or runs.get("using") != "composite":
        errors.append(
            f"{path}: action must declare `runs.using: composite` (ADR-30)"
        )

    # PR-controlled-expression-in-run check applies to action steps
    # too — a malicious caller could pass a poisoned `inputs.intent-
    # file` value that breaks bash quoting on the runner.
    for location, run_body in _iter_run_blocks(payload):
        m = _PR_CONTROLLED_EXPR.search(run_body)
        if m:
            errors.append(
                f"{path}: PR-controlled expression `{m.group(0)}` "
                f"interpolated inside a run block at {location}; "
                "lift it into the step's env: map and use $VAR"
            )

    inputs = payload.get("inputs")
    if not isinstance(inputs, dict):
        errors.append(f"{path}: action must declare `inputs:`")
        return errors

    # llm-provider default MUST be replay.
    llm_provider = inputs.get("llm-provider")
    if not isinstance(llm_provider, dict):
        errors.append(f"{path}: missing input `llm-provider`")
    elif llm_provider.get("default") != "replay":
        errors.append(
            f"{path}: input `llm-provider` must default to `replay`, "
            f"got {llm_provider.get('default')!r}"
        )

    # The action MUST guard fork PRs against external providers.
    if (
        "pull_request" in body
        and "head.repo.full_name" not in body
    ):
        errors.append(
            f"{path}: action must explicitly block external providers on "
            "fork PRs (look for github.event.pull_request.head.repo.full_name"
            " != github.repository)"
        )

    # Required input names per QA/A21.md §4.5-B.
    required_inputs = {
        "repo-path", "base-ref", "intent-file", "output-dir",
        "upload-sarif", "fail-on", "surface", "enable-shadow",
        "llm-provider",
    }
    missing = required_inputs - set(inputs.keys())
    if missing:
        errors.append(
            f"{path}: missing required inputs {sorted(missing)}"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows-dir", default=str(_WORKFLOW_DIR),
        help="Directory containing GitHub Actions workflows.",
    )
    parser.add_argument(
        "--action-file", default=str(_ACTION_FILE),
        help="Path to the composite action's action.yml.",
    )
    args = parser.parse_args()
    workflows_dir = Path(args.workflows_dir)
    action_file = Path(args.action_file)

    if yaml is None:
        print("ERROR: PyYAML is required (pip install pyyaml).", file=sys.stderr)
        return 2

    errors: list[str] = []
    if workflows_dir.is_dir():
        for path in sorted(workflows_dir.glob("*.yml")):
            errors.extend(_check_workflow(path))
        for path in sorted(workflows_dir.glob("*.yaml")):
            errors.extend(_check_workflow(path))
    else:
        print(f"WARN: no workflows directory at {workflows_dir}")
    errors.extend(_check_action(action_file))

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("OK: workflow + action invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
