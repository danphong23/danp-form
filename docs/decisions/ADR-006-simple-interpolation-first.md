# ADR-006 — Test Simple Patch Deformation Before Advanced Methods

**Decision:** test a small current-shape/displacement candidate, proportional and enabled
hard constraints before choosing advanced numerical methods. The candidate in
core/interpolation-baseline.md is replaceable. Its predecessor's logical-component
weighting is superseded by ADR-008 grouping-independent Source geometry semantics.

**Reason:** prove the modeling behavior before freezing numerical complexity. No fixed
midpoint response or required harmonic/ARAP backend follows from product intent.
