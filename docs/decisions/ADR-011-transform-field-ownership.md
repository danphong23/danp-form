# ADR-011 — Patch ownership uses control transforms

**Status:** Accepted for the deformation upgrade, 2026-09-19

## Decision

An enabled Source patch is controlled by the enabled control definitions incident
to its boundary. A patch with one incident control receives that control's
operation transform over its full captured scope. A patch with multiple incident
controls blends their transforms within the patch. The operation boundary is the
union of the initial explicit selection and every Controller vertex whose
coordinates actually change. Selected-but-unchanged vertices retain exact Operation
Rest targets but remain part of that boundary. Enabled controls outside it provide
identity and are hard stationary constraints; unselected vertices moved by Blender
Proportional Editing are exact targets. Hidden controls are not incident controls.

The canonical operation representation is shared by Blender UI and agents:
operation type, pivot, coordinate space, absolute targets and proportional
settings. A target mapping may represent an arbitrary free deformation, but it
must not silently change the ownership rules above.

## Consequences

- Translation, rotation and scale use the same patch-local ownership semantics.
- A single control no longer loses rotation or scale through averaging its
  boundary displacement vectors.
- Names, list order and logical grouping remain selection/storage conveniences;
  the effective Source IDs and patch incidence determine geometry.
- Patches outside the captured incident scope remain unchanged and are never
  written back.
- Evaluated modifier bleed is measured separately from the Source-base contract;
  a modifier-aware boundary policy requires separate evidence.

The transform fit is a replaceable numerical candidate. It must pass the exact
target, stationary-boundary, scope, cancel and parity gates before release.
