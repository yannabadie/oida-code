# PHASE 1 REPORT — `oida-code` bootstrap

Generated: **2026-04-24 07:04:50 UTC**.
Repo: <https://github.com/yannabadie/oida-code> (public, MIT).
Reference plan: `prompt.md` + `oida-code-mvp-blueprint.md`.

---

## 1. Files created in phase 1

Four commits on `main`:

```
257040a test: phase 1 smoke tests (roundtrip, CLI, vendored analyzer)
a887b9a feat: phase 1 skeleton — CLI inspect, Pydantic I/O models, vendored OIDA scorer
44db7df docs: add MIT LICENSE
15138f3 chore: initial brainstorm and research snapshot
```

File list + SHA256 (new files only, excluding the snapshot commit and `LICENSE`):

```
f178a093739b54833c0ccb585c35a6e2385a1a46e2cbaa7be6327baa353a6107  examples/audit_report.json
eeec2776604a123ec41bcecf55950a87118fb8fe231ebc40446c52c26e72c55f  examples/audit_request.json
f25c27989c390f39406f656ff2ebcbb5573fbc16d63bcdfacf6a1b156e019d66  examples/normalized_scenario.json
415156029bebcbc45fc63592578b989b23b4fe8868cdc5897bde9e64aaacc148  pyproject.toml
850f1067f1ed8cd493369c4e97a9512606592dc3e89860ca2817b45c19ba0792  README.md
e0db324387a94c03648e7a2945f98088d36730e6cac8b6f955a7e8ea39574511  src/oida_code/__init__.py
41fd5275a5220bffa16a0a956b3cdb407629f69f35ef63460242cb9775a06972  src/oida_code/_vendor/__init__.py
b7c4fc53564805264de594aaa3513507e580fe6d56431f8caded3e8cb54ab6d7  src/oida_code/_vendor/oida_framework/__init__.py
ae1d805669fa0195bee89ffe4e4361f485e78a22d7daecb2a3f4dea31d46a4b4  src/oida_code/_vendor/oida_framework/analyzer.py
7f08fc1a761d5867d6f14040e17eee4ed441990b650b5953a66bfece9f7b9758  src/oida_code/_vendor/oida_framework/io.py
1d8ac478c2f218c47c45f17b14878fd8ec94d7ac9fe00a242712767558472713  src/oida_code/_vendor/oida_framework/models.py
7da5542da264e5c28485dfb4bd8696fc5a5491f1f67ef879376140b997bbb33f  src/oida_code/_vendor/oida_framework/VENDORED_FROM.txt
a01cc56f409e5ddd4ea559eed4cd39b9d05035a86a59697927e5fdafa5fdddc5  src/oida_code/cli.py
52a847432ba418242c04ddfcd528d4666112b072e6892fa1cf9986c18d546796  src/oida_code/config.py
6f548e5a7b3efc2152f3871c8b19579924bfc11bf57cf74ea42cb722b13df6a9  src/oida_code/extract/__init__.py
ce414d83c17caf9475948dea7e750e34b057fa25a467c6f3305054e541d744f2  src/oida_code/extract/blast_radius.py
2dd03334376024bd105b18af48554d2551aea1b65c561ed77f0890baf5ca86f2  src/oida_code/extract/claims.py
196f965ea13dafbbcec714472c01a9591733dd3f35384df04be26a58b4933e5c  src/oida_code/extract/dependencies.py
e4fac6fd3c1a21c179a3c809d0c639df4dd64ba4912edd53a3ea856d04e4d4d5  src/oida_code/extract/preconditions.py
0b2920fa9632f8328408553291cbd5d35a3843e0bf644ffe638d0863d4bf704e  src/oida_code/github/__init__.py
c5198b3066e0410c8d766b2cd508b526f1de85a226ebaeedeb8928bef99022d7  src/oida_code/github/annotations.py
ae142eee6d0775e5d1158caab334cb8ed7f0035148b682235080a8f5f2721701  src/oida_code/github/checks.py
b0ecdffda8e0888a304a1738950175764ee9f9b2654a9ed3e0050b3c04a011f7  src/oida_code/ingest/__init__.py
c088643a84c21081b23c295a8b42d797c68ec17003d4d1c749661be82157015d  src/oida_code/ingest/diff_parser.py
985e1384ad0af1933149004ed7e3743b900c726ecef0982a5bc8882b0985ab4a  src/oida_code/ingest/git_repo.py
dad84a61b30caf41e3aa7bed3a54cc5c3e2a64072f23eb72131682975c317353  src/oida_code/ingest/manifest.py
516f6f91dc026dd319e75445fccfb75189ac8fbded20cdfdee5ac44c4fe4eb88  src/oida_code/llm/__init__.py
17a4cc3afef2a5803ba1dc0d2207248749d749022e06321026662b8ab0dcf5a5  src/oida_code/llm/backward_verifier.py
b451045b5573e3c93d34e0845ff7e589ac57f2c45984fdd2e6b7c7c8c6429f7e  src/oida_code/llm/client.py
cc423fa3ca730244c6a50e74d19da10e446624194703680ab2fec9c360fad703  src/oida_code/llm/forward_verifier.py
becba94e02ac31861d4da79074e7cc3fd33bd02b7d8096a5c49e25d15e6404a6  src/oida_code/llm/repair_prompts.py
d119cce644412f5d46e473b86c84b2030c280a6af0842957c558a50b8817f483  src/oida_code/llm/schemas.py
92fa8a90ad072725d4985d666fc28ac69fc4cff4a35aa1f17e1430265af2a0fa  src/oida_code/models/__init__.py
37d244c9a78c4ed962d705b4887f3bd7ac1190efce4859eb512465ea26e753ab  src/oida_code/models/audit_report.py
9dd07a2db04509ed19fc090f52a5e3ce6e59c1a074e8809227815a297eaba315  src/oida_code/models/audit_request.py
0f916ca906dd745d21891c65d602cb53c611795f1f53a41ff80908f634a47444  src/oida_code/models/normalized_event.py
de5f15f885cbe788290758816bc09ce90a98e95e66d3180b17bfae2a6385e2b9  src/oida_code/report/__init__.py
ec0e373ca57d96ada43919b9b26713aef517c80754548532ca04e6dcf74dde1d  src/oida_code/report/json_report.py
1d2420b1771e54dc1d1e67367b0f2c0135be26280dd62864b26c77848312c647  src/oida_code/report/markdown_report.py
83def8c7976d433fdef3d370e52e13a34ad272c2e6b4e29018dd9dc9dd994104  src/oida_code/report/sarif_export.py
2027106173d6fc67db47f7803e6cfb9766035090760ff209679d5575f539f642  src/oida_code/score/__init__.py
9be3f4701c16aec6d8dff0bf93ff2b41168e76563f0b3add75051589091526af  src/oida_code/score/analyzer.py
d788aefd62bb6b5ddba4261e3cb4e092c3c3d9f95e87a81f487114f1b83baccf  src/oida_code/score/mapper.py
2da21aa966d96c88f36bfb533d2096edfef25111222daa8f6831f035a48b9cdc  src/oida_code/score/verdict.py
777d8f943d0efe9bfaa149beb49a05ee0ab7767005424c2f69fd9d4029ce975d  src/oida_code/verify/__init__.py
6b58a2188c04b26c5b2055c4fd251dda1039762b9a1bc9afc17984f7321ecb0e  src/oida_code/verify/codeql_scan.py
3416327157789c9de4800775056654117e82d7948113c6ca5df2fb770094ca91  src/oida_code/verify/hypothesis_runner.py
842ff78c534055a68c08735b39c2495f01fe09c55268e178da839ac146582eb2  src/oida_code/verify/lint.py
a9ad35206559105fe6f84811f353ed62ee330d7dcb2ed383310823f483365d35  src/oida_code/verify/mutmut_runner.py
a0c595caf3f9d8b77f5e717826f280861b4e5d5e8eef181e5e6356dce846b49c  src/oida_code/verify/pytest_runner.py
0f05ddf62a09fee1386cd0a53d165c13530bb4e4db396932d599e8ac77919997  src/oida_code/verify/semgrep_scan.py
97cfe536e1e974d546b5e53db89219b8946ca4eadd4d1d16c5536c967c924470  src/oida_code/verify/typing.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  tests/__init__.py
cb531c2913c4c87db31c1b20fbaafca1d960ed4df1a68f81fe4c01a991a2da48  tests/conftest.py
6e48c93fd657eb32ed23f32717611e96cdcb8def97f6be409428bd8732380988  tests/test_cli_smoke.py
4e16fc2a2183b378a555f0fae1ea4f28b47fe915940ab0d61f2119415bff06e8  tests/test_models_roundtrip.py
e96c0ebec1accb51d1dc7c14d8fe4bf85a946728f552754e1e03fdaaaa17f849  tests/test_vendored_analyzer.py
```

