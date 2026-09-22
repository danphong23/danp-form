# Operation Semantics

**Status: Normative**

## Capture

Validate editable Source, mapping and supported topology; sync proxy from current Source.
Resolve selection once and freeze enabled network, selected Source IDs, pivot/orientation,
topology fingerprint and network/proxy generations. One transaction owns a Source.

For native Controller Edit `G/R/S`, Blender owns the transform operator and its modal
input. DANP captures the first observed pre-transform Controller pose, then observes
the absolute Controller pose against that rest and writes the Source preview. A timer
may sample Blender's explicit `Window.modal_operators` state, but it is not a boundary:
the active native operator means Preview, its end means Confirm, and exact restoration
of the captured Controller pose means Cancel. There is one shared Confirm primitive;
no legacy macro or quiet-poll timeout creates a second history step.

Capture immutable P0 for every vertex in potential operation scope: all patches incident
to resolved selection, even when the initial transform is zero. Capture proxy start state
and enabled hard constraints. Never change coordinates outside this captured scope.

## Preview updates

Targets are absolute relative to operation start, not incremental transforms of preview.
From P0, resolve selected Q, fix other enabled vertices, identify nonzero targets and
compute affected patch output. Initialize the entire captured-scope output buffer to
P0 before inserting this update's results; validate before writing. This resets earlier
preview displacement when targets return to P0, radius shrinks or affected scope shrinks.

```text
P0 + target_1/settings_1 → preview_1
P0 + target_2/settings_2 → preview_2
P0 + unchanged targets  → P0, including every earlier previewed vertex
```

Resetting prior preview writes is cleanup within captured scope, not permission to deform
unrelated patches. Identity updates return NO_CHANGE and can keep a transaction open;
early-out may skip solving but must not skip resetting previous preview writes.

The core coordinate contract is Source-local. A WORLD-space operation must provide an
explicit Source-to-world matrix and is converted back before Source writeback; a request
without that matrix fails with `WORLD_SPACE_MATRIX_REQUIRED` rather than being guessed.

## Confirm/cancel

Confirm validates generations, targets and finite output, writes the accepted method,
syncs proxy and records one logical undo operation. Preview/final may refine free vertices
but share hard targets, masks, scope and P0. Next operation uses the committed result.

With unchanged topology/identity, cancel restores exact P0/proxy start state, releases
ownership and creates no meaningful undo entry. Confirm with a result identical to start
returns NO_CHANGE instead of claiming an edit. Update/commit/cancel after closure returns
OPERATION_CLOSED without writes.

The native observer may use a timer only to sample Blender's explicit modal operator state.
It must never commit or cancel from elapsed time, mouse quietness, or a fixed poll count.
While a `TRANSFORM_OT_*` modal operator is present, the transaction remains in Preview.
When that operator ends, the final absolute Controller pose is Confirmed; a Controller
pose restored to its captured C0 is Cancel. If a future native macro supplies an explicit
Finish step, it may call the same Confirm primitive, but the observer must not invent a
second operation boundary.

## Structural state/ownership

Hide/reveal, definition edits, rebuild and simplify/refine are separate operations with
zero deformation and their own undo semantics. Reject them during a transform with
OPERATION_BUSY: finish/cancel first. Freeze selection/network/proxy representation during
the transaction. Reject second ownership of the same Source; unexpected revision changes
invalidate the operation. Native proxy transforms bypassing DANP Form cannot commit mesh
deformation; resync from Source before the next valid operation.

## External edits and recovery

Coordinate-only Source edits outside transactions are valid; resample at the next boundary.
External coordinates/object-transform or mode-ownership changes during a transaction
invalidate it before another write; do not absorb them into P0. This ownership validation
is operation-local, not continuous scene polling.

Handled numerical errors with unchanged topology restore P0/proxy and cancel. If Source
identity/topology changes, stop stale-index writes. Restore only coordinates with proven
identity; a coordinate snapshot is not a topology rollback. Report TOPOLOGY_CHANGED or
OPERATION_STALE and block continuation. Source deletion and unhandled Blender crashes
cannot promise exact rollback; normal Blender recovery applies. No operation snapshot
becomes persistent authoritative template data.
