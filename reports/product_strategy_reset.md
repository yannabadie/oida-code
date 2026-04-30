# Product strategy reset

Date: 2026-04-30
ADR: 74
cgpro thread: `repo-product-vision-review`
cgpro conversation: `69f329be-0dd4-838f-8687-d68190f21e7d`

## Why this block exists

After ADR-73, the repo had a clear empirical next step (G-6d remains
open toward N>=20) but the product direction was getting harder to
read. `PLAN.md` still described a long-horizon verdict / fusion /
repair / GitHub App trajectory, while `docs/project_status.md`
correctly said the current product is diagnostic-only and blocks all
official verdict fields.

The user asked for cgpro to review the whole repo and define a clearer
vision. cgpro recommended pausing G-6d briefly to repair the product
compass and front door.

## What changed

- `docs/product_strategy.md` now defines the active product compass:
  diagnostic second opinion for Python reviewers.
- `README.md` points to product strategy before the phase ledger and
  states that the ledger is evidence history, not the active roadmap.
- `PLAN.md` is marked as historical/aspirational when it conflicts with
  current diagnostic-only status.
- `docs/project_status.md` points readers to `docs/product_strategy.md`
  for active product direction.
- `AGENTS.md` now reflects the post-ADR-73 state: head `b8bc2ad`,
  G-6a closed for the current replay set, G-6d open but paused until
  product reset plus dependency policy.
- `memory-bank/codexContext.md` now carries a 2026-04-30 override so
  older Claude/Codex capture details are not mistaken for current state.
- `src/oida_code/cli.py` help text no longer contains the Unicode arrow
  that crashed under the local Windows cp1252 console path.

## What did not change

- No corpus pins were added.
- No live calibration index changes were made.
- No replay output was generated.
- No runtime verifier, provider, gateway default, MCP path, GitHub
  Action behavior, or clone-helper flag changed.
- Official OIDA fusion fields remain blocked.

## Active vision

For the next 30 days, `oida-code` is a diagnostic second opinion for
Python reviewers. It should help a reviewer classify a named claim as:

- supported by executable evidence;
- contradicted by executable evidence;
- unsupported within the evidence gathered.

It must not become a merge decision, production-readiness claim, or
autonomous repair system.

## G-6d position

G-6d remains open and scientifically important. The live corpus remains
at N=14 after ADR-73, and the target remains N>=20.

The next empirical G-6d block must be preceded by a dependency-install
policy for projects whose test dependencies live in `requirements/*.txt`
or `tox.ini`. That policy must be decided before candidate selection,
not added as post-freeze rescue.

## Verification scope

This block should be verified with:

- product-strategy doc guards;
- CLI cp1252 help guard;
- focused CLI help subprocess check;
- existing G-6d stop guard if any G-6d status text is touched.
