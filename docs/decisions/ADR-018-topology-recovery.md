# ADR-018 — Explicit topology recovery

**Status: Accepted for H07, 2026-09-25.** This decision defines how DANP Form
recovers after a Source topology edit. It does not make arbitrary topology
changes transparent to the add-on.

## Decision

The Source mesh remains the only owner of topology, persistent IDs, control
definitions, masks, Shape Keys and coordinates. DANP captures a compact
topology snapshot when IDs are initialized or explicitly validated. It contains
the persistent vertex and edge IDs and face connectivity needed to distinguish
unambiguous additions from edits to a control's affected patch.

After the topology fingerprint changes, normal editing stays paused. An
explicit Validate action may report the proposed repair without changing mesh
data. An explicit Repair action may proceed only when all of these conditions
hold:

1. The saved topology snapshot exists and is valid.
2. Existing nonzero vertex and edge IDs remain unique. Duplicated or rewritten
   IDs are ambiguous and are never reassigned automatically.
3. Every ID referenced by a control or mask still exists.
4. All faces and boundary edges in patches incident to current controls retain
   their recorded connectivity, and new faces do not touch those patches.
5. New unassigned vertices/edges can receive monotonically increasing IDs
   without altering coordinates or Shape Key data.

Safe additions/removals outside protected control patches can be repaired.
Loop cuts, changed connectivity, lost control elements, duplicate IDs, legacy
files without a trustworthy snapshot, and other ambiguous cases return
`STALE_MAPPING`; they require Undo, manual repair, or Reset DANP. Successful
repair preserves definitions/masks, refreshes the fingerprint and snapshot,
invalidates caches, and rebuilds the Controller. Failed validation/repair must
not write mesh coordinates, IDs, control data, masks, or Shape Keys.

## Rationale and consequences

Persistent IDs survive index shifts but do not prove unchanged face adjacency.
Therefore DANP compares stored connectivity for the patches that its controls
can deform. It accepts only changes that cannot alter those patches. The saved
snapshot adds file size in exchange for making this decision reproducible after
save/reopen; corrupt or absent snapshots fail closed.

Topology changes that subdivide or replace faces inside an affected patch are
not auto-migrated, even if control IDs still exist. The patch solver's result
would otherwise change without enough identity information to promise the same
deformation. Reset is an explicit user choice that discards the old mapping.
