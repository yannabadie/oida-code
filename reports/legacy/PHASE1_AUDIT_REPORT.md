# PHASE 1 AUDIT REPORT — `oida-code` deterministic audit layer

Generated: **2026-04-24**.
Active plan: `PLAN.md` §14 Phase 1.
Repo: <https://github.com/yannabadie/oida-code>.
Preceded by: `PHASE1_REPORT.md` (historical, describes Phase 0 output).

---

## 1. Files created / modified in Phase 1

### New files

```
e41021410f22cb9cba11bc5a01ab41e66e47ffa55b17d8e2e4619157954c19b0  src/oida_code/models/evidence.py
25fc607012b10cd7f26875416c0715149b9bb6c87f7ad096d80e15ac358644e8  src/oida_code/verify/_runner.py
a8c8dfbd1bb875444329163a68f293155c154e94d872c4692529c961d0918ecd  tests/test_blast_radius.py
cca27fccf10abec06bbd1b783a6ac5326ff8d28fda36255c5c4d838cbffe53b7  tests/test_cli_audit.py
a2eb0612e0c1e04336dd7eb681fe3de8cf4a487b75ad793c17a6d58412536c47  tests/test_detect_commands.py
4296c4912f73a3dfaa64c4faf5d1931f1f7f5e281d78f00fb364115f4261adb6  tests/test_reports.py
cc2dd66011b39e233a8274ecbc06485d47f85b578e11ba9240ccb5fccb896567  tests/test_verdict.py
8794700a073248b241fe51229c97716ec80962b77e5ebc39a72a0ae379dff8de  tests/test_verify_runners.py
```

### Modified files (SHA256 after Phase 1)

```
66cd29cc13ef47a6a2fdc5734a322b909c017afdf10612d0764fd47ac16f09b2  src/oida_code/verify/lint.py
0eed4a114ad657f6bc317b432c80066d7f6bef007dd3eebe515dc17a7afe735c  src/oida_code/verify/typing.py
13082c1ce8979066f111f8e8d8f3d2613c5f29420f595eff5ecd5ebd975a5979  src/oida_code/verify/pytest_runner.py
9d2968900815d49c76e7f27b6ab51d270f977bddef759a7ff0ffb62673f69414  src/oida_code/verify/semgrep_scan.py
815c41adca8428f2819b352c0a6b13ba5b74ca48f88242bac2e3e465a6304d87  src/oida_code/verify/codeql_scan.py
d11fffbc83aff66c0700cf5fef8eb24c0d5de15f5b991e57dc1df20189d88d3f  src/oida_code/extract/blast_radius.py
377613be706d5e9af7d9f18247097d63bd665b37347bc4415194b4f15d9e55cb  src/oida_code/score/verdict.py
254b08dd5b091fbf060423209b7fb04aca2f9c25eb071513ff7702ea5b29f332  src/oida_code/ingest/manifest.py
b834e4c4d82feda495a8c70ae324ebc94268bf6f00cb53b41c7e8816109c2870  src/oida_code/cli.py
9d28ee159fe12000325ce5392a8dd7bf8f218ef7e8882d927af06fe4284a375a  src/oida_code/models/audit_request.py
de636d979f4a1d3d4b1e355ca2ad5cee15487fba7a03307c144630d475760d79  src/oida_code/models/audit_report.py
62e3cd98908a68096c0fa7449031f8fb8576ce231cb50cb43f1de042f09f84b9  src/oida_code/models/__init__.py
d3d96e1ff1896de5f5e957dcec9b5fc4820a32a691b7482cedb4c9eba1261c1d  src/oida_code/report/json_report.py
b141d0b0358361f92617971846fe2e27e7274c8a713430653d68bdd837eb114e  src/oida_code/report/markdown_report.py
aa4d71d6a74e0c8b75291dbb2526116ed292bbb7335e7b2adc141576b06f84c7  src/oida_code/report/sarif_export.py
b40c2d6cc26656c5b103795c34519b8a909073bdd09844468bc87a69340174cb  examples/audit_request.json
a610b2adf224c17a7666cdf9f2f8e520affbd4921fa855c1b19aec866f1212c7  examples/audit_report.json
392b75f0db244e92b6cc7e2036f77ba2eaa13a6a4b8033a0bbad45a31af53552  tests/test_cli_smoke.py
```

