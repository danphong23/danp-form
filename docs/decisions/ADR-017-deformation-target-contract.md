# ADR-017 — Deformation Target contract

**Status: Accepted for H01, 2026-09-25.** Refines [ADR-015](ADR-015-shape-key-edit-target.md);
does not replace its active-key behavior or its support for relative and absolute
Shape Keys. The [contract](../architecture/deformation-target-contract.md) and
[test matrix](../testing/deformation-target-matrix.md) are normative for H02–H06.

## Decision

The Source mesh owns topology, persistent vertex/edge IDs, control definitions,
masks and patch connectivity. A **Deformation Target** supplies one array of
Source-local coordinates for that same topology. It is either:

1. `BASE`: mesh vertices, only when the mesh has no Shape Key blocks; or
2. `KEY`: one actual KeyBlock, including Basis (the first block), selected by
   the Source object's active Shape Key index before an operation begins.

The editable base mesh underneath an existing Shape Key stack is not a second
user-selectable DANP target. Creating or removing keys is a separate structural
action, never a side effect of a transform. Relative and absolute key stacks
remain in scope. Both write the selected KeyBlock's stored coordinates; neither
implicitly edits other blocks or changes `use_relative`, key values, mute,
drivers, keyframes or absolute evaluation time.

The controller is a rebuildable input proxy. Its persistent membership and the
patch graph are shared by all targets. While idle, its displayed coordinates
mirror the Source's visible evaluated mesh, including Shape Key values, blends,
mute state and show-only-key display. This makes the Source's visible result the
only geometric truth for controller display. On entering Controller Edit, DANP
isolates the selected key through Blender's show-only-key display and resyncs
from that evaluated result. A transaction captures exactly one stored-coordinate
target and its immutable P0. Preview, confirm, cancel and Undo/Redo address that
captured target, never whichever key is active later.

## Identity and failure rule

A runtime transaction captures the Source mesh owner and the actual KeyBlock
identity (or `BASE`), plus name, index, key-stack mode, vertex count and
topology signature as guards. Name and index are diagnostics, **not** proof of
identity. A pointer/reference is valid only while its owning Blender data
survives in the current session; after Undo/reload, an adapter must re-resolve
from a proven identity or fail closed. A changed name, active key, lock state,
mode, owner, count or topology invalidates the active transaction before new
deformation writes. A key being deleted or replaced is never matched by name
alone. Internal rollback may bypass a newly set lock only after it proves the
original target and topology still exist; otherwise it stops without guessing.

Reset Model's Init snapshot is also target-specific. The current name-only
snapshot guard is not enough to distinguish a renamed/replaced key; H02 must
make provenance sufficient across save/reopen or refuse Reset when it cannot
prove the target. This contract does not mandate a particular persistence
field or Blender API mechanism.

## Adapter boundary

One Blender-side adapter resolves/validates a target and provides target-aware
coordinate read, write, snapshot and restoration in Object/Edit Mode. An
explicit historical target must never fall back to the active Edit BMesh layer.
If Blender cannot safely expose/write that specific layer in the current mode,
the adapter must take a controlled path that preserves context or reject the
write before mutation. The core solver receives IDs, connectivity, P0 and
targets; it does not branch on `BASE`, Basis, relative or absolute key mode.

The UI and agent use the same target resolution and transaction path. A key
selection command is allowed only while the Source has no active deformation;
it then resynchronizes the proxy from the new target. During Controller Edit,
Blender's show-only-key display may isolate the selected key; the previous
display state is restored on exit/error. It must not change key values/mute.

An explicit **New Shape Key** command (H05) starts from a copy of the selected
target's stored coordinates, not from the evaluated mix of other keys. If no
key stack exists, create Basis from the base mesh first, then the new key from
that same coordinate snapshot. The new key becomes active and the proxy is
resynchronized. Existing key coordinates, values, mute, drivers, keyframes,
`use_relative` and absolute evaluation time remain unchanged. For an absolute
stack, H05 must assign a non-conflicting frame without moving evaluation time;
if Blender cannot do so safely, it rejects the command before modifying the
stack. This is a structural command requiring idle state and compatible
topology, never an implicit transform side effect.

## Rejected alternatives and consequences

- **Relative-only first release:** rejected for H01 because ADR-015 already
  includes absolute keys and both modes have the same stored-coordinate
  contract. H02/H05 must test absolute mode; a failing gate blocks release
  rather than silently withdrawing support.
- **Separate controls or patch definitions for each key:** rejected because
  all targets share Source topology and persistent IDs.
- **Name/index as target identity, or use the current active key for Undo:**
  rejected because rename, reorder, replacement and mode changes could direct
  a write to the wrong coordinates.
- **Force key values to 1 and others to 0:** rejected; display isolation uses
  `show_only_shape_key` without altering animation state.

This decision creates no new data write in H01. H02 implements safe I/O,
visible evaluated Source-to-proxy synchronization and Reset/Undo provenance;
native Undo history stores scalar key identity and re-resolves the live target
before reading or writing. H05 completes target selection and New Shape Key UX;
H06 exposes equivalent agent operations. `Save As Shape Key`, automatic Basis
propagation, corrective drivers, multi-object transactions and topology
remapping remain outside this decision.
