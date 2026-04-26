**Scenario:** the requested scope contains `../etc/passwd` —
the existing sandbox (Phase 4.2-C, ADR-27) raises
`SandboxViolation` BEFORE the adapter is invoked. The gateway
captures the violation in an audit event with
`policy_decision="block"` and a reason starting with
`"sandbox violation:"`.

Phase 5.2 keeps this defence layered: gateway hardening
(5.1.1 mismatch + admission), then sandbox path traversal,
then the deny-pattern list (`.env`, `*.key`, secrets).
