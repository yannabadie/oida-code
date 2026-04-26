"""Phase 5.6 (QA/A33.md, ADR-41) — opt-in gateway-grounded
GitHub Action helpers.

This package hosts the three Python helpers the composite
GitHub Action calls when ``enable-tool-gateway: "true"``:

* :mod:`bundle` — operator-supplied bundle validator (8
  required files, no path traversal, no secret-shaped paths,
  no provider/MCP config).
* :mod:`summary` — Markdown step-summary renderer with a
  runtime forbidden-phrase scan.
* :mod:`status` — :class:`Literal` ``GatewayStatus`` enum
  (``disabled`` / ``diagnostic_only`` / ``contract_clean`` /
  ``contract_failed`` / ``blocked``) — product verdict
  vocabulary (``merge_safe`` / ``verified`` / ``production_safe``
  / ``bug_free``) is structurally unrepresentable.

Phase 5.6 hard rules (ADR-41, QA/A33 lines 9-15):

* No MCP runtime, no JSON-RPC dispatch.
* No provider tool-calling.
* ``enable-tool-gateway: false`` default.
* No ``pull_request`` / ``pull_request_target`` execution.
* No write tools, no network egress.
* No official ``total_v_net`` / ``debt_final`` /
  ``corrupt_success`` emitted.
"""
