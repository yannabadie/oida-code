"""Phase 4.3-E (QA/A19.md, ADR-28) — stability check for code_outcome.

Runs each ``code_outcome`` case's pytest suite ``stability_runs``
times and records F2P / P2P pass-rates. Cases where any of the runs
disagree on F2P or P2P are marked **flaky** and excluded from the
calibration metrics by ``run_calibration_eval.py``.

**Real subprocess.** The script invokes ``pytest`` with
``shell=False`` against each case's ``repo/`` directory. Missing
pytest binary becomes an explicit ``status="tool_missing"`` per-case
and the case is recorded as flaky with that reason.

Usage::

    python scripts/check_calibration_stability.py
    python scripts/check_calibration_stability.py --dataset datasets/calibration_v1
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from oida_code.calibration.runner import load_case


@dataclass
class StabilityRun:
    f2p_passed: tuple[bool, ...]
    p2p_passed: tuple[bool, ...]
    runtime_ms: int
    returncode: int
    timed_out: bool


@dataclass
class StabilityCaseReport:
    case_id: str
    family: str
    runs: list[StabilityRun] = field(default_factory=list)
    flaky: bool = False
    flaky_reason: str | None = None


def _run_pytest_once(
    repo: Path, f2p_tests: tuple[str, ...], p2p_tests: tuple[str, ...],
    *, timeout_s: int = 60,
) -> StabilityRun:
    binary = shutil.which("pytest")
    if binary is None:
        return StabilityRun(
            f2p_passed=tuple(False for _ in f2p_tests),
            p2p_passed=tuple(False for _ in p2p_tests),
            runtime_ms=0, returncode=-1, timed_out=False,
        )
    targets = [*f2p_tests, *p2p_tests]
    argv = [binary, "-q", "--no-header", "-p", "no:cacheprovider"]
    argv.extend(t for t in targets)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(repo),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout_s,
            check=False, shell=False,
        )
    except subprocess.TimeoutExpired:
        return StabilityRun(
            f2p_passed=tuple(False for _ in f2p_tests),
            p2p_passed=tuple(False for _ in p2p_tests),
            runtime_ms=int((time.monotonic() - start) * 1000),
            returncode=-1, timed_out=True,
        )
    runtime_ms = int((time.monotonic() - start) * 1000)
    failed = set()
    for raw in proc.stdout.splitlines():
        if raw.startswith("FAILED "):
            failed.add(raw.split(" ", 2)[1])
    f2p_passed = tuple(t not in failed for t in f2p_tests)
    p2p_passed = tuple(t not in failed for t in p2p_tests)
    return StabilityRun(
        f2p_passed=f2p_passed, p2p_passed=p2p_passed,
        runtime_ms=runtime_ms, returncode=proc.returncode, timed_out=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", default="datasets/calibration_v1",
    )
    parser.add_argument(
        "--out", default=".oida/calibration_v1",
    )
    args = parser.parse_args()

    dataset = Path(args.dataset)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = dataset / "cases"

    reports: list[StabilityCaseReport] = []
    for case_dir in sorted(p for p in cases_dir.iterdir() if p.is_dir()):
        case = load_case(case_dir)
        if case.family != "code_outcome" or case.expected_code_outcome is None:
            continue
        report = StabilityCaseReport(case_id=case.case_id, family=case.family)
        repo = case_dir / (case.repo_fixture or "repo")
        if not repo.is_dir():
            report.flaky = True
            report.flaky_reason = "repo dir missing"
            reports.append(report)
            continue
        for _ in range(case.expected_code_outcome.stability_runs):
            run = _run_pytest_once(
                repo,
                case.expected_code_outcome.f2p_tests,
                case.expected_code_outcome.p2p_tests,
            )
            report.runs.append(run)
        # Flaky if any two runs disagree on F2P / P2P or pytest missing.
        if any(run.returncode == -1 and not run.timed_out for run in report.runs):
            report.flaky = True
            report.flaky_reason = "pytest binary not on PATH"
        else:
            f2p_signatures = {run.f2p_passed for run in report.runs}
            p2p_signatures = {run.p2p_passed for run in report.runs}
            if len(f2p_signatures) > 1 or len(p2p_signatures) > 1:
                report.flaky = True
                report.flaky_reason = "F2P / P2P disagreement across runs"
        reports.append(report)

    payload = [
        {
            **{k: v for k, v in asdict(r).items() if k != "runs"},
            "runs": [asdict(run) for run in r.runs],
        }
        for r in reports
    ]
    (out_dir / "stability_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )
    flaky_count = sum(1 for r in reports if r.flaky)
    print(
        f"wrote stability report for {len(reports)} code_outcome case(s); "
        f"flaky={flaky_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
