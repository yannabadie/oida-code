"""Tests for :mod:`oida_code.ingest.claude_code_trace`."""

from __future__ import annotations

import json
from pathlib import Path

from oida_code.ingest.claude_code_trace import parse_claude_code_transcript


def _write_transcript(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _assistant_tool_use(use_id: str, name: str, **input_kwargs: object) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": use_id,
                    "name": name,
                    "input": input_kwargs,
                }
            ]
        },
    }


def _user_tool_result(use_id: str, text: str) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": use_id,
                    "content": [{"type": "text", "text": text}],
                }
            ]
        },
    }


def test_empty_transcript(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    p.write_text("", encoding="utf-8")
    trace = parse_claude_code_transcript(p)
    assert trace.events == []


def test_single_read_event(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    _write_transcript(
        p,
        [
            _assistant_tool_use("u1", "Read", file_path="/src/a.py"),
            _user_tool_result("u1", "file contents\nmore\n"),
        ],
    )
    trace = parse_claude_code_transcript(p)
    assert len(trace.events) == 1
    ev = trace.events[0]
    assert ev.kind == "read"
    assert ev.tool == "Read"
    assert ev.scope == ["/src/a.py"]
    assert ev.new_facts == ["file contents"]


def test_bash_pytest_classified_as_test_run(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    _write_transcript(
        p,
        [
            _assistant_tool_use(
                "u1", "Bash", command="python -m pytest tests/ -q", description="run tests"
            ),
            _user_tool_result("u1", "5 passed"),
        ],
    )
    trace = parse_claude_code_transcript(p)
    assert trace.events[0].kind == "test_run"


def test_bash_git_commit_classified_as_commit(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    _write_transcript(
        p,
        [
            _assistant_tool_use(
                "u1", "Bash", command="git commit -m 'msg'", description="commit"
            ),
            _user_tool_result("u1", "[main abc] msg"),
        ],
    )
    trace = parse_claude_code_transcript(p)
    assert trace.events[0].kind == "commit"


def test_parser_preserves_order(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    _write_transcript(
        p,
        [
            _assistant_tool_use("u1", "Read", file_path="/a.py"),
            _user_tool_result("u1", "a"),
            _assistant_tool_use("u2", "Edit", file_path="/a.py"),
            _user_tool_result("u2", "edit ok"),
            _assistant_tool_use("u3", "Bash", command="pytest"),
            _user_tool_result("u3", "ok"),
        ],
    )
    trace = parse_claude_code_transcript(p)
    assert [e.kind for e in trace.events] == ["read", "edit", "test_run"]
    assert [e.t for e in trace.events] == [0, 1, 2]


def test_parser_tolerates_malformed_lines(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    lines = [
        "not json",
        json.dumps(_assistant_tool_use("u1", "Read", file_path="/a.py")),
        "still not json",
        json.dumps(_user_tool_result("u1", "ok")),
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    trace = parse_claude_code_transcript(p)
    assert len(trace.events) == 1
