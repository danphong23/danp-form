# H02 follow-up — evaluated sync and Undo safety

**Status: PASS in Blender 5.2.1 background fixtures and live MCP mapping check;
interactive native Undo is still pending user acceptance.** This follow-up was prompted by a report that a
Shape Key value change left the Controller at its previous pose and Blender
crashed during Undo.

## Findings

- The crash log's Python backtrace entered the deferred native Undo bridge and
  then `_source_positions` while reading Shape Key coordinates. Undo history
  retained a live `KeyBlock` wrapper, which could refer to data Blender had
  replaced during its native Undo operation.
- Idle proxy sync sampled the selected key's stored coordinates. It did not
  observe Shape Key value/blend changes, so a key returning to zero could leave
  the proxy showing the previous key pose.

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
- If a topology-changing modifier duplicates Source IDs, evaluate the same
  Shape Key pose on an unmodified temporary Source copy. This keeps Controller
  coordinates on the Source cage and avoids guessing which subdivided point
  represents an original vertex.

## Evidence

- [PASS] `tests/live_shape_key_support.py`: evaluated Controller pose at key
  values 1.0, 0.5 and 0.0; automatic depsgraph detection; Basis/expression and
  absolute-key coordinate routing; cancel; safe key identity resolution;
  Undo/Redo bridge including Source Edit Mode; lock, target-change, Reset and
  no-key cases.
- [PASS] The same fixture with a level-2 Subdivision modifier: Blender produced
  more evaluated vertices than Source, while Controller kept all Source IDs
  and followed the full, blended and zero-valued Shape Key poses.
- [PASS] `tests/live_owned_object_safety.py` and
  `tests/live_duplicate_bindings.py` remain green.
- [PASS] 59 static test functions; documentation regeneration and validation;
  `git diff --check`.
- [PASS] Blender MCP inspection of the open comparison file and modifier stack.
  After loading 0.5.33, cage evaluation returned 1,698 unique IDs; all 726
  existing Controller points matched the corresponding Source pose exactly
  (maximum delta 0.0). The installed manifest reports 0.5.33 and the file
  remained clean. The earlier 0.5.32 probe had reproduced the Subdivision error.
- [NOT RUN] Native Ctrl+Z/Ctrl+Shift+Z from a real Blender UI after a Controller
  transform. The Blender MCP connection can inspect the live UI, but this
  session does not expose native keyboard input. The open file was inspected
  read-only and was not saved or modified.

## Acceptance

The code and disposable fixtures pass. Version 0.5.33 is installed in the
current Blender session. H02 is not user-accepted yet: check that changing the
Shape Key value from 1 to 0 moves the Controller back with the visible Source,
then perform a real Undo/Redo after a Controller edit and confirm Blender stays
open and both objects remain in sync. Do not start the next phase until that UI
check passes.
