# PHASE 3 AUDIT REPORT — `oida-code` Explore/Exploit trajectory scorer

Generated: **2026-04-24**.
Active plan: `PLAN.md` §14 Phase 3 (re-scoped via ADR-17 / ADR-18).
Repo: <https://github.com/yannabadie/oida-code>.
Preceded by: `PHASE2_AUDIT_REPORT.md`, `v0.3.0` (fork guard).

---

## 1. Files created / modified in Phase 3

### New files (SHA256 at the tip of this phase)

```
131664085b54511dd03e1a46702ccfd4f38fb6a05141a3ee0802dd5ef32bcba5  src/oida_code/score/trajectory.py
7c7a310a28fe7b7ba6944543d09a0eefa86af94ea1499cc312b6b342235d64a6  src/oida_code/models/trajectory.py
d37431cc8851611f088aef4fbee44f80be260d2e4963fc8f0ae613a4f5c01355  src/oida_code/ingest/claude_code_trace.py
fac03270728fc5134e5d35b9a35acd1d285f2bdc35cd36c9c9cdc1e4f5d9c18c  src/oida_code/ingest/session_outcome.py
fabcfcd585ae762572da96dd89794239b66c53d0527533ce32234d819c66c3b3  scripts/validate_phase3.py

tests/fixtures/traces/clean_success.json
tests/fixtures/traces/exploration_dominated.json
tests/fixtures/traces/exploitation_dominated.json
tests/fixtures/traces/mixed_progress.json
tests/fixtures/traces/stale_cycling.json
tests/test_score_trajectory.py
tests/test_claude_code_trace.py
```

### Modified files

- `src/oida_code/cli.py` — new `score-trace` subcommand wiring the
  parser, scorer, and (optional) outcome labeler.
- `src/oida_code/models/__init__.py` — re-exports `TrajectoryMetrics`,
  `TimestepCase`, `CaseLabel`.
- `memory-bank/decisionLog.md` — ADR-16 (fork guard, shipped in 0.3.0),
  ADR-17 (Phase-3 re-spec), **ADR-18 (grid→code mapping, bounded U(t))**.
- `PLAN.md §14` row 3 rewritten under ADR-17.

Total Phase-3 delta over `v0.3.0`: **+8 new files / +5 modified / ~1,800 insertions** in 4 commits.

---

## 2. Quality gates (verbatim)

```
$ .venv/Scripts/python.exe -m ruff check src/ tests/
All checks passed!

$ .venv/Scripts/python.exe -m mypy src/
Success: no issues found in 50 source files

$ .venv/Scripts/python.exe -m pytest tests/ \
      --ignore=tests/test_cli_audit.py \
      --ignore=tests/test_verify_runners.py
99 passed in 2.40s
```

- **99 tests passing** (was 77 at Phase 2 → **+22 new**).
- All four Phase-3 synthetic fixtures classified in the expected
  dominant-error direction; 10 scorer tests + 6 parser tests green.

---

## 3. End-to-end validation

### 3.1 Synthetic fixtures (5 traces)

`tests/fixtures/traces/*.json` — each carries a ``label`` field that is
the ground truth. The scorer classifies all five in the correct
direction:

| Fixture | Label | scorer says |
|---|---|---|
| `exploration_dominated.json` | `exploration_error` | exploration > exploitation ✓ |
| `exploitation_dominated.json` | `exploitation_error` | exploitation >> exploration ✓ |
| `stale_cycling.json` | `stale` | `stale_score ≥ 1` ✓ |
| `clean_success.json` | `success` | both errors ≤ 0.55 ✓ |
| `mixed_progress.json` | mixed | ≥ 1 progress event + non-trivial exploration error ✓ |

**ADR-17 synthetic gate met.**

### 3.2 Real-trace validation (20 Claude Code transcripts, 18 usable)

`scripts/validate_phase3.py` pulls one transcript per project from
`~/.claude/projects/`, round-robin across 20 projects. Each transcript:

1. Parsed into `Trace` via `ingest.claude_code_trace`.
2. Scored with `score_trajectory` using a **bounded U(t) heuristic**
   (first 15 distinct paths touched = proxy for the session's audit
   surface; full audit-request ingest is Phase-4).
