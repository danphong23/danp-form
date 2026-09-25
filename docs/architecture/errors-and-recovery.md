# Errors and Recovery

**Status: Normative behavior; code names may be refined before implementation**

Recommended stable statuses:

```text
OK
NO_CHANGE
INVALID_INPUT
OPERATION_BUSY
OPERATION_CLOSED
NO_ACTIVE_SOURCE
SOURCE_NOT_EDITABLE
UUID_CONFLICT
CONTROLLER_CONFLICT
SHARED_DATA
PROXY_MISSING
PROXY_CORRUPT
STALE_MAPPING (legacy diagnostic; translated to TOPOLOGY_CHANGED in the UI)
TOPOLOGY_CHANGED
CONTROL_HIDDEN
EMPTY_SELECTION
NO_MOVING_TARGET
TARGET_CONFLICT
NO_AFFECTED_PATCH
NON_FINITE_RESULT
OPERATION_STALE
UNSUPPORTED_FEATURE
SHAPE_KEY_TARGET_INVALID
SHAPE_KEY_TARGET_CHANGED
SHAPE_KEY_LOCKED
TARGET_PROVENANCE_UNKNOWN
```

Rules:

- mapping/proxy failure never writes Source;
- Source/Controller ownership is resolved through direct parentage, a single
  DANP-marked child, matching owner marker, unique identity among bound pairs,
  and single-user mesh data. UUID-only first-match lookup never grants ownership;
- a mesh-only duplicate remains unbound even if Blender copied its Source UUID.
  Initialize gives it a new UUID and clean definitions. A complete duplicate pair
  gets its own UUID while preserving its local controls/IDs. Ambiguous collisions
  fail before any Source or Controller write and expose a pair-resolution action;
- non-finite result with unchanged identity/topology restores P0/proxy and cancels; topology/deletion failures follow operation-semantics.md limits;
- missing proxy is recoverable by rebuild if Source definitions are valid;
- a Source topology change pauses DANP without writing stale IDs. Undo restores
  the previous mapping when Blender can restore the mesh. Reset DANP is the
  explicit repair path: it removes the old controller/definitions and creates
  a fresh mapping from the current Source topology in one undoable operation;
- an unapplied modifier does not redefine the mapping. The proxy stays backed
  by base Source IDs while the overlay may follow evaluated cage geometry. An
  Apply operation that changes base topology pauses DANP and uses the same Undo
  or Reset recovery path;
- Reset Model restores the coordinate snapshot captured by the first Init on the
  same topology. It is separate from Reset DANP and is itself undoable. If the
  topology no longer matches that snapshot, Undo or Reset DANP is required first;
- under [ADR-017](../decisions/ADR-017-deformation-target-contract.md), an
  explicit historical Shape Key write must prove the captured key's identity,
  not match only its name/index. Invalid/deleted target returns
  `SHAPE_KEY_TARGET_INVALID`; active target switch/rename returns
  `SHAPE_KEY_TARGET_CHANGED`; lock returns `SHAPE_KEY_LOCKED`; Reset/Undo with
  insufficient saved identity returns `TARGET_PROVENANCE_UNKNOWN`. Changed
  key-stack mode or coordinate count returns `OPERATION_STALE`. None permits
  a write to another key. Internal rollback after a newly locked key is allowed
  only with proven target and unchanged topology;
- user UI receives a short recovery-oriented message;
- agent receives a stable code plus machine-readable context.

NO_CHANGE is successful identity, not solver failure; clear prior preview writes too.
Invalid/busy/hidden/stale requests fail before new writes. An error during an existing
transaction cannot leave partial preview edits: recover/close according to operation
semantics. Report Source/element IDs and expected/actual revisions where available.

Rejecting a second/busy caller must not cancel or restore the legitimate owner's preview.
NO_MOVING_TARGET can be diagnostic context for successful NO_CHANGE, not a reason to
skip prior-preview cleanup. NO_AFFECTED_PATCH describes selected geometry with no faces.