Memory-bank updates and docs (not SHA-listed): `memory-bank/{progress, activeContext, decisionLog}.md`, `README.md`.

Total Phase 1 delta: **8 new files + 19 modified files = 27 file changes**.

---

## 2. Quality gates (verbatim)

```
$ .venv/Scripts/python.exe -m ruff check src/ tests/
All checks passed!

$ .venv/Scripts/python.exe -m mypy src/oida_code
Success: no issues found in 43 source files

$ .venv/Scripts/python.exe -m pytest -q --cov=oida_code --cov-report=term
.....................................................                    [100%]
...
TOTAL                                         922    167    230     52    78%
53 passed in 13.24s
```

- **53 tests**, all passing (was 10 at Phase 0).
- **Coverage 78 %** (was 74 % at Phase 0). Gains: new runners, verdict, blast_radius, detect_commands, reports, CLI audit smoke. Losses: `semgrep_scan` sits at 24 % (dev env lacks semgrep on Windows).

---

## 3. Validation runs (4 targets)

The exit criterion in PLAN.md §14 P1 is "stable report on **10 Python repos** without human intervention". Per advisor scope-realism call, Phase 1 validated on **4 targets** — 3 in-workspace + 1 external — and explicitly defers the 10-repo criterion to the Phase 2 gate.