Total: **57 new files** (47 Python + 3 JSON examples + README + pyproject.toml + LICENSE + 3 vendored marker + VENDORED_FROM + `.gitignore`, already counted in the snapshot).

The 4 vendored `.py` SHA256 match the upstream under `search/OIDA/oida_framework/oida/` byte-for-byte.

---

## 2. Quality-gate outputs (verbatim)

### Gate 1 — `ruff check src/ tests/`

```
All checks passed!
```

### Gate 2 — `mypy src/oida_code` (strict)

```
Success: no issues found in 41 source files
```

*(Source file count excludes 4 vendored modules, per `tool.mypy.exclude = ["src/oida_code/_vendor/"]`.)*

### Gate 3 — `pytest -q --cov=oida_code`

```
..........                                                               [100%]

Name                                        Stmts   Miss Branch BrPart  Cover
-----------------------------------------------------------------------------
src\oida_code\__init__.py                       3      0      0      0   100%
src\oida_code\cli.py                           46      7      4      1    84%
src\oida_code\config.py                         4      4      0      0     0%
src\oida_code\extract\__init__.py               0      0      0      0   100%
src\oida_code\extract\blast_radius.py           2      2      0      0     0%
src\oida_code\extract\claims.py                 2      2      0      0     0%
src\oida_code\extract\dependencies.py           2      2      0      0     0%
src\oida_code\extract\preconditions.py          2      2      0      0     0%
src\oida_code\github\__init__.py                0      0      0      0   100%
src\oida_code\github\annotations.py             2      2      0      0     0%
src\oida_code\github\checks.py                  2      2      0      0     0%
src\oida_code\ingest\__init__.py                0      0      0      0   100%
src\oida_code\ingest\diff_parser.py             9      2      2      1    73%
src\oida_code\ingest\git_repo.py               42      7      8      4    78%
src\oida_code\ingest\manifest.py                5      0      0      0   100%
src\oida_code\llm\__init__.py                   0      0      0      0   100%
src\oida_code\llm\backward_verifier.py          2      2      0      0     0%
src\oida_code\llm\client.py                     2      2      0      0     0%
src\oida_code\llm\forward_verifier.py           2      2      0      0     0%
src\oida_code\llm\repair_prompts.py             2      2      0      0     0%
src\oida_code\llm\schemas.py                    2      2      0      0     0%
src\oida_code\models\__init__.py                5      0      0      0   100%
src\oida_code\models\audit_report.py           29      0      0      0   100%
src\oida_code\models\audit_request.py          33      0      0      0   100%
src\oida_code\models\normalized_event.py       37      0      0      0   100%
src\oida_code\report\__init__.py                0      0      0      0   100%
src\oida_code\report\json_report.py             2      2      0      0     0%
src\oida_code\report\markdown_report.py         2      2      0      0     0%
src\oida_code\report\sarif_export.py            2      2      0      0     0%
src\oida_code\score\__init__.py                 2      0      0      0   100%
src\oida_code\score\analyzer.py                 4      0      0      0   100%
src\oida_code\score\mapper.py                   2      2      0      0     0%
src\oida_code\score\verdict.py                  2      2      0      0     0%
src\oida_code\verify\__init__.py                0      0      0      0   100%
src\oida_code\verify\codeql_scan.py             2      2      0      0     0%
src\oida_code\verify\hypothesis_runner.py       2      2      0      0     0%
src\oida_code\verify\lint.py                    2      2      0      0     0%
src\oida_code\verify\mutmut_runner.py           2      2      0      0     0%
src\oida_code\verify\pytest_runner.py           2      2      0      0     0%
src\oida_code\verify\semgrep_scan.py            2      2      0      0     0%
src\oida_code\verify\typing.py                  2      2      0      0     0%
-----------------------------------------------------------------------------
TOTAL                                         265     66     14      6    74%

10 passed in 0.94s
```

