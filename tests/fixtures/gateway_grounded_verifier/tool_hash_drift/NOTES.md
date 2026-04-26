**Scenario:** the served `definitions.json` carries a description
that differs from the operator-approved fingerprint — the
gateway must quarantine the tool, refuse to run pytest, and
audit the event with `policy_decision="quarantine"`.

The approved fingerprint's description hash was computed for
the canonical Phase 5.1 description "Run pytest (read-only)."
The served description has been rewritten, so the runtime
fingerprint does not match. ADR-36 + ADR-37 require quarantine
on drift.
