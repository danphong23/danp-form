# ADR-012 — Native transform boundary and continuous affine patch fit

**Status: Accepted for implementation, 2026-09-22**

## Decision

Controller Edit remains Blender's native Edit Mode. DANP Form observes the
Controller's absolute coordinates against one immutable operation rest. A
runtime poll may schedule the observation, but it does not infer completion from
elapsed time, mouse quietness, or a fixed number of polls:

- while a `TRANSFORM_OT_*` operator is present in a Window's modal operator list,
  the transaction stays in Preview;
- when that modal operator has ended, the final absolute Controller pose is
  Confirmed;
- when Blender has restored the captured Controller pose `C0`, the transaction
  is Cancelled and Source is restored to `P0`.

The native operator state is the lifecycle boundary. Timer callbacks are only a
way to observe that state because Blender does not expose a separate add-on
callback for the completion of a built-in transform.

For a patch with no stationary boundary, coherent control samples use one
regularized affine fit. The samples determine the measured affine field; a
frame-derived prior supplies only underdetermined directions such as the normal
of a planar ring. If arbitrary proportional targets cannot be represented by a
single affine field, the constrained displacement solve is used so hard target
positions remain exact. This is a semantic distinction between a coherent
whole-control transform and per-vertex targets, not a leg- or axis-specific
special case. Patches with fixed boundaries retain the constrained displacement
solve.

## Consequences

- A second Scale starts from the previous committed Source pose even when it is
  issued immediately after the first one.
- Esc/RMB cancellation cannot be committed by a quiet timer tick.
- Non-uniform Scale on a planar control is represented as one affine field; the
  free patch does not jump between unrelated interpolation methods.
- The missing normal of a planar sample is deterministic and based on the
  measured control frame, not a leg-specific or axis-specific special case.
- Blender native transform input, axis locks, numeric entry and proportional
  selection remain owned by Blender.

## Verification required

The live integration gate must cover two consecutive Scale operations on the
same selection, immediate selection changes, Confirm, RMB/Esc, proportional
editing, Undo/Redo, and planar rings on both the cylinder and character mesh.
