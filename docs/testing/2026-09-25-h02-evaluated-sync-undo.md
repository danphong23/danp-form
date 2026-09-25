# H02 follow-up — evaluated sync and Undo safety

**Status: Blender 5.2.1 fixture and live MCP Shape Key transition PASS for
version 0.5.34; user confirms stable Blender interaction.** This follow-up covers reports that a Shape Key value change left the
Controller at Basis and that Blender crashed during Undo.

## Findings

- The crash log's Python backtrace entered the deferred native Undo bridge and
  then `_source_positions` while reading Shape Key coordinates. Undo history
  retained a live `KeyBlock` wrapper, which could refer to data Blender had
  replaced during its native Undo operation.
- Idle proxy sync sampled the selected key's stored coordinates. It did not
  observe Shape Key value/blend changes, so a key returning to zero could leave
  the proxy showing the previous key pose.
- Version 0.5.33 introduced a Subdivision fallback using an unlinked object
  copy. `evaluated_get()` returned its Basis coordinates even with Key 1 at
  value 1. On the user's file, the 726 Controller points exactly matched Basis;
  226 differed from stored Key 1, with a maximum difference of 0.359884 Source
  units. The Shape Key signature and depsgraph handler were both current, so
  the fault was the coordinate sample rather than event detection.
- In that file, the base mesh and Basis both contain 1,698 matching positions.
  Stored Key 1 differs from Basis at 642 vertices. Subdivision produces 6,786
  displayed vertices, while Controller contains 726 Source-ID knots. Key value
  is a display input; it does not overwrite either stored coordinate array.

## Changes

- Source-to-Controller sync now samples the evaluated Source mesh and maps the
  resulting coordinates by persistent Source vertex IDs. A missing, duplicate
  or incomplete ID mapping fails safely instead of guessing by array index.
- A runtime evaluation signature observes Shape Key values, mute state, active
  key, evaluation time and show-only-key changes. The depsgraph callback resyncs
  the Controller when the visible Source pose changes.
- Undo history now stores scalar key identity (`kind`, pointer, name and index)
  instead of a live `KeyBlock` wrapper. Before restoration, the adapter resolves
  that identity against the current stack; a mismatch is rejected before access
  or mutation.
- Entering/leaving Controller Edit refreshes the proxy after Blender evaluates
  the temporary show-only-key state.
- If a topology-changing modifier duplicates Source IDs, copy the Source mesh
  and ask Blender to create a temporary Shape Key from its current mix. Map
  that native mixed pose by original Source IDs, then remove the temporary
  object and mesh. This keeps Controller coordinates on the Source cage and
  avoids guessing which subdivided point represents an original vertex.

## Evidence

- [PASS] `tests/live_shape_key_support.py`: evaluated Controller pose at key
  values 1.0, 0.5 and 0.0; automatic depsgraph detection; Basis/expression and
  absolute-key coordinate routing; cancel; safe key identity resolution;
  Undo/Redo bridge including Source Edit Mode; lock, target-change, Reset and
  no-key cases.
- [PASS] A level-2 Subdivision fixture compared returned coordinates against
  independently calculated Basis/key coordinates. Controller followed a
  partial blend, value zero, and the zero-to-one transition. An absolute-key
  fixture also verified a half-time blend under Subdivision.
- [PASS] `tests/live_owned_object_safety.py` and
  `tests/live_duplicate_bindings.py` remain green.
- [PASS] 59 static test functions; documentation regeneration and validation;
  `git diff --check`.
- [FAIL, corrected in 0.5.34 fixture] The earlier live 0.5.33 check compared
  Controller positions to the same faulty fallback output, producing a false
  PASS. The user's zero-to-one test exposed it. A later MCP inspection at
  Key 1 = 1 showed both Controller and fallback at Basis while stored Key 1
  coordinates differed. The user's file was already dirty when inspected;
  the read-only probes did not save it.
- [PASS] After installing 0.5.34 into the open comparison file, the Source
  cage evaluation matched stored Key 1 at value 1 (maximum delta 0). Explicit
  resync repaired all 726 Controller points without changing any stored Source
  key coordinates. MCP then changed the value 1 → 0 → 1; ordinary depsgraph
  updates moved Controller to Basis and back to Key 1 with maximum delta 0 at
  each step. The final value was restored to 1, and the file was not saved.
  Afterward, object/mesh/Shape Key datablock counts remained 13/9/5, with no
  temporary object or mesh left behind.
- [USER CONFIRMED] After the 0.5.34 fix and requested Blender check, the user
  reported that it operates stably. The agent did not independently observe a
  native Ctrl+Z/Ctrl+Shift+Z key sequence; its automated Undo/Redo bridge and
  live Shape Key transition evidence are listed above.

## Acceptance

The 0.5.34 fixture and live MCP Shape Key transition pass. The user has
confirmed the Blender interaction is stable, closing H02 user acceptance.
H04 may begin; keep native keyboard evidence attributed to the user because the
agent did not independently operate that input surface.
