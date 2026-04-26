# Case `tool_needed_then_supported`

**Family:** gateway_grounded.
**Expected delta:** `improves` — gateway-grounded run cites a
fresh `[E.tool_output.0]` ref while the baseline accepts the
claim purely on event evidence.

## Discriminator

* **baseline:** forward supports `C.cap` citing only
  `[E.event.1]`; backward says necessary conditions met; the
  aggregator accepts.
* **gateway pass-1:** forward returns no claims and one
  `requested_tools` entry asking for pytest scoped to `tests`.
* **tool phase:** the gateway runs the pytest adapter against
  the canned `executor.json` (`returncode=0`, stdout `"=====
  5 passed in 0.4s ====="`). The pytest adapter's positive
  branch fires (`returncode==0 and not findings and stdout.strip()`)
  and emits a single `EvidenceItem(id="[E.tool_output.0]",
  kind="test_result")`.
* **gateway pass-2:** forward supports `C.cap` citing both
  `[E.event.1]` and `[E.tool_output.0]`; backward says
  necessary conditions met; the aggregator accepts.

## Why the labels match `improves`

Both modes accept the claim, BUT only the gateway run carries
a citation to the fresh tool ref. The runner's
`fresh_tool_ref_citation_rate` is:

* baseline: 0 / 1 = 0.0
* gateway:  1 / 1 = 1.0

The delta is unambiguously positive, hence
`expected_delta="improves"`.

## What this does NOT prove

This case shows the gateway can _surface_ a tool citation
when forward asks for one. It does NOT show the gateway
catches a regression that baseline accepted incorrectly —
that's `tool_failed_contradicts_claim`'s job.
