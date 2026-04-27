# Diagnosis — case_001 pytest evidence failure (run 24995045522)

_QA/A39 §"Detailed work expected" item 2 — answer the 10 specific
questions about why the operator-soak gateway emitted no
`[E.tool.pytest.0]` evidence on the first cycle._

## Symptom recap

- run 24995045522 (`operator-soak.yml`) completed at 1m56s with
  workflow conclusion `success`.
- inside the gateway-grounded path:
  - `gateway-status: diagnostic_only`
  - `gateway-official-field-leak-count: 0`
  - 1 tool call (pytest)
  - **0 accepted claims**, **1 rejected claim**
- the rejected claim (`C.docstring.no_behavior_delta`) cited
  `["[E.event.1]", "[E.event.2]", "[E.tool.pytest.0]"]` in
  `evidence_refs`. The verifier rejected it with
  *"claim cites unknown evidence_refs ['[E.tool.pytest.0]']; rejecting"*.
- the audit log shows the pytest tool ran for **193 ms** and exited
  with `reason: "adapter completed with status=error"`,
  `evidence_refs: []`.

## The 10 questions (QA/A39 §"Detailed work expected" item 2)

### 1. What command did the gateway try to run?

```
pytest -q --no-header --maxfail=20 ./tests/test_phase5_7_operator_soak.py
```

Composed by `PytestAdapter.build_argv` at
`src/oida_code/verifier/tools/adapters.py:346-352` (line numbers
pre-patch). The scope (`tests/test_phase5_7_operator_soak.py`)
came from the bundle's `pass1_forward.json` `requested_tools` entry.

### 2. What was the cwd?

`policy.repo_root` resolved to `Path(".")` inside the verify-grounded
process. The `default_subprocess_executor`
(`src/oida_code/verifier/tools/adapters.py:78-115`) passes
`cwd=ctx.cwd` to `subprocess.run`, where `ctx.cwd = repo_root`. With
`repo_root="."`, the subprocess inherits the parent's actual cwd.

### 3. What was the repo root?

The bundle's `tool_policy.json` carries
`"repo_root": "."` — bundle-relative, resolved at run time. The
verify-grounded process was started by the composite action's
"Run audit" step, which has no explicit `working-directory:` in
`action.yml`, so it inherits `$GITHUB_WORKSPACE` =
`/home/runner/work/oida-code/oida-code/`. **That is the workspace
root, not the case-001 target ref's working tree.**

### 4. What was PYTHONPATH?

Inherited from `actions/setup-python` — no explicit `PYTHONPATH`
override in `operator-soak.yml`. The composite action installs
`oida-code` in editable mode from `${{ github.action_path }}` (i.e.
`oida-main/`); that install is what `import oida_code` resolves to.

### 5. Which checkout did pytest run against?

**Neither.** pytest was invoked with cwd=`$GITHUB_WORKSPACE` (the
workspace root, not `oida-main/` and not `oida-target/`) and a scope
path `./tests/test_phase5_7_operator_soak.py`. That path resolves to
`/home/runner/work/oida-code/oida-code/tests/test_phase5_7_operator_soak.py`
which **does not exist** — the workspace root has no top-level
`tests/` directory; tests live inside `oida-main/tests/` and
`oida-target/tests/`.

### 6. Which checkout contained the editable oida-code install?

`oida-main/` (per `action.yml:256` —
`working-directory: ${{ github.action_path }}` on the install
step). That is the checkout from which `pip install -e ".[dev]"`
ran.

### 7. Which checkout contained the target branch?

`oida-target/` (per the second `actions/checkout@v4` step in
`operator-soak.yml`, `path: oida-target` with
`ref: ${{ inputs.target-ref }}`).

### 8. Why did pytest return status=error?

**pytest exited rc=4 (usage error: file or directory not found)**
in ~193 ms because the scope path it was given does not exist at
its cwd. With rc=4 and zero parseable `FAILED ` lines on stdout,
the adapter's status logic
(`src/oida_code/verifier/tools/adapters.py:177-186` pre-patch) flips
to `status="error"`:

```python
rc = outcome.returncode or 0
if findings:           # no findings parsed
    status = "failed"
elif rc != 0:          # rc=4 ⇒ this branch
    status = "error"
else:
    status = "ok"
```

### 9. Why was no [E.tool.pytest.0] evidence emitted?

