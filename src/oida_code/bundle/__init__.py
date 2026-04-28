"""Phase 6.1'b (ADR-55) — gateway bundle skeleton generator.

Reads a Tier-3-complete inclusion record from
``reports/calibration_seed/index.json`` and produces an
8-file gateway bundle directory the verifier can consume.

The generator is **local composition only**:

* No network egress (no GitHub API call, no clone).
* No provider call (no LLM, no MCP runtime).
* No `MANUAL_EGRESS_SCRIPT` marker (this is not the manual
  data-acquisition lane — see ADR-53).

Per ADR-55, the four `pass*_*.json` files emitted by this
generator are minimal-schema-valid SKELETONS, not real verifier
output. The skeleton note lives in each stub's ``warnings``
array. The verify-grounded round-trip is deferred to
Phase 6.1'd, where it runs on real or operator-authored
replays.
"""

from oida_code.bundle.generator import (
    REQUIRED_TIER_3_FIELDS,
    BundleGenerationError,
    GeneratedBundle,
    generate_bundle,
)

__all__ = [
    "REQUIRED_TIER_3_FIELDS",
    "BundleGenerationError",
    "GeneratedBundle",
    "generate_bundle",
]
