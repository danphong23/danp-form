# ADR-015 — Edit the Active Source Shape Key

**Status: Accepted for implementation, 2026-09-24**

## Decision

DANP Form deformation reads and writes the active Shape Key on the Source mesh.
When the Source has no Shape Keys, it reads and writes the base mesh. The target is
captured at operation start and remains fixed for the full preview/commit/cancel
transaction. Controller geometry remains a rebuildable input proxy.

Only the active key is edited. Editing Basis does not automatically translate other
keys; any future propagate-to-keys command must be explicit and separately designed.
Locked keys reject new operations. A lock or target change during a native transform
cancels the preview and restores the original target coordinates.

When controller editing starts, the Source temporarily displays the active Shape Key
at full value using Blender's show-only-key setting; the previous display setting is
restored when the user returns to the Source or leaves Controller Edit Mode. Shape
Key values and mute settings are not changed.

Init snapshots record the target Shape Key name. Reset Model can restore that snapshot
only when the same target is active, preventing a Basis snapshot from being written to
an expression key. Shape Keys retain their Blender topology constraints; DANP Form
does not add, remove, or reorder shape-key points.

## Rationale

Blender's native Edit Mode edits the selected key's coordinate layer. DANP's Controller
is a separate mesh object, so Blender cannot infer which Source key to change. The
Source adapter must route reads, writes, proxy synchronization, overlays, preview
rollback, and native Undo/Redo through the captured active key.

## Consequences

- Shape Key support is part of the Blender mesh adapter and does not change the core
  deformation solver or persistent control IDs.
- Shape Key name/identity, lock state, coordinate count and relative/absolute mode
  participate in operation validity.
- Relative and absolute keys use the same active-coordinate write path. Basis
  propagation to other keys is intentionally not implicit.
- Blender integration must cover target changes, lock changes, cancel, undo/redo,
  display restoration, and a mesh with no Shape Keys.
