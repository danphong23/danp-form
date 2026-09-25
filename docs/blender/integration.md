# Blender Integration

**Status: Current DANP Form integration contract**

DANP Form can be implemented as a normal Blender Extension using Python APIs for mesh access, BMesh, PropertyGroups/attributes, modal operators, overlays, and keymaps.

## Mode policy

- Create controls from Source Edit Mode.
- Manipulate controls through the Control Proxy or a dedicated DANP Form tool in the 3D View.
- Source remains visible as the actual result.

Controller is a child object of Source, using the same local geometric frame. Move,
rotate or scale Source object carries controller exactly once. This is object
parenting, not nested controls. Phase 2 provides Source-to-controller coordinate
display refresh; reverse interaction is added in phase 4 through DANP Form targets
and transaction writeback, not uncontrolled two-way sync.

Phase 3 patch visualization is an overlay. Toggling it must not hide/exclude Source
geometry from core or change network masks/partition. Phase 4 must route controller
Edit Mode G/R/S through owned DANP Form operations; native Blender transforms alone
are not assumed to provide immutable-rest preview/cancel/undo semantics.

## Mesh access

When Source is in Edit Mode, implementation must account for the live edit-mesh/BMesh
state rather than assuming `obj.data` coordinates are current. For Shape Keys,
it must also verify that the BMesh layer belongs to the **captured target**;
an explicitly requested different key must never silently resolve through the
active edit layer. H02 owns this adapter and its Undo regression tests.

## Downstream modifiers

Core edits the captured Source base/Basis/Shape Key coordinates under ADR-015.
Subdivision/Armature/etc. may evaluate
afterward. An unapplied modifier never becomes the control mapping: the proxy
continues to follow base Source IDs while the overlay may use evaluated cage
geometry. Applying a modifier is treated as a normal Source topology/coordinate
edit. If the base topology fingerprint changes, DANP pauses and reports a
recovery action; it does not write stale IDs. Undo can restore the old mapping,
or Reset DANP can create a new mapping on the current mesh in one undoable step.

## Unsupported/uncertain Blender features

Shape Keys are governed by [ADR-015](../decisions/ADR-015-shape-key-edit-target.md),
with H01/H02 safety work pending. They are no longer a blanket unsupported
prototype case. Multires, non-manifold corner cases, linked read-only data and
shared editable meshes still need dedicated evidence or explicit rejection
before writes. Do not apply/remove modifiers, copy data or make it local
automatically to start an operation.

Mapping is against Source-local persistent topology, not evaluated subdivisions/poses.
Capture object transforms for target conversion; reject singular matrices. Solve into
plain buffers, validate, then update mesh/BMesh through the correct mode path. Do not
deform numerically in depsgraph handlers. Version/platform packaging remains a release
test item; record the actual Blender version rather than claim untested compatibility.
