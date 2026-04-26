"""Phase 5.3 (QA/A30.md, ADR-38) — gateway calibration runner.

Pairs each holdout case's expected verdicts (baseline vs.
gateway) with two actual runs of the verifier and emits
per-mode metrics + a failure analysis. Replay-only by default;
no MCP runtime, no remote-procedure-call runtime, no
provider-side tool calling, no network egress.

Usage::

    python scripts/run_gateway_calibration.py \\
        --manifest datasets/private_holdout_v2/manifest.example.json \\
        --mode replay \\
        --out .oida/gateway-calibration

The runner is read-only over ``datasets/`` — there is no path
through this script that mutates an operator-supplied label
(QA/A30 §5.3-E line 269).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from oida_code.calibration.gateway_calibration import run_calibration


def _parse_argv(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 5.3 gateway-grounded verifier calibration "
            "runner (replay-only by default)."
        ),
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help=(
            "Path to a Phase 5.3 calibration manifest (e.g. "
            "datasets/private_holdout_v2/manifest.example.json)."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["replay"],
        default="replay",
        help=(
            "Execution mode. Phase 5.3 supports 'replay' only — "
            "external providers stay opt-in via Phase 4.4.1 "
            "binders and never reach this script."
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help=(
            "Output directory for the four artifacts: "
            "baseline_metrics.json, gateway_metrics.json, "
            "delta_metrics.json, failure_analysis.md, "
            "artifact_manifest.json."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_argv(argv)
    if not args.manifest.is_file():
        print(
            f"manifest not found: {args.manifest}",
            file=sys.stderr,
        )
        return 2
    run_calibration(
        manifest_path=args.manifest,
        out_dir=args.out,
        mode=args.mode,
    )
    print(
        f"calibration={args.out} mode={args.mode} "
        f"manifest={args.manifest}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