`PytestAdapter.parse_outcome`
(`src/oida_code/verifier/tools/adapters.py:354-401` pre-patch) only
emits an `EvidenceItem` in TWO situations:

- one item per `FAILED ...` line on stdout (none here — no tests
  collected);
- one synthetic `[E.tool.pytest.0]` "passed cleanly" item ONLY when
  `returncode == 0 and not findings and stdout.strip()`.

With rc=4 and empty stdout, neither branch fires. `parse_outcome`
returns `(items=[], findings=[], warnings=[])`. The base class's
`ToolAdapter.run` then returns
`VerifierToolResult(status="error", evidence_items=())` —
**status=error with zero citable evidence**.

### 10. Root cause category

**Two compounding bugs.**

#### (A) Workflow topology bug

The dual-checkout in `operator-soak.yml` (oida-main/ for action +
bundle, oida-target/ for audit subject) leaves the verify-grounded
process running with cwd=workspace root, while the bundle's
`tool_policy.repo_root="."` resolves to that wrong cwd. pytest's
scope path `tests/test_phase5_7_operator_soak.py` is therefore
unfindable — not because the test file doesn't exist anywhere, but
because at workspace root level neither `oida-main/tests/` nor
`oida-target/tests/` is unprefixed.

This is a fixture/topology issue. Fixing it requires either:

- adding `working-directory:` to the composite action invocation in
  `operator-soak.yml` so the verifier runs from inside one of the
  checkouts, OR
- editing the bundle's `tool_policy.json` to embed an absolute path
  resolved at runtime, OR
- threading `repo-path` from the composite action down into
  `tool_policy.repo_root` automatically.

**Phase 5.8.1 does NOT apply this fix.** The topology fix is more
invasive (multi-file workflow + composite-action surgery) and
requires its own QA cycle.

#### (B) Adapter invariant violation

Independently of the topology bug, the adapter base class violated
the QA/A39 §4 invariant:

> Every requested tool produces at least one citable EvidenceItem
> (with id `[E.tool.<binary>.0]`) OR an explicit blocker. A tool
> requested by the verifier must NEVER silently emit
> `status="error" + evidence_items=()`.

Pre-patch, **all four** error paths in `ToolAdapter.run` (tool_missing,
timeout, parse exception, rc!=0 with no findings) returned
`evidence_items=()`. Any claim that pre-cited `[E.tool.pytest.0]`
during pass-1 forward (so the verifier could ground a pass-2
claim) would silently lose its grounding when the tool failed —
exactly what happened here.

**Phase 5.8.1 fixes (B).** The patch is in
`src/oida_code/verifier/tools/adapters.py` and adds a
`_diagnostic_evidence` helper that synthesises a citable
`[E.tool.<binary>.0]` `EvidenceItem` with `kind="tool_finding"` on
each error path. The downstream Phase 5.2.1-B contradiction
enforcer remains responsible for deciding whether the diagnostic
*supports* the claim — that semantic check is unchanged.

## Why patching (B) without (A) is the right move

1. **(B) is a universal invariant** — applies to all 3 adapters
   (ruff, mypy, pytest) and any future ones. Fixing it now removes
   a whole class of silent failures.
2. **(B) is minimal scope** — one helper + four call sites in one
   file (~30 lines added).
3. **(A) needs operator decision** — the topology fix interacts
   with case_002 / case_003 (which audit external repos). Picking
   the right approach (working-directory vs. repo_root mapping vs.
   composite-action threading) needs a QA round of its own.
4. **(B) lets case_001 produce a non-empty `[E.tool.pytest.0]`
   evidence item even with the topology bug still present** — so
   the rerun signal is still imperfect (pytest still crashes at
   the bad cwd), but at least the verifier doesn't silently reject
   on missing evidence. The cgpro label after the rerun will then
   reflect the *real* signal: "(B) is fixed, (A) is still wrong".

## What this diagnosis does NOT do

- It does not patch the workflow topology bug (A). That stays for
  a follow-up phase.
- It does not auto-rerun case_001 — Phase 5.8.1 requires explicit
  cgpro + Yann double-gate before any new dispatch.
- It does not assert that the patch fixes the gateway's wider
  usefulness — only that the citable-evidence invariant holds.
- It does not change `enable-tool-gateway` default (still `false`).
- It does not introduce MCP, provider tool-calling, write/network
  tools, or any forbidden product-verdict token. ADR-22 hard wall
  holds.
