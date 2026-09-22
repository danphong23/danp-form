# ADR-013 — Keep selection intent separate from measured movement

**Status:** Accepted for implementation, 2026-09-23

## Context

Blender reports live Controller coordinates. Proportional Editing can move
unselected vertices, while an axis Scale can leave some selected vertices at
their original coordinates. Treating only changed IDs as the transforming
boundary makes those unchanged selected vertices look like a second stationary
control, even though they were part of the same native operation.

## Decision

Capture two operation-local sets:

- `selection_intent`: enabled Source IDs selected when the native transform begins;
- `moved_targets`: every Controller ID whose measured coordinate differs from its
  captured Controller rest, including unselected Proportional motion.

The transforming boundary is their union. Actual moved IDs use their measured
Controller coordinates as exact targets. Selected IDs not moved by Blender retain
exact P0 coordinates, but do not count as an independent stationary-control
boundary. Enabled control IDs outside the union remain exact stationary anchors.
Hidden geometry contributes to neither set nor stationary constraints.

All preview samples still solve from immutable P0. A no-op produces P0 exactly.
The rule applies to every mesh and transform axis; it does not inspect control
names, object names or anatomical regions. The same intent/target inputs go through
the shared deformation path for native and agent operations.

## Consequences

- A selected loop scaled along one axis remains one transforming boundary even
  where some loop vertices lie on the pivot axis and do not move.
- Unselected vertices moved by Blender Proportional Editing remain exact targets.
- A separate enabled unselected control remains a stationary anchor.
- Multiple controls still share one position per Source ID; conflicting moved
  targets remain an error.

## Verification

Core regressions cover a planar ring under X/Y/Z non-uniform Scale, unchanged
selected samples, Proportional moved vertices, a second stationary control,
repeated previews, cancel and immediate consecutive transforms. Blender live
verification checks Controller/Source/overlay agreement without saving the
user's scene.
