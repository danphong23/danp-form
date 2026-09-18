# Blender Integration

**Status: Implementation guidance; no production code yet**

DAN Form can be implemented as a normal Blender Extension using Python APIs for mesh access, BMesh, PropertyGroups/attributes, modal operators, overlays, and keymaps.

## Mode policy

- Create controls from Source Edit Mode.
- Manipulate controls through the Control Proxy or a dedicated DAN Form tool in the 3D View.
- Source remains visible as the actual result.

Controller is a child object of Source, using the same local geometric frame. Move,
rotate or scale Source object carries controller exactly once. This is object
parenting, not nested controls. Phase 2 provides Source-to-controller coordinate
display refresh; reverse interaction is added in phase 4 through DAN Form targets
and transaction writeback, not uncontrolled two-way sync.

Phase 3 patch visualization is an overlay. Toggling it must not hide/exclude Source
geometry from core or change network masks/partition. Phase 4 must route controller
Edit Mode G/R/S through owned DAN Form operations; native Blender transforms alone
are not assumed to provide immutable-rest preview/cancel/undo semantics.

## Mesh access

When Source is in Edit Mode, implementation must use the edit-mesh/BMesh pathway rather than assuming `obj.data` coordinates are current. Object-mode operations may use standard mesh updates.

## Downstream modifiers

Core edits base Source coordinates. Subdivision/Armature/etc. may evaluate afterward. A modifier that radically changes displayed topology can make the visual proxy differ from evaluated geometry; core mapping remains against the base Source.

## Unsupported/uncertain Blender features

Shape Keys, Multires, non-manifold corner cases, and linked read-only data should be explicitly tested before claiming support. They are not reasons to complicate the first interpolation prototype.

Prototype default: reject Shape Keys, Multires, non-manifold topology,
read-only linked data and shared editable meshes before writes, with an explicit
UNSUPPORTED_FEATURE/SOURCE_NOT_EDITABLE. This is not a permanent product ban. Do not
apply/remove modifiers, copy data or make it local automatically to start an operation.

Mapping is against Source-local base geometry, not evaluated subdivisions/poses.
Capture object transforms for target conversion; reject singular matrices. Solve into
plain buffers, validate, then update mesh/BMesh through the correct mode path. Do not
deform numerically in depsgraph handlers. Version/platform packaging remains a release
test item; record the actual Blender version rather than claim untested compatibility.
