from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .models import Scenario


def load_json(path: str | Path) -> Dict[str, Any]:
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Scenario file not found: {file_path}") from exc
    return json.loads(text)


def load_scenario(path: str | Path) -> Scenario:
    data = load_json(path)
    return Scenario.from_dict(data)


def save_report(report: Dict[str, Any], path: str | Path) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
