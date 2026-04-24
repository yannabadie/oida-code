"""Hermetic code-domain trace fixtures (Block D2, QA/A9.md).

Each subdirectory under this package is one scenario with:

    repo/                  synthetic mini-repo (Python sources)
    request.json           AuditRequest (raw diff only)
    trace.jsonl            Claude Code transcript
    expected.json          expected scorer + graph + repair outputs
    README.md              scenario description + why it matters

Loaded by :mod:`tests.test_block_d2_hermetic_traces` which iterates the
10 scenarios and runs ``normalize`` + ``score-trace`` in both surface
modes where applicable, asserting against ``expected.json``.
"""
