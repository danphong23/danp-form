# Open Decisions

**Status: Intentionally unresolved; do not silently freeze these during implementation**

1. **Default proportional setting.** Whole Patch vs a finite default radius, and which small set of falloff profiles should ship.
2. **Baseline quality threshold.** How much shear/detail change in rotation case G5 is acceptable before an advanced interpolation experiment is required.
3. **Simplify scope for the first public build.** Exact controls may ship before automatic simplify/refine if interaction remains usable.
4. **Simplify knot-selection heuristic.** Endpoints/junctions must remain, but the automatic choice of additional Source knots is not yet product behavior.
5. **Future non-manifold support.** Prototype rejects ambiguous/non-manifold cases. Expanding correctness beyond manifold surfaces needs dedicated evidence.
6. **Future Multires support.** Shape Key editing is settled by ADR-015. Multires support needs separate semantics/tests and is not required to start the core prototype.
7. **Interpolation candidate and quality.** Prototype numeric methods remain replaceable;
   compare proportional response/current patch form without changing settled constraints.

Settled by ADR-008: enabled unselected control vertices stay fixed, including sparse
omitted vertices; selected junctions move; whole/partial Hide releases cuts/constraints;
Reveal uses current Source positions. Logical grouping does not change deformation.
No parent/child controls, patch nesting or separate deactivate feature is planned.

Settled by ADR-009: five development phases; controller object parented to Source;
Source-to-proxy display sync in phase 2, deformation transaction in phase 4; patch
overlay toggles are display-only; phase 5 uses MCP and references without requiring
automatic image fitting. Object parenting does not mean nested control ownership.

Phase 1 records initial Blender support. Phase 2 chooses measured refresh routing.
Phase 4 resolves interpolation/default profiles and quality evidence; phase 5 reviews
workflow/release evidence. Optional sparse/auto-fit decisions do not block these phases.

Everything else that changes source-of-truth, patch derivation, operation rest, target expansion, proportional placement, or same-path human/AI behavior requires a new ADR.
