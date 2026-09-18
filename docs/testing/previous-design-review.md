# Review of the Previous Documentation

**Status: Audit**

The previous DAN Form documentation contained several strong architectural decisions but over-specified the numerical solver before the simplest product behavior had been validated.

## Keep

- Source Mesh as the geometric source of truth.
- Separate rebuildable Control Proxy.
- Persistent Source element IDs and Source-owned Control Definitions.
- Topology-derived patches; open chains only cut when connectivity really disconnects.
- Current Source at operation start as immutable Operation Rest.
- Exact cancel and one-commit/one-undo semantics.
- Multi-template identity/context handling.
- Human and AI using the same primitives.
- Reference fitting producing control targets only.

## Rewrite

- **Control selection:** distinguish node, Source span, and whole-control selection; define partial-line behavior explicitly.
- **Sparse controls:** spans explicitly select dense Source paths; knot-only edits leave omitted enabled vertices fixed. The previous automatic neighbor expansion is superseded by ADR-008.
- **Deformation:** describe required geometry behavior first, then a simple prototype interpolation.
- **Hide/reveal:** canonical whole/partial masks release constraints/cuts; reveal samples current mesh. Display-only hiding and separate deactivation are superseded.
- **Proportional:** apply once to patch propagation instead of mixing user falloff with multiple solver stages.
- **Testing/roadmap:** validate geometry behavior before performance/production claims.

## Remove from core

The following are no longer mandatory core architecture:

- harmonic vector fields;
- ARAP/similarity-ARAP;
- SVD;
- PCG;
- a required multi-stage “base field + shape-preserving relaxation” pipeline;
- a required NumPy/native numerical backend;
- solver-family-specific caches and numerical thresholds;
- claims that the design is production-ready before behavior prototypes pass.

They may return only as evidence-driven experiments.

## Move to extensions

- detailed reference-image fitting;
- collision/volume preservation;
- advanced interpolation/shape-preservation methods;
- aggressive performance acceleration;
- automated AI fitting strategies beyond the shared core API.