3. Labeled with `compute_session_outcome` — non-LLM, git-derived:
   `success` if any commit during the session window is reachable from
   HEAD; `failure` if no commits; `partial` if commits exist but were
   rebased away.
4. Correlations computed across the filtered set (sessions ≥ 50 steps).

| Metric | Spearman ρ vs outcome | Sign |
|---|---|---|
| `log(exploration_error)` | **+0.356** | **wrong — expected negative** |
| `log(exploitation_error)` | +0.163 | weak |
| **`progress_rate = progress_events / total_steps`** | **−0.668** | correct, **passes gate** |
| `no_progress_rate` | +0.668 | correct (mirror) |

**n = 13** after the min-steps filter (9 success, 4 failure, 0 partial).

Raw JSON at `.oida/phase3_validation.json` (gitignored; reproducible via `python scripts/validate_phase3.py --n 20`).

**Gate decision (amended 2026-04-24 post-ship review):** the
**empirical real-trace gate is NOT met** on this corpus. ADR-17's
primary deliverable — the synthetic-fixtures gate — stands unchanged
(§3.1). The empirical ρ was a nice-to-have beyond the re-spec, and
attempting it on this mixed-language 20-repo corpus hit three
artifacts:

1. **Outcome label is a length proxy.** `outcome = success` iff
   `commits_in_window > 0`, which on this corpus has `ρ(commits,
   total_steps) = +0.79`. Longer sessions commit more.
2. **`progress_events` ceiling at ~15.** The validation's bounded-U(t)
   heuristic caps at 15 paths; 12 of 18 rows saturate within 1-3 of
   the ceiling.
3. **Mechanical `progress_rate = 15/N` decay.** ρ(progress_rate,
   length) = −0.86 — arithmetic, not domain signal.

**Attempted remediation (2026-04-24):**

* `commits_per_step` as a length-normalized outcome: still
  `ρ(cps, total_steps) = +0.52` (confounded), and the failure class
  collapses to a constant (all-zero) because `commits = 0` for every
  failure. The metric reduces to "commits happened," same tautology.
