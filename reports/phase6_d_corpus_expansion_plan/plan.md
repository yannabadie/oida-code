# Phase 6.d.0 corpus expansion plan

This is a planning and instrumentation artifact only. It does not add
new pinned cases, change train/holdout partitions, generate replay
sets, call providers, call GitHub, or touch the runtime path.

## Scope

- Phase: `G-6d.0`
- Pins added: `0`
- Partition changes: `0`
- Provider calls required: `False`
- PAT_GITHUB required: `False`
- Runtime path changed: `False`

## Current corpus

- Source index: `reports/calibration_seed/index.json`
- Candidate pool count: `46`
- Pinned count: `6`
- Train count: `4`
- Holdout count: `2`
- Unpinned count: `40`
- Holdout ratio: `0.33`

## Target

- Minimum pinned count before larger-N claims: `20`
- Required additions from current state: `14`
- Allowed holdout ratio: `0.20` to `0.40`
- Full target recommendation: `+10` train / `+4` holdout, ending at `20` pinned cases and `0.30` holdout ratio.

## Next empirical tranche

- Phase: `G-6d.1`
- New pins: `4`
- Split: `3` train / `1` holdout
- Resulting pinned count: `10`
- Resulting holdout ratio: `0.30`

## Candidate policy

- Primary pool: `reports/calibration_seed/index.json existing 46 inclusions`
- Fresh GitHub harvesting: `defer_to_separate_block_if_needed`
- Candidate diversity is secondary to evidence quality and scoped-test quality.
- See `docs/calibration_seed_expansion_protocol.md` and
  `docs/calibration_seed_authoring_checklist.md` before any future pin.

## Backlog status

- G-6d after this plan: `open`
- G-6d.0 after this plan: `complete_after_this_plan_only`
- G-6c after this plan: `partially_addressed_until_checklist_is_exercised`
- Next block: G-6d.1 pin 4 new cases from existing index, split 3 train / 1 holdout, then clone and scoped-pytest feasibility.

Future LLM-authored replay sets inherit ADR-68 static audit and
ADR-69 manual semantic review before replay content carries
claim-supporting weight. Provider output is not non-LLM evidence.

G-6d remains open after G-6d.0; this artifact only closes the
planning/instrumentation sub-block.
