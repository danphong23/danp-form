# Deformation Target contract

**Status: Normative for H02–H06 under [ADR-017](../decisions/ADR-017-deformation-target-contract.md).**
This describes required behavior, not a claim that current code passes it.

## Target model

| Source state | Selectable target | Coordinate store | Display label |
| --- | --- | --- | --- |
| No Shape Key blocks | `BASE` | Source mesh vertices | Mesh gốc |
| Shape Key stack exists | `KEY(Basis)` | First KeyBlock coordinates | Basis |
| Relative key stack | `KEY(active)` | Active KeyBlock coordinates | Key name |
| Absolute key stack | `KEY(active)` | Active KeyBlock coordinates | Key name |

`BASE` and `KEY(Basis)` are distinct. DANP does not expose the hidden base mesh
as an additional target when key blocks exist. The Source mesh remains the
structural owner in every row: same persistent IDs, control membership, masks,
topology fingerprint and patch connectivity. Only coordinate P0/writeback
changes with target. No per-key control or patch copy is stored.

## Operation sequence and identity

```text
resolve Source/Controller + selected target
  → validate owner, topology, target, lock and mode
  → resync controller from target when idle
  → capture target descriptor + immutable P0
  → core computes each preview from P0
  → adapter writes only captured target
  → commit or restore captured target; resync controller
```

The target descriptor has `kind`, Source mesh owner identity, actual KeyBlock
identity when applicable, original name/index, key-stack mode, vertex count
and topology signature. The actual object identity is valid only for the live
session; persisted snapshot/Undo restoration needs independently proven
provenance. A name or index match alone never authorizes a write. No target
change is permitted during an active transaction. The adapter validates the
descriptor before each write, cancel and Undo/Redo restoration. Stale identity
must produce a stable error before mutation.

Explicit-target reads/writes, including Undo and Reset, must address the
descriptor's key even if Blender's currently active key differs. In Source Edit
Mode, the live BMesh is usable only if verified to represent that exact target;
otherwise use a controlled context-preserving route or reject before writes.
Internal rollback after a lock/change may use a narrowly scoped lock bypass
only if target and topology identity are still proven. No rollback by stale
array index or by a different active key.

## UI, agent and structural actions

The Source active key is the single user-visible selection state; DANP's panel
must show that same target. Choosing another key is a structural command:
require no active transform, change active key, validate it and resync controller
to its coordinates. Entering Controller Edit may temporarily enable
`show_only_shape_key`; leaving it or an error restores the prior setting.
Key values, mute, drivers, animation and absolute-key evaluation time remain
untouched. A locked key can be selected for inspection but cannot begin a new
deformation. New Shape Key belongs to H05, not to a transform. It copies the
currently selected target's **stored coordinates**, never evaluated mix. Without
keys, it creates Basis from base first and then the new key. It selects the new
key and resyncs the proxy while preserving existing keys and animation state.
For absolute stacks, it must choose a non-conflicting frame without changing
evaluation time, or fail before changing the stack. Blender topology constraints
still apply.

The H06 agent API may list/select targets and begin operations without mouse
simulation. It must return the same target identity, errors and coordinates as
the UI path. The core accepts only IDs, coordinates and operation settings.

## Existing implementation versus required adapter

| Current path | Observed behavior | Required follow-up |
| --- | --- | --- |
| `blender.mesh._shape_key_signature` | Captures mesh/key pointer, name, lock, count, mode and active index | H02 validates one captured target signature |
| `blender.selection._source_positions` | Reads explicit BMesh shape layer in Edit Mode or `KeyBlock.data` in Object Mode | H02 runtime fixture passes Basis/expression routing |
| `blender.workflows.write_source_positions` | Writes exact explicit target after all IDs/counts/coordinates validate | H02 runtime fixture passes Object/Edit Mode routing |
| `blender.workflows.deform_begin/update/cancel` | Captures target/P0 and checks signature before preview writes | H02 fixture passes cancel and changed-target guards |
| `blender.lifecycle._restore_native_undo_records` | Stores historical KeyBlock and uses shared workflow writer | H02 fixture passes bridge write while Source edits another key |
| `operators.DANFORM_OT_reset_source` | Uses BASE/KEY kind and session proof; refuses unknown saved-key identity | H02 fixture passes same-key reset and replacement/load-evidence refusal |
| `operators.DANFORM_OT_select_shape_key` | Selects active key, syncs proxy | H05 completes UI and New Shape Key workflow |
| `dan_form.agent` | Transaction facade exists, target list/select absent | H06 adds target API and MCP parity |

H01 changed only contracts and review evidence. H02 implementation and runtime
evidence are recorded in
[`2026-09-25-h02-target-io-undo.md`](../testing/2026-09-25-h02-target-io-undo.md).
Native modal G/R/S and remaining matrix rows stay assigned to later phases.
