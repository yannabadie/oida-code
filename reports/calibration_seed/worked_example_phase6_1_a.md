# Worked example — `seed_008_pytest_dev_pytest_14407`

This document walks through one calibration-seed inclusion
record end-to-end. The goal is to teach how a public PR is
turned into the canonical schema, with the field-derivation
pedagogy split that ADR-54 enshrines.

The record is in [`index.json`](index.json) under
`case_id: "seed_008_pytest_dev_pytest_14407"`.

> **Backport caveat — read this first.** The PR being walked
> through is a maintainer-authored 9.0.x backport (PR #14407)
> of an upstream community-contributor PR (#14382). The diff is
> materially identical to #14382: the original semantic change
> was authored by the community contributor against `main`, then
> cherry-picked by pytest maintainers to `9.0.x`. We pin the
> backport rather than the original because the upstream PR
> comes from a fork and is filtered by the Phase 5.6 fork-PR
> fence. The pedagogy is honest about this: we are
> demonstrating the schema, not claiming authorship.
>
> This is also the reason both Phase 6.1'a inclusions are
> backports — see the README §"Selection-effect caveat" and
> §"Corpus state". Future Phase 6.1'c collection MUST seek
> non-backport non-release-prep cases.

## The PR in one paragraph

[PR #14407](https://github.com/pytest-dev/pytest/pull/14407)
on `pytest-dev/pytest` (9.0.x branch) backports a small bugfix:
pytest's CLI accepts `--version` (long flag) for showing the
version string via a fast-path that skips full plugin loading.
The `-V` short flag was historically not in that fast-path, so
running `pytest -V` would either error or trigger full plugin
loading depending on context. The fix adds `-V` to the
fast-path counter and parametrizes the existing test over both
flags. Three files: `changelog/14381.bugfix.rst` (1 line),
`src/_pytest/config/__init__.py` (5 added / 2 removed), and
`testing/test_helpconfig.py` (4 added / 3 removed). 15 lines
total.

## The diff that matters

Only the two `.py` files carry semantic content. The
`changelog` entry is metadata.

### `src/_pytest/config/__init__.py` (the production fix)

```diff
-    # Handle a single `--version` argument early to avoid
-    # starting up the entire pytest infrastructure.
+    # Handle a single `--version`/`-V` argument early to avoid
+    # starting up the entire pytest infrastructure.
     new_args = sys.argv[1:] if args is None else args
-    if isinstance(new_args, Sequence) and new_args.count("--version") == 1:
+    if (
+        isinstance(new_args, Sequence)
+        and (new_args.count("--version") + new_args.count("-V")) == 1
+    ):
         sys.stdout.write(f"pytest {__version__}\n")
         return ExitCode.OK
```

### `testing/test_helpconfig.py` (the test, parametrized)

```diff
-def test_version_less_verbose(pytester: Pytester) -> None:
-    """Single ``--version`` parameter should display only the
-    pytest version, without loading plugins (#13574)."""
+@pytest.mark.parametrize("flag", ["--version", "-V"])
+def test_version_less_verbose(pytester: Pytester, flag: str) -> None:
+    """Single ``--version`` or ``-V`` should display only the
+    pytest version, without loading plugins (#13574)."""
     pytester.makeconftest("print('This should not be printed')")
-    result = pytester.runpytest_subprocess("--version")
+    result = pytester.runpytest_subprocess(flag)
     assert result.ret == ExitCode.OK
     assert result.stdout.str().strip() == f"pytest {pytest.__version__}"
```

The test parametrization means a single test name covers both
flags. Pytest will execute the test twice with `flag="--version"`
and `flag="-V"`. The fix is grounded by the `flag="-V"` run.

## The schema mapping (ADR-54: three tiers)

Every field of the inclusion record falls into one of three
tiers. The teaching part of this worked example is to recognise
which tier each field is in — because the bundle authoring
helper (Phase 6.1'b) can automate the first two tiers but
cannot replace the third.

### Tier 1 — API-derived (mechanical, no judgment)

These fields come straight from the GitHub REST API. The
indexer fills them; no operator judgment is involved.

| Field | Value (this case) | API source |
|---|---|---|
| `repo_url` | `https://github.com/pytest-dev/pytest` | constructed from `--repo` |
| `pr_number` | 14407 | `pulls[].number` |
| `title` | "[PR #14382/d72943a5 backport][9.0.x] Fix `-V` to show version information" | `pulls[].title` |
| `base_sha` | `4afcd4906b9cf4468dc9ca8cf7c53126e190d008` | `pulls[].base.sha` |
| `head_sha` | `480809ae02a97344e68e52eb015e68b840f2e05c` | `pulls[].head.sha` |
| `changed_files_list` | `["changelog/...", "src/...", "testing/..."]` | `pulls[N]/files[].filename` |
| `labels_observed` | `[]` (none on this PR) | `pulls[].labels[].name` |
| `merge_status` | `"merged"` | derived from `pulls[].merged_at` non-null |
| `collected_at` | `"2026-04-28T20:53:16Z"` | system clock at indexer run |
| `script_version` | `"phase6_1_a_pre_v1"` | indexer constant |
| `public_only` | `true` | indexer asserts after `repos/{repo}.visibility=="public"` |
| `case_id` | `"seed_008_pytest_dev_pytest_14407"` | `seed_<seq>_<repo_slug>_<pr>` |

**Pedagogy:** these fields have no semantic ambiguity. Two
operators running the indexer with the same flags against the
same PR will produce byte-identical Tier 1 fields (modulo
`collected_at` and the `seq` counter). They are pure provenance.

### Tier 2 — allowlist-categorical (judgment, but Literal-constrained)

These fields require operator judgment but the answer is
constrained to a finite Literal allowlist. The bundle authoring
helper (Phase 6.1'b) can suggest values, but the operator must
confirm. There is no free-form text.

| Field | Value (this case) | Allowlist source |
|---|---|---|
| `expected_grounding_outcome` | `"evidence_present"` | 6 values per `schema.md` (evidence_present / evidence_absent / tool_missing / scope_invalid / ambiguous / not_run) |
| `label_source` | `"yann_manual_review"` | 5 values per `schema.md` |
| `selection_source` | `"manual"` | 4 values per `schema.md` |
| `claim_type` | `"repair_needed"` | 7 values per `LLMEvidencePacket.allowed_fields` Literal |
| `llm_assist_used` | `false` | boolean |
| `human_review_required` | `false` (case is reviewed) | boolean |

**Pedagogy:** Tier 2 fields have judgment AND constraint. The
operator picks one of the allowed values. A wrong pick is
catchable by schema validation (Pydantic Literal raises). The
helper can rank the most likely values; the operator confirms.

For `claim_type` specifically, the rationale for picking
`repair_needed` is:

* The change is labelled `bugfix` in the changelog
  (`14381.bugfix.rst` is the literal filename).
* The fix repairs a behavioural inconsistency (`--version`
  worked via fast-path, `-V` did not).
* The other 6 `LLMEvidencePacket.allowed_fields` values do not
  fit:
  * `capability_sufficient` — would imply post-fix the system
    has a NEW capability; this is repair, not new capability.
  * `benefit_aligned` — about goal alignment, not bug-fixing.
  * `observability_sufficient` — about logging / metrics.
  * `precondition_supported` — about preconditions for some
    operation; this is end-user CLI behaviour.
  * `negative_path_covered` — about adding a negative test;
    the fix is a positive-path repair.
  * `shadow_pressure_explained` — about shadow-fusion stress.

For `expected_grounding_outcome=evidence_present`, the
rationale is: running the test scope on `head_sha` produces
output that demonstrates the fix's effect — specifically, the
`flag="-V"` run of `test_version_less_verbose` exits OK and
prints the version string (matching the assertion). Output
exists, is observable, and supports the claim.

### Tier 3 — free-form domain reasoning (real teaching)

These fields cannot be inferred from the API or from a finite
allowlist. They require the operator to read the diff,
understand the context, and write a defensible narrative. This
is where the bundle authoring helper provides the LEAST value
and where human review is irreducible.

| Field | Value (this case) |
|---|---|
| `claim_id` | `"C.cli_version_flag.repair_needed"` |
| `claim_text` | (full paragraph — see `index.json`) |
| `test_scope` | `"testing/test_helpconfig.py::test_version_less_verbose"` |
| `candidate_reason` | (operator note — see `index.json`) |

**Pedagogy:**

* `claim_id` follows the `C.<surface>.<claim>` pattern from
  `docs/beta/beta_case_template.md`. The `<surface>` is the
  operator's domain framing — here `cli_version_flag` because
  the affected surface is the CLI's version flag handling. The
  `<claim>` is what the change demonstrates — here
  `repair_needed`. The id is human-chosen and stable across
  re-runs.
* `claim_text` is one paragraph that names the change, locates
  it in the codebase, states what the change does, and notes
  any provenance caveats (here: the backport relationship to
  #14382).
* `test_scope` is a pytest-runnable target. For parametrized
  tests it is the test name without the parameter (pytest will
  run all parametrizations). If the operator wants to ground a
  specific parametrization, they write
  `testing/test_helpconfig.py::test_version_less_verbose[-V]`.
  This case uses the unparametrized form because the claim is
  about the fix as a whole; the `-V` parametrization is the
  one that actually exercises the new code path, but
  `--version` continues to pass too (regression coverage).
* `candidate_reason` is the operator's narrative for why this
  case was selected (and, after manual review, why it was
  pinned). It records the operator's judgment chain.

## How to ground this case (Phase 6.1'd preview)

When the bundle generator (Phase 6.1'b) lands, it will be able
to emit a bundle for this case roughly like:

```
oida-code prepare-gateway-bundle \
    --repo https://github.com/pytest-dev/pytest \
    --base-sha 4afcd4906b9cf4468dc9ca8cf7c53126e190d008 \
    --head-sha 480809ae02a97344e68e52eb015e68b840f2e05c \
    --claim-id C.cli_version_flag.repair_needed \
    --claim-type repair_needed \
    --test-scope 'testing/test_helpconfig.py::test_version_less_verbose' \
    --out bundles/seed_008_pytest_dev_pytest_14407/
```

The bundle would contain (per the existing
`docs/beta/beta_case_template.md` shape):

* The `claim_id` + `claim_text` + `claim_type` mapping.
* The `base_sha`/`head_sha` checkout instruction.
* The `test_scope` invocation: `pytest -k test_version_less_verbose`.
* Expected output shape.

The Phase 6.1'd stress-test would then verify that the bundle
is well-formed and that running the verifier against it
produces `evidence_present`. The bundle-generation helper is
NOT in scope for Phase 6.1'a; this preview is forward guidance.

## What this worked example does NOT establish

* It does NOT establish that the `-V` fix is correct.
  Correctness is the upstream pytest team's call, not ours.
  We only test that the bundle authoring of this case is
  consistent with the schema.
* It does NOT establish that the bundle produces a useful
  diagnostic. That requires Phase 6.1'b + 6.1'd.
* It does NOT establish that `repair_needed` is the universally
  best categorical fit. Two reasonable operators might disagree
  between `repair_needed` and `negative_path_covered`. We pick
  one, document the rationale, and let Phase 6.1'd surface
  whether the framing held up.
* It does NOT count as external-human beta evidence. This is
  Yann-internal manual curation — the seed lane stays
  structurally separated from the human-beta lane.

## Cross-references

* Schema field-by-field: [`schema.md`](schema.md)
* Lane charter: [`README.md`](README.md)
* ADR-54 (this commit): `memory-bank/decisionLog.md`
* PR upstream: <https://github.com/pytest-dev/pytest/pull/14382>
* PR backport: <https://github.com/pytest-dev/pytest/pull/14407>
* Beta case template (legacy reference): `docs/beta/beta_case_template.md`