### Gate 4 — `oida-code inspect ./search/OIDA/oida_framework --base HEAD`

```json
{
  "repo": {
    "path": "C:\\Code\\Unslop.ai\\search\\OIDA\\oida_framework",
    "revision": "257040a4fd2fc29698d6e97373aba602b4d54627",
    "base_revision": "257040a4fd2fc29698d6e97373aba602b4d54627"
  },
  "intent": {
    "summary": "",
    "sources": []
  },
  "scope": {
    "changed_files": [],
    "language": "python"
  },
  "commands": {
    "lint": "ruff check .",
    "types": "mypy .",
    "tests": "pytest -q"
  },
  "policy": {
    "max_critical_findings": 0,
    "min_mutation_score": 0.0,
    "min_property_checks": 0
  }
}
```

Deserializes cleanly: `AuditRequest.model_validate(json.loads(payload))` → `deserialized OK`, `base == head`, `language = python`, `changed_files = []` (expected: `--base HEAD` yields empty diff).

---

## 3. Coverage summary

- **Total coverage: 74 %** (threshold: >70 %). 265 statements, 14 branches.
- **100 % coverage** on all code we actually implemented: `models/*`, `ingest/manifest`, `score/__init__`, `score/analyzer`, package `__init__`.
- **84 %** on `cli.py` (miss = console-script thunk + a couple of error branches).
- **78 %** on `ingest/git_repo.py` (miss = error-path branches for `FileNotFoundError`, timeout, non-zero exit — not exercised by smoke tests to avoid calling the real git binary with bad args).
- **73 %** on `ingest/diff_parser.py` (miss = the non-empty-diff branch, blocked by `--base HEAD` on a single-branch HEAD at smoke-test time).
- **0 %** on every `NotImplementedError` stub (`extract/`, `verify/`, `llm/`, `report/`, `github/`, `score/mapper`, `score/verdict`, `config.py`). That is expected: these modules are intentionally empty scaffolds for phases 2-4. `tool.coverage.report.exclude_lines = ["raise NotImplementedError"]` keeps them from polluting the top-line figure when their stubs are exercised in future phases.