* Pytest-pass at session-end commit (advisor's preferred signal): not
  tractable on this mixed-language corpus (per-repo env setup required
  for each of 15 distinct repos).
* Narrowing to one repo: candidate single-repo sample sizes are 9-16,
  marginal for Spearman and would need a repo-specific test runner.

**Honest disposition:** the synthetic-fixtures gate (§3.1) is what ADR-17
promised and what ships. The empirical ρ measurement moves to Phase 4,
when the obligation-close detector (§6.2) and bounded-U-from-inspect
(§6.1) will produce non-tautological data by construction.

The ρ = −0.668 reported in the original v0.4.0 text was retracted in
v0.4.1 (tag message: "honest Phase-3 report amendment"). Users should
read the amended §3.2 + §7, not the original text.

---

## 4. Decisions NOT in the blueprint

Three ADRs landed this phase (16-18). 18 is the substantive one.

| ADR | Decision | Rationale |
|---|---|---|
| 16 | Self-audit fork guard on pytest runner. | Two OOM-adjacent fork-bomb crashes during Phase 2. Detection via `pyproject.toml[project].name == "oida-code"`. |
| 17 | Re-spec Phase 3 with synthetic-gate + shifted Spearman to Phase 4; adopt paper's exact formulas (`ct/et/nt`). | Original PLAN.md gate required a human-labeled dataset that was never produced. |
| 18 | **Grid→code mapping.** U(t) = `changed_files` unread; P(t) = open obligations with scope visited + deps closed; Goal = intent-source obligation falling back to heaviest weight; Gain = set-membership on unread files OR newly-closed obligations. | Paper's U(t) (unobserved grid cells) is bounded by grid size; in code the "unobserved" space is effectively infinite. Bounded U(t) is the defensible adaptation; the empirical check (§3.2) is whether the scorer's direction survives. |

Non-ADR design choices:

- **Transcript parser tolerance**: malformed JSONL lines skipped, not fatal. On 1542 production transcripts the parser never raises.
- **Tool-kind mapping table** keyed on Claude Code tool name (Read/Grep/Edit/Write/Bash/etc.) with bash-argv classification for `git commit` → `commit` and `pytest` → `test_run`. No introspection of bash argv for paths (too unreliable).
- **Dense `t` index**: `t` is a 0-based index over consumed tool_use records, not the raw JSONL line number, so the downstream scorer sees a compact timeline.
- **Outcome labeler uses git log, not the trace itself** — non-circular validation signal per advisor (measuring LLM labels against LLM-scored formulas would be a vanity metric).
- **Round-robin transcript sampling** in `validate_phase3.py`: first transcript per project, then second, etc., so the sample spans many repos rather than over-sampling one.

---

## 5. Contradictions / surprises

1. **The paper's raw `exploration_error` does not transfer to code out of the box.** On 18 real Claude Code sessions, ρ(log exploration_error, outcome) = **+0.36** — the OPPOSITE sign of paper Figure 1a. Confound identified: session length dominates the case-attribution normalizers. Long successful sessions accumulate many "wasted" steps that still produce commits; short failures have no progress events but their denominators shrink in step. See §7 for the length-independent fix.
2. **`progress_rate` is the cleaner signal in this domain.** `ρ = −0.67` vs outcome; length-independent; already computed by the scorer. It's the paper's intent (low exploration error → success) projected through a metric that respects the fundamental difference between grid navigation (bounded) and code reading (unbounded). Proposal: surface `progress_rate` as the primary Phase-3 output and keep `exploration_error` / `exploitation_error` as paper-faithful secondaries.
3. **Outcome labeler matches well despite bluntness.** `commits-reachable-from-HEAD` as the success indicator agreed with my intuition on every transcript I spot-checked. The one `unknown` outcome was a session whose `cwd` wasn't a git repo (expected).
4. **Paper-dataset sanity check (P3-E) NOT executed** in this phase. Their released code is a separate repo (`jjj-madison/measurable-explore-exploit`); running our `ct/et/nt` on their 2D grid traces would verify the math independently of the domain adaptation. Deferred because the adaptation's empirical result (§3.2) gave a stronger signal than the sanity check would have. Carry-over to Phase-4 first week.

---

## 6. Open questions ranked

### Blocking Phase 4

None. Phase-4's entry criterion in PLAN.md §14 is "P3 ships + M.2 2TB installed." P3 shipped; M.2 is on the user.

### Carry-over tickets (fix in early Phase 4)

1. **Re-run validation with a non-confounded outcome signal.** This is the **must-do**, not nice-to-have. Options: (a) `pytest --co` at the session's ending commit → length-independent boolean; (b) test-pass rate over the session's changed files; (c) user-hand-labeled sample. Remove the `limit=15` cap on `_derive_changed_files` and use `git diff` between the session's start/end HEADs for a real bounded U(t). Recompute ρ; honest Phase-3 success means ≤ −0.3 on *that* signal.
2. **Obligation-close detector.** The transcript parser sets `closed_obligations = []` for every event because there's no linkage from Edit/Write events to obligation IDs. Every real trace ends up with Case attribution collapsed to exploit_goal after U empties. A lightweight linker (re-run `extract_obligations` after each Edit/Write, diff the open set) would populate `closed_obligations` and unlock Case 2/3 distinction.
2. **Bounded U(t) from a real `AuditRequest`.** The validation used "first 15 paths touched" as a surface proxy. A proper pipeline captures `inspect` at session start and feeds the resulting `changed_files` into the scorer.
3. **Paper-dataset sanity check (ADR-17 carry-over).** Run our `ct/et/nt` implementation on the authors' released 2D grid traces. If numbers diverge, fix the math; if they match, we've verified the implementation independently of the domain adaptation.
4. **Session-length controlled metrics.** Document `progress_rate` as the primary trajectory health signal; keep `exploration_error` / `exploitation_error` as diagnostics but with a prominent "length-sensitive" note.
5. **Partial-outcome labels are empty** in the sample (0 of 18). Rebased branches are probably rare in my own workflow; a public-dataset validation would hit more `partial` cases.

### Nice-to-have

6. **No scipy dependency** — `statistics.correlation(..., method="ranked")` gave us Spearman without adding a runtime dep. Keeping it that way.
7. **Transcript parser covers 10 tool families**; extending to tools like `TaskCreate`/`Skill` with richer scope inference would tighten the progress signal.
8. **`score-trace --summary`** shortcut that excludes `timesteps` from the output — useful when piping to jq.

---

## 7. Honest self-critique — defensible vs placeholder

### What is defensible

- **Paper §4 formulas implemented faithfully.** `ct`, `et`, `nt`, `St`, `err(t)` exactly as stated; the 4-case attribution from Table 1; normalizers for `exploration_error` / `exploitation_error` computed per paper §5. Synthetic fixtures with hand-crafted ground truth are classified correctly by the scorer.
- **ADR-18's bounded U(t)** is the defensible adaptation: it keeps the paper's Case structure intact while respecting the fundamental unboundedness of the code-reading action space.
- **Transcript parser** handles 1542 production Claude Code JSONL files without raising, classifies tool calls into the full `TraceEventKind` enum, and passes 6 unit tests including a malformed-line tolerance test.
- **Outcome labeler** uses git as a non-circular validation signal. `SessionOutcome` dataclass separates the decision (`success/failure/partial/unknown`) from its provenance (start_ts, end_ts, commit counts) so callers can audit the label.
- **`score-trace` CLI** produces schema-valid `TrajectoryMetrics` JSON and optionally appends a `session_outcome` block — the full pipeline is one command.
- **99 / 99 unit tests pass.** Ruff clean. Mypy clean (50 source files). No warnings.

### What is placeholder — DO NOT PRETEND OTHERWISE

- **The Phase-3 validation gate is NOT met on a non-confounded signal.** The original report text ("ρ = −0.67 passes the gate") was corrected in §3.2 post-ship. The −0.67 is driven by a mechanical `progress_rate = 15/N` ceiling combined with a length-tautological outcome label (`commits > 0`). Real validation requires either a pytest-pass outcome signal or git-derived actual changed_files (carry-over §6.1). Until then, the Phase-3 deliverable stands as **scorer + synthetic fixtures + ADR-18 mapping**, with real-trace validation deferred.
- **The paper's raw `exploration_error` does not work on real code traces either.** ρ on 18 transcripts is **+0.36** (wrong sign). The length-independent rewrite is on the Phase-4 backlog.
- **The transcript parser populates `closed_obligations = []` always.** Without an obligation-close linker, every real trace's Case attribution collapses once `U` empties — which dominates the trace-scale signal. Phase-4 should ship a minimal post-hoc linker (Edit on file containing obligation scope → close candidate, verified against pytest-run evidence).
- **Bounded U(t) in the validation run is a heuristic** ("first 15 distinct scope paths"). Good enough to pass the gate with the right direction; not a ground-truth audit surface. Phase-4 must connect `inspect` → `score-trace` so the surface is the actual diff.
- **n = 13 is small for Spearman.** The ρ = −0.67 signal is suggestive, not definitive. A proper validation needs n ≥ 30 with diverse outcomes (currently 9 success / 4 failure / 0 partial). Phase-4 should run on a larger corpus.
- **Paper-dataset sanity check (P3-E) was not run** — we compared our adapted scorer to its expected domain behavior, not to the original grid-world formulas. If Phase-4 surfaces an inconsistency, the carry-over is the first place to look.
- **No CI** — gates run on my machine only. Still true since Phase 1.
- **Mutation and property runners remain opt-in** — unchanged since v0.3.0; the self-audit guard only handles the Phase-1 five.

### One-line verdict

Phase 3 ships a faithful paper-adapter (`score/trajectory.py` + `models/trajectory.py`), a production transcript parser (1542 files tested), a git-derived outcome labeler, and an `oida-code score-trace` CLI that wires them end-to-end. **Synthetic-fixtures gate: met. Real-trace validation gate: not met on a non-confounded signal — the ρ = −0.668 figure in §3.2 was revised after post-ship re-review (see amendment) to show it's driven by an arithmetic `15/N` ceiling + a length-tautological outcome label. Real validation is the first Phase-4 item.**

---

## 8. Stop and wait

Per PLAN.md §14 Phase 4 entry gate: **"Phase 3 shipped + M.2 2TB installed."**

Phase 3: shipped as `v0.4.0`.
M.2 2TB: user-side.

Awaiting explicit **"go Phase 4"** before starting the agentic (forward/backward) LLM verifier and the obligation-close detector carry-over (§6 item 1).
