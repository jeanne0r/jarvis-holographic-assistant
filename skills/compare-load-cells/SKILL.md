---
name: compare-load-cells
description: Compare explicit load-cell capacities and distinguish the current configuration from superseded claims, with source attribution.
---

Retrieve the current memory and its provenance before describing the configuration.
Treat an episode about similar equipment as an analogy, not evidence about this
equipment. If accepted sources disagree, report both and request resolution.

For explicit capacities in kilograms, apply the declarative `v2.json` procedure
through `memory_manager.skills.apply`. Compare every capacity; the number of
cells alone does not prove they are identical. Do not infer a complete scale’s
safe load by adding the cells’ capacities.

`v1.json` preserves a synthetic failed procedure for the regression benchmark.
Evaluate using `memory_manager.skills.evaluate`; the publication gate recomputes
the fixed cases and checks previously passing cases before producing a Git review
manifest. This example is experimental and is not installed in Hermes or Codex.