Coverage > 70 % on code we wrote: ✓.

---

## 4. Decisions made that were NOT spelled out in the blueprint

These are the choices I made (with user's carte-blanche after the Step-0 digest — "comme tu veux"). Each is also logged as an ADR in `memory-bank/decisionLog.md`.

| # | Decision | Why not spelled out | Rationale |
|---|---|---|---|
| 1 | Vendoring layout = `src/oida_code/_vendor/oida_framework/` mirroring upstream, with `VENDORED_FROM.txt` + SHA256 pinning. | Blueprint §2 just says "keep the current OIDA core almost intact"; prompt Step 2 says "thin wrapper importing and re-exporting". Neither picks a physical layout. | Flat-copying would break the vendored `from .models import ...` relative imports; a path-dep on `search/` wouldn't survive `pip install`. A mirror layout is the minimum that works cleanly and lets `ruff`/`mypy` exclude the directory. |
| 2 | `Typer` instead of `Click`/`argparse`. | Plan says "Typer or Click". | Typer's `Annotated[T, typer.Option(...)]` is mypy-strict-clean and gives subcommand ergonomics for the planned 5-subcommand surface. argparse would be more boilerplate and less discoverable; Click needs more glue. Cost: +1 dep. |
| 3 | `--base HEAD` on a single-commit repo = valid `AuditRequest` with empty `changed_files`. | Gate 4 wording didn't disambiguate empty-vs-non-empty diff. | Real usage always passes `--base origin/main` or a SHA; the smoke-test form is the degenerate case. Treating it as "empty list, not an error" matches git's own behavior (`git diff HEAD..HEAD` exits 0 with no output). |
| 4 | `@app.callback(invoke_without_command=True)` so `oida-code --version` exits 0. | Not a blueprint concern; found empirically when `test_version_flag` failed. | Without this, Typer's "missing command" check fires before the callback's `typer.Exit(code=0)`. |
| 5 | Split phase-1 work into two commits (`feat:` + `test:`) instead of one. | Plan said "conventional commits, one logical change per commit, no 500-line mega commits" but didn't partition phase 1. | Keeps the skeleton commit reviewable on GitHub; tests are a separable concern. |
| 6 | `ingest/manifest.default_python_commands` ships as implementable helper; `detect_commands` stays `NotImplementedError`. | Blueprint doesn't say which manifest helpers belong in phase 1. | Auto-detection needs AST/packaging heuristics (phase 2); stock Python defaults (`ruff check . / mypy . / pytest -q`) are groundable and used by the `inspect` CLI today. |
| 7 | `model_config = ConfigDict(extra="forbid")` on every Pydantic model. | Blueprint doesn't specify strictness. | Extra fields at the public boundary should error, not silently pass. Prevents drift between the schema and example JSONs. Keeps round-trip semantics honest. |
| 8 | `ruff`/`mypy` exclude `src/oida_code/_vendor/**` via `pyproject.toml` (documented in comments on those blocks). | Plan said "ignore vendored code if needed, but document it in `pyproject.toml`". | Required to keep vendored code verbatim per ADR-02. |
| 9 | `NormalizedScenario` round-trip test uses dict-equivalence + serialization-idempotency, not byte-for-byte against the source file. | Plan says "byte-for-byte" for the two example JSONs; NormalizedScenario wasn't in that list. | The vendored `safe_online_migration.json` uses int weights (`"weight": 2`) and omits the optional `config:` block. Byte-for-byte would require hand-tuning the mapper — legitimately a phase-2 concern. Idempotency + dict-equality are the honest guarantees phase 1 can make. |
| 10 | Module docstrings cite blueprint § numbers. | Style convention, not spec. | Makes traceability obvious when a reader lands on a stub and wonders "when is this due?". |
| 11 | Python `>=3.11` pinned (not `>=3.10` like the vendored package). | Plan said "Python 3.11+". | Uses PEP 604 `|` unions throughout; `from __future__ import annotations` handles deferred evaluation but strict mode is cleaner on 3.11+. |
| 12 | `.env` + `.env.*` gitignored at repo init; verified via `git check-ignore` before any `git add`. | Plan says "never commit `.env`" but doesn't specify enforcement. | Belt + suspenders: the pre-`add` check confirms the ignore rule applies. Zero secrets leaked into any commit. |

---

## 5. Contradictions found in input documents and resolutions

Per the authority order in `prompt.md`: `oida-code-mvp-blueprint.md > brainstorm2_improved.md > last.md > infos.md > brainstorm2.md`.

| # | Documents in conflict | Conflict | Resolution |
|---|---|---|---|
| 1 | `brainstorm2.md` vs `infos.md §1` vs blueprint §1 | brainstorm2 proposes `unslop.ai`; infos.md documents 6+ active collisions; blueprint sets `oida-code`. | Blueprint wins → repo = `oida-code`. ADR-01. |
| 2 | `brainstorm2.md` vs blueprint §12 + infos.md §4 | brainstorm2 promises "preuves mathématiques des failles"; infos cites Rice; blueprint §12 limits claims to 4 buckets. | Blueprint + honesty rule win. No mathematical-proof claim in the product. |
| 3 | `brainstorm2.md` vs blueprint §1 | brainstorm2 frames as "anti-slop"; blueprint frames as "AI code verifier / OIDA Code Audit". | Blueprint wins. Anti-slop framing banned everywhere in the code and docs. |
| 4 | `brainstorm2_improved.md` vs blueprint §13 | brainstorm2_improved has 6 phases (Phase 0 → 5); blueprint has 10 concrete days. | Blueprint day-by-day schedule wins; brainstorm2_improved kept as conceptual index. |
| 5 | `brainstorm2_improved.md` vs paper + vendored `analyzer.py` | brainstorm2_improved proposes `V_net = Q_obs − μ − λ − traj_error + proof_gain`; paper + vendored use `V_net = V_dur − H_sys`. | Paper + vendored formula authoritative. The Explore/Exploit-augmented formula is a phase-2+ proposal, NOT implemented. |
| 6 | Blueprint §5 Pydantic-ish JSON vs vendored `@dataclass(slots=True)` | Two incompatible Python model styles for the same scorer surface. | Pydantic v2 at the public boundary (`oida_code.models`), dataclasses in the vendored core (`_vendor/`). A mapper (phase 2) bridges them. ADR-07. |
| 7 | Blueprint §7 single-file `score/analyzer.py` vs vendored package of 4 files | §7 tree lists one file; the upstream is a 5-module package. | Physical layout = vendored directory mirror; `score/analyzer.py` is a shim re-exporting the public surface. ADR-02. |
| 8 | Prompt Step 2 "Typer or Click" vs vendored `argparse` | Two different CLI frameworks. | New CLI = Typer; vendored `oida` CLI not re-exposed, stays argparse internally. ADR-06. |
| 9 | Brainstorm2 timestamp "23 avril 2026" vs formalism markdown "5 avril 2026" vs paper PDF "5 April 2026" | Different creation dates. | Consistent timeline (no actual conflict). Project "today" = 2026-04-24. |

---

## 6. Open questions

### Blocking (require user decision before phase 2)

**None.** The 3 blocking questions from the Step-0 digest were resolved by the user's carte-blanche ("comme tu veux"):

- Vendoring strategy → ADR-02 (vendor-mirror layout).
- Gate-4 smoke target → ADR-08 (empty-diff acceptance).
- CLI framework → ADR-06 (Typer).

### Nice-to-have (deferrable to phase 2)

1. **PyPI release cadence.** Should `oida-code` be published to PyPI before phase 2 ends, or only after the `audit` subcommand is real? Currently installable only via `pip install git+https://github.com/yannabadie/oida-code`.
2. **`.gitattributes` for LF enforcement.** Windows `core.autocrlf` is triggering LF→CRLF warnings on every commit; a `.gitattributes` with `* text=auto eol=lf` for `.py`/`.md`/`.json`/`.toml` would stabilize SHA across Windows/Unix clones. Not required for phase-1 correctness.
3. **`oida-code inspect` semantics on ignored files.** Currently passes through `git diff --name-only` output which already respects `.gitignore`. Explicit handling (e.g., `--include-ignored`) is a phase-2 flag if users ask for it.
4. **Coverage floor in CI.** Phase 1 hit 74 % but has no CI to enforce it. A GitHub Action running `pytest --cov --cov-fail-under=70` would prevent regressions in phase 2.
5. **Deprecation warnings from Typer 0.24.** 32 `DeprecationWarning: The 'is_flag' and 'flag_value' parameters are not supported by Typer` surface in test output even after I removed `is_flag=True`. Source is internal to Typer's `params.py:946`; harmless for us. Monitor for Typer 0.25+.

---

## 7. Honest self-critique — defensible vs placeholder

### What is defensible

- **Vendored OIDA core (`src/oida_code/_vendor/oida_framework/`).** Byte-identical to upstream under `search/OIDA/oida_framework/oida/`, SHA256 pinned in `VENDORED_FROM.txt`. The test `test_safe_online_migration_is_clean` validates that `safe_online_migration` yields the paper's §7.1 signature (debt = 0, V_net > 0, 0 corrupt-success). That's a real regression guard on the formulas.
- **Pydantic models (`models/*.py`).** Three models with strict `extra="forbid"`, bounds on unit-interval floats, `weight > 0` on preconditions. Deterministic serialization proven by `test_audit_request_roundtrip` / `test_audit_report_roundtrip`. 100 % line coverage. These will not silently accept malformed input.
- **`inspect` CLI end-to-end.** Reads HEAD + base SHAs via `git rev-parse`, computes changed files via `git diff --name-only`, emits a valid `AuditRequest` on stdout or `--out`. Subprocess is argv-form, no shell, 30 s timeout. `test_inspect_emits_valid_audit_request` runs it against the repo itself and re-validates with Pydantic.
- **Quality gates.** ruff + mypy-strict + pytest + coverage all green. None of these rely on mock data or skipped tests.
- **Memory bank.** All 6 files contain real content (not templates), with the 9 ADRs the plan required (5 explicit + 4 from implementation). Timestamp format matches the chatmode protocol.
- **Secret hygiene.** `.env` ignored before first `git add`; verified via `git check-ignore -v .env` and a final `grep -iE '\.env$|secret|credential|\.key$'` on the staged file list. Zero credentials leaked into any commit, memory-bank file, or report.

### What is placeholder (and I should not pretend otherwise)

- **Every module under `extract/`, `verify/`, `llm/`, `report/`, `github/`, plus `score/mapper.py` and `score/verdict.py`, plus `ingest/manifest.detect_commands`.** These are `NotImplementedError` with phase pointers. They are honest scaffolds, but until phase 2 wires real logic, invoking any of them at runtime yields an error. That's the point (blueprint "honesty over progress") — but it means the package's *declared* surface is much larger than its *working* surface.
- **`oida-code inspect`'s language detection.** Hardcoded to `"python"`. Real manifest auto-detection is phase 2. A Ruby or Go repo run through `inspect` today still gets `"language": "python"` — technically wrong but not dangerous because nothing downstream consumes the field yet.
- **`oida-code inspect`'s `commands`.** Hardcoded Python defaults (`ruff check . / mypy . / pytest -q`). A repo that uses `pylint` or `pdm run` will get wrong commands. Again, nothing consumes them yet.
- **`AuditRequest.policy`.** Defaults to `max_critical_findings=0, min_mutation_score=0.0, min_property_checks=0` — placeholders. Real policy surfaces once `verify/` and `score/verdict.py` exist.
- **`NormalizedScenario` round-trip is dict-equivalent, not byte-for-byte.** Because the source example has int weights (`2` vs my model's `float`) and omits the optional `config:` block. A phase-2 custom serializer (or field validator that preserves numeric form) could fix it, but this phase doesn't need it.
- **Typer + deprecation warnings.** 32 `is_flag`-related warnings from Typer 0.24's internals surface in test output. They don't affect correctness, but they pollute CI logs if a future `-W error::DeprecationWarning` pytest flag is added.
- **CRLF warnings on every commit.** Windows `core.autocrlf` noise. Didn't block commits but would if stricter hooks land.
- **No CI yet.** Gates ran on my machine only. A GitHub Action rerunning them on push is a phase-2 must (blueprint §13 day 10 demo wants a stable baseline).
- **I did not do the "demo on 10 intentionally sloppy PRs" exercise** (blueprint §13 day 10). That's explicitly phase-1-plus, and honesty demands saying it wasn't attempted. Phase 2 should prioritize it over tuning thresholds.

### One-line verdict

Phase 1 is a defensible CLI + typed I/O surface + vendored scorer, with honest scaffolds for everything else. **It is scaffolding, not product.** The wedge (corrupt-success detection on real PRs) lives in phase 2.

---

## 8. Stop and wait

Per `prompt.md` Step 5: **"Do not start phase 2 (Semgrep, Hypothesis, LLM verifier) without my explicit 'go phase 2' in chat."**

Phase 1 closed. Awaiting review.