| # | Target | Nature | Verdict | Crash? | Notes |
|---|---|---|---|---|---|
| 1 | `./` (oida-code self) | in-workspace | `counterexample_found` | no | ruff: 119 findings; mypy: 160 findings; pytest: `error` (subprocess-Python bug, see §7). |
| 2 | `./search/OIDA/oida_framework` | in-workspace | `counterexample_found` | no | ruff: 41; mypy: 1; pytest: `error` (same cause). |
| 3 | `./search/OID/oid-framework-v0.1.0` | in-workspace | `counterexample_found` | no | ruff: 78; mypy: 158; pytest: `ok` (0 tests collected, exit 5). |
| 4 | `python-attrs/attrs` `--depth=1` | **external** (cloned to `.oida/validation-external/attrs/`) | `insufficient_evidence` | no | ruff: 0; mypy: 0; pytest: `error` (attrs' own test deps not installed in our venv). |

All four produced schema-valid JSON / SARIF 2.1.0 / Markdown outputs.

Raw JSON reports available in the gitignored `.oida/validation/` directory.

---

## 4. Decisions NOT in the blueprint

9 ADRs were added during Phase 0 (01-09); 3 more in the merge (10-12); **2 new in Phase 1 (13-14)** — all logged in `memory-bank/decisionLog.md`.

| ADR | Decision | Phase | Rationale |
|---|---|---|---|
| 13 | `ReportSummary` fusion fields are `Optional[float] = None`; Phase 1 emits `null`. | Phase 1 | Advisor option (a). Rejected (b) "dual summary block" (doubles schema) and (c) "emit 0.0 with footnote" (silent lie). Markdown renders `null` as "_not computed in Phase 1_". |
| 14 | `oida-code verify` consumes `AuditRequest` (not `NormalizedScenario`) in Phase 1. | Phase 1 | Blueprint §8 shows verify ← scenario, but `normalize` is a Phase 2 concern. Rather than stub verify, it accepts AuditRequest directly. Phase 2 adds a content-type sniff to accept either shape. |

Additional design choices this phase, each small enough not to merit an ADR:

- **Shared subprocess helper** (`verify/_runner.py`) with `RunResult` dataclass. Uniform contract: never raise, always return a status-tagged result. UTF-8 enforced (Windows cp1252 bit us once).
- **`probe_version` for lazy `tool_version` population.** One extra `--version` subprocess per OK-status runner; keeps the schema field meaningful instead of always-None.
- **Severity mapping for ruff**: `E|F|S|B` prefixes → `error`, rest → `warning`. Naive but transparent.
- **Blast-radius weights** 0.20 modules / 0.20 api / 0.35 data / 0.25 infra — data + infra weighted highest because they map to the Replit DB wipe / Kiro delete-and-recreate class of incidents the paper cites.
- **CodeQL = uniform stub.** `status="tool_missing"` when CLI absent, `status="skipped"` with rationale when present. Phase 2 lands the real integration.
- **JUnit XML over `pytest-json-report`** (advisor choice): zero runtime dep, stable across pytest versions.
- **Semgrep + CodeQL kept out of `pyproject.toml` deps.** Expected on PATH; degrade gracefully via §5 contract.

---

## 5. Contradictions / surprises in source material

Phase 1 introduced no new document contradictions (the merge that produced PLAN.md already resolved them). Surprises:

1. **Ruff's `--output-format=json` emits absolute paths by default**, not relative. This is fine for SARIF (which wants URIs) but if we ever serve audit reports cross-machine we'll need to re-root them. Not fixed in Phase 1.
2. **Typer 0.24 deprecation noise.** `DeprecationWarning: The 'is_flag' and 'flag_value' parameters are not supported` still surfaces in test output, coming from Typer's `params.py` internals even after we removed `is_flag=True`. Upstream issue.
3. **`resolve_verdict`'s behavior is conservative.** Any `tool_missing` tool → `insufficient_evidence`. That correctly means "can't verify with partial evidence", but for a user who is deliberately not installing CodeQL it may be jarring. Flagged in Phase 2 carry-over.

---

## 6. Open questions ranked

### Blocking Phase 2

None. All advisor-blocking items from the pre-ship review were addressed (ADR-13 written; 1 external repo cloned; subprocess-Python bug disclosed; `progress.md` updated).

### Carry-over tickets (fix in early Phase 2)

1. **Pytest / mypy subprocess-Python bug.** `shutil.which("pytest")` can resolve to a pytest bound to a different Python than the one running oida-code (e.g. miniforge3 system-wide vs. our venv). The target's tests then fail to import the target's own package. Fix: probe `sys.executable -m pytest` availability and prefer it when the resolved binary's Python differs from `sys.executable`.
2. **10-repo exit criterion deferred.** Validation ran on 4 targets; PLAN.md P1 says 10. Phase 2 will bundle a public-repo evaluation script (`datasets/repo_suite.txt` → CSV report) and close this gate.
3. **semgrep_scan JSON parser is untested.** Coverage 24 % because dev env lacks semgrep. Add a fixture-based unit test driving `_parse_semgrep` against canned JSON strings.
4. **`--fail-on corrupt` structurally unreachable in Phase 1** (no V_net → no `corrupt_success`). Wired, no crash, but not useful until Phase 5 fusion.
5. **ruff warnings do not surface as `critical_findings`** (by design — only `severity="error"`). Markdown counts column surfaces them. Re-check the shape when Phase 2 fusion lands.

### Nice-to-have

6. **`.gitattributes` for LF endings** — still producing CRLF warnings on every commit (Windows `core.autocrlf`). Low priority.
7. **PyPI release cadence** — not published yet; installable via `pip install git+https://github.com/yannabadie/oida-code`.
8. **GitHub Action CI** — all gates run locally only. Phase 6 will add, but a minimal push-gate workflow could land sooner.

---

## 7. Honest self-critique — defensible vs placeholder

### What is defensible

- **`Finding` + `ToolEvidence` + `ToolBudgets` + `VerdictLabel`**: advisor-vetted abstraction. Strict `extra="forbid"`, runners never invent their own return shape, CodeQL absence is the same code path as any missing tool.
- **Shared `run_tool` helper**: UTF-8 enforced, timeout wraps every tool, catches `OSError`, never raises. Uniform contract exercised by 5 runners.
- **`run_lint` (ruff)**: real JSON parsing, tested end-to-end on oida-code, oida_framework, oid_framework, attrs. Severity mapping transparent.
- **`run_type_check` (mypy)**: stdout regex parser handles the absolute-path + column format, skips `note:` lines. Validated across 4 repos.
- **`estimate_blast_radius`**: weighted signals; 7 table-driven tests; output bounded `[0, 1]`. Calibratable.
- **`resolve_verdict`**: 6 table-driven tests, covers verified / counterexample_found (regression + static-error) / insufficient_evidence. `corrupt_success` explicitly dark until Phase 5.
- **`detect_commands`**: handles malformed `pyproject.toml` without crashing, honors setup.cfg flake8 / pyrightconfig.json / marker files.
- **Schemas v1.1 round-trip**: `AuditRequest` and `AuditReport` still round-trip deterministically on the updated examples. Example `verdict` updated to `corrupt_success` (valid `Literal`).
- **SARIF 2.1.0 minimal compliance**: `version`, `$schema`, `runs[].tool.driver.{name,version,rules}`, `runs[].results[]`. GitHub code-scanning should accept this.
- **Every runner reports `tool_version`** when status=ok (via `probe_version`).

### What is placeholder — DO NOT PRETEND OTHERWISE

- **`run_pytest` on the oida-code repo itself errors.** When `shutil.which("pytest")` finds a pytest bound to a different Python, collection fails with `ModuleNotFoundError: No module named 'oida_code'`. The runner surfaces this as `status="error"` with stdout excerpt — graceful — but **it means self-audit never actually exercised pytest's regression path**. Tests that assert `verdict ∈ {verified, counterexample_found, insufficient_evidence}` pass because the error path routes through `insufficient_evidence`, not because pytest collected anything. Phase 2 ticket.
- **`run_semgrep` parser is unexercised** in CI because dev env on Windows lacks semgrep. The JSON-parse logic (lines 33-71 of `semgrep_scan.py`) has 0 % coverage. Ship risk: minimal (dev-only) but not zero.
- **`run_codeql` is a stub.** It returns `tool_missing` always (no CLI probe does anything). Phase 2 integration work is substantive.
- **`AuditRequest.policy.min_mutation_score` / `min_property_checks`** are accepted in the schema but **NOT enforced** by `resolve_verdict` in Phase 1. Their inputs (mutmut, hypothesis) ship in Phase 2. Documented in `score/verdict.py` docstring.
- **`ReportSummary.mean_q_obs` / `mean_grounding` / `total_v_net` / `debt_final` / `corrupt_success_ratio`** all emit `null` from Phase 1 reports. They require the Phase 5 fusion. ADR-13 covers the trade-off.
- **`oida-code normalize` + `repair` commands stay `NotImplementedError`.** Phase 2 / Phase 5 respectively.
- **No genuine "all tools green → verdict=verified" integration test.** Unit tests cover the resolver branch; no end-to-end test exercises it because no target repo I ran has all 5 tools passing (semgrep + codeql missing on dev env).
- **`--fail-on corrupt` is wired but structurally unreachable in Phase 1.** Flag accepted, exit code logic present, but `corrupt_success` label cannot be emitted without Phase 5 fusion.
- **No CI** — gates run on my machine only.
- **No PyPI release** — installable via git clone + `pip install -e ".[dev]"`.

### One-line verdict

Phase 1 ships a defensible deterministic-audit skeleton: 2 real Python static analysers (ruff, mypy) feeding a uniform evidence contract, a verdict resolver with honest rationale trail, 3 report formats (JSON / Markdown / SARIF 2.1.0 minimal), and a CLI that completes end-to-end on 4 real Python targets without crashing. **The semgrep / codeql / pytest layers are scaffolding that will earn their coverage in Phase 2 or when run inside a matching venv.**

---

## 8. Stop and wait

Per PLAN.md §14 Phase 2 entry gate: **"Phase 1 shipped."** That gate is now met pending user sign-off.

Awaiting explicit **"go Phase 2"** before starting the observation model + obligation graph (models/trace.py + models/obligation.py + extract/obligation_graph.py + 50-100 hand-annotated trace dataset).
