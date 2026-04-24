"""Parse Claude Code JSONL transcripts into :class:`~oida_code.models.trace.Trace`.

Transcript location: ``~/.claude/projects/<project-slug>/<session-id>.jsonl``.
Each line is one JSON record; relevant record types:

* ``{"type": "assistant", "message": {"content": [{"type": "tool_use",
  "id": "...", "name": "Read|Grep|Edit|Write|Bash|...", "input": {...}}, ...]}}``
* ``{"type": "user", "message": {"content": [{"type": "tool_result",
  "tool_use_id": "...", "content": "..."}]}}``

Mapping to :class:`~oida_code.models.trace.TraceEvent.kind`:

===================  =================================
Claude Code tool     TraceEventKind
===================  =================================
``Read``             ``read``
``Grep``             ``grep``
``Glob``             ``grep`` (path-search family)
``Edit``             ``edit``
``Write``            ``write``
``NotebookEdit``     ``edit``
``Bash`` (``git``)   ``commit`` if argv starts with ``git commit``
``Bash`` (``pytest``) ``test_run`` if ``pytest`` in argv
``Bash`` (other)     ``tool_call``
``TaskCreate/*``     ``other``
other                ``tool_call``
===================  =================================

Progress signal: :attr:`TraceEvent.new_facts` is populated with a
single-line summary when the tool result has non-empty content. The
transcript carries no ``obligation_id`` linkage, so
:attr:`TraceEvent.closed_obligations` is always empty after ingest —
Phase-3's trajectory scorer derives progress from ``new_facts`` presence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oida_code.models.trace import Trace, TraceEvent, TraceEventKind

_TOOL_KIND: dict[str, TraceEventKind] = {
    "Read": "read",
    "Grep": "grep",
    "Glob": "grep",
    "Edit": "edit",
    "Write": "write",
    "NotebookEdit": "edit",
    "TaskCreate": "other",
    "TaskUpdate": "other",
    "TaskList": "other",
    "TaskGet": "other",
    "TaskOutput": "other",
    "TaskStop": "other",
    "Skill": "tool_call",
    "ToolSearch": "tool_call",
    "Monitor": "tool_call",
    "WebFetch": "read",
    "WebSearch": "grep",
}


def _classify_bash(argv: str) -> TraceEventKind:
    cmd = argv.strip().lower()
    if cmd.startswith("git commit") or " git commit " in cmd:
        return "commit"
    if "pytest" in cmd or "python -m pytest" in cmd:
        return "test_run"
    return "tool_call"


def _extract_scope(tool_name: str, tool_input: dict[str, Any]) -> list[str]:
    """Pull file-path-like strings out of the tool input for scope."""
    if tool_name in {"Read", "Edit", "Write", "NotebookEdit"}:
        p = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("notebook_path")
        return [str(p)] if p else []
    if tool_name in {"Grep", "Glob"}:
        p = tool_input.get("path") or tool_input.get("pattern") or ""
        return [str(p)] if p else []
    if tool_name == "Bash":
        # Do not parse bash argv for paths — too unreliable to guess.
        return []
    return []


def _summarize_result(result: Any) -> str | None:
    """Return a one-line summary of a tool_result payload."""
    if result is None:
        return None
    if isinstance(result, list):
        # Claude Code result content is a list of {type, text} blocks.
        pieces: list[str] = []
        for item in result:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    pieces.append(str(text))
            else:
                pieces.append(str(item))
        text = "\n".join(pieces)
    else:
        text = str(result)
    text = text.strip()
    if not text:
        return None
    first = text.splitlines()[0].strip()
    return first[:160] or None


def parse_claude_code_transcript(path: Path | str) -> Trace:
    """Parse one Claude Code JSONL transcript into a :class:`Trace`.

    ``t`` is a dense 0-based index over consumed tool_use records (not the
    raw JSONL line number) so downstream scorers see a compact timeline.
    Non-tool records (``permission-mode``, ``file-history-snapshot``,
    ``attachment``, ``last-prompt``, user prompts, assistant text-only
    replies) are skipped — they don't represent agent actions.
    """
    transcript_path = Path(path)
    events: list[TraceEvent] = []
    results: dict[str, str | None] = {}

    # First pass: collect tool_results keyed by tool_use_id, assistant tool_use in order.
    tool_uses: list[tuple[str, str, dict[str, Any]]] = []  # (use_id, name, input)

    with transcript_path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            rtype = rec.get("type")
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue

            if rtype == "assistant":
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        use_id = str(block.get("id", ""))
                        name = str(block.get("name", "")).strip()
                        tool_input = block.get("input", {}) or {}
                        if not isinstance(tool_input, dict):
                            tool_input = {}
                        tool_uses.append((use_id, name, tool_input))
            elif rtype == "user":
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        use_id = str(block.get("tool_use_id", ""))
                        results[use_id] = _summarize_result(block.get("content"))

    # Second pass: assemble TraceEvents in order.
    for t, (use_id, name, tool_input) in enumerate(tool_uses):
        if name == "Bash":
            kind: TraceEventKind = _classify_bash(str(tool_input.get("command", "")))
        elif name == "PowerShell":
            kind = _classify_bash(str(tool_input.get("command", "")))
        else:
            kind = _TOOL_KIND.get(name, "tool_call")
        scope = _extract_scope(name, tool_input)
        intent = (
            tool_input.get("description")
            or tool_input.get("query")
            or tool_input.get("intent")
        )
        if isinstance(intent, str):
            intent_val: str | None = intent[:160] or None
        else:
            intent_val = None
        result_summary = results.get(use_id)
        new_facts = [result_summary] if result_summary else []
        events.append(
            TraceEvent(
                t=t,
                kind=kind,
                tool=name or None,
                scope=scope,
                intent=intent_val,
                result=result_summary,
                new_facts=new_facts,
            )
        )

    return Trace(events=events)


__all__ = ["parse_claude_code_transcript"]
