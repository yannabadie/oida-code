# Calibration seed expansion protocol

This protocol governs G-6d corpus expansion after ADR-69. It was authored
as ADR-70 before G-6d.1. The baseline counts below are therefore historical
pre-G-6d.1 counts; the live corpus after ADR-72 is N=14 (10 train + 4
holdout). The protocol still governs future pinning tranches so larger-N
work does not dilute the lane separation, holdout discipline, or
replay-review hard walls already established.

## ADR-70 baseline state

At ADR-70 time, the calibration seed index had 46 inclusion records. Six
were pinned: four train cases and two holdout cases. The holdout ratio was
0.33.

G-6d remains open because N=14 is still too thin for any broad cross-target
claim. The target for the next larger-N milestone is at least 20 pinned cases while
keeping holdout ratio inside the existing 0.20 to 0.40 band.

## G-6d.0 scope

G-6d.0 is planning and instrumentation only:

- read `reports/calibration_seed/index.json`;
- report the current pinned/train/holdout/unpinned counts;
- define the first pinning tranche;
- codify the authoring checklist that folds G-6c into G-6d;
- keep G-6d open.

G-6d.0 must not:

- add or edit seed records;
- change `partition` or `partition_pinned_at`;
- generate new replay bundles;
- create `round_trip_outputs`;
- call providers;
- require `PAT_GITHUB`;
- touch runtime code under `src/oida_code/`;
- claim product safety, predictive validity, broad generalisation, or future
  replay correctness.

## Historical first empirical tranche

The first empirical block was G-6d.1:

- pin four new cases from the existing 46-case index;
- split them as three train and one holdout;
- move from N=6 to N=10;
- move from holdout=2 to holdout=3;
- keep the holdout ratio at 0.30.

The full G-6d target from the ADR-70 baseline was +14 new pinned cases:

- +10 train;
- +4 holdout;
- resulting N=20;
- resulting holdout=6;
- resulting holdout ratio 0.30.

After ADR-72, the live corpus is N=14 and at least 6 more pins are still
needed to reach N=20. Fresh GitHub harvesting is not part of G-6d.0,
G-6d.1, or G-6d.2. If the remaining existing unpinned records cannot
supply enough high-quality cases, harvesting becomes a separate later block
with its own consultation and report.

## Candidate policy

Use the existing `reports/calibration_seed/index.json` pool first.

Accept a candidate only when all of these hold:

- `public_only` is true;
- `merge_status` is `merged`;
- `repo_url`, `pr_number`, `base_sha`, and `head_sha` are present;
- the diff is inspectable without private data;
- the claim can be expressed as a narrow `claim_id`, `claim_type`, and
  `claim_text`;
- the `test_scope` is narrow and runnable in the target checkout;
- `evidence_items` include at least one implementation or diff fact;
- `evidence_items` include at least one test-result or runnable-scope fact;
- the partition is frozen before outcome inspection.

Reject or defer a candidate when it is release-prep-only, dependency-only,
formatting-only, generated-heavy, non-Python-adapter-dependent, over-broad in
test scope, dependent on PR comments for the claim, or likely to require a
clone-helper carve-out.

Diversity across repos and claim types is useful, but evidence quality and
runnable scoped tests are the first-order gates.

## Replay review inheritance

Any future LLM-authored replay set generated from newly pinned cases inherits:

- ADR-68 static replay-content audit;
- ADR-69 manual semantic review against non-LLM upstream diff/test evidence.

Provider output can assist authoring, but it is not non-LLM evidence.

## Stop conditions

Stop the block and consult again if the work starts pinning cases, changing
partitions, generating replays, widening clone-helper flags, requiring fresh
GitHub harvesting, using provider judgment as evidence, or implying that
G-6d closes from protocol text alone.
