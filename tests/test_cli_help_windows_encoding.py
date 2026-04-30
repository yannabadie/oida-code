"""Windows help-text encoding guard.

The local Windows console uses a cp1252 code page in this environment.
Typer/Rich help text that contains characters outside cp1252 can crash
before users see the first CLI command.
"""

from __future__ import annotations

import os
import subprocess
import sys

from tests.conftest import REPO_ROOT


def test_cli_help_text_is_cp1252_encodable() -> None:
    cli_source = (REPO_ROOT / "src" / "oida_code" / "cli.py").read_text(
        encoding="utf-8",
    )
    offenders = sorted(
        {
            f"U+{ord(char):04X}"
            for char in cli_source
            if ord(char) > 127 and not char.encode("cp1252", errors="ignore")
        }
    )
    assert offenders == []


def test_python_module_help_runs_with_cp1252_stdout() -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252:strict"
    env["COLUMNS"] = "200"
    completed = subprocess.run(
        [sys.executable, "-m", "oida_code.cli", "--help"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode(
        "cp1252",
        errors="replace",
    )
    assert b"inspect" in completed.stdout
    assert b"audit" in completed.stdout
