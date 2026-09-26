# C01 checkpoint — operation safety

**Date:** 2026-09-26
**Status:** verified checkpoint; C01 remains open.
**Runtime:** Blender 5.2.1 LTS, Windows 11, generated factory-startup fixtures.

## Changes in this checkpoint

- The Deform operator only cancels the transaction it opened. Busy rejection
  cannot roll back another caller's transaction.
- Native G/R/S refuses to begin while the Source already has an open operation;
  native commit/cancel verifies the transaction identity it owns.
- The workflow validates targets against the controller mapping captured at
  operation start, checks 3D shape and finite coordinates before solving/writing.
- WORLD transforms reject non-finite or non-invertible matrices instead of
  producing incorrect targets through `inverted_safe`.
- Create/Sync/Hide/eye/Reveal/Delete snapshot definitions, masks, revision,
  proxy mesh/generation, and proxy runtime snapshot. An injected rebuild failure
  restores the pre-operation state.
- Reset postpones removing the old controller and owned face objects until a
  replacement is complete. A failed rebuild restores Source properties, ID
  layers, binding and controller.
- Repair restores topology metadata, paused state, identity layers and proxy if
  the rebuild fails after ID repair.
- Unregister cancels an open preview to Operation Rest and clears runtime state.
- Registration failure rolls back classes, properties, handlers, overlay and
  keymaps registered earlier in the same attempt.
- Added `live_operation_ownership.py` to the release runner and a singular-matrix
  regression to the core suite.

## Results

- Release runner: 9/9 static suites and 11/11 Blender background suites passed;
  overall status `INCOMPLETE` because H08 GPU overlay review and P95/peak-memory
  measurement were not run. UI gate passes in its report remain historical
  evidence, not UI interaction on this revision.
- Operation/structure regression: 14/14 assertions passed — caller ownership,
  unmapped target rejection, injected failures across Create/Sync/Hide/eye/
  Reveal/Delete/Reset, unregister recovery, and successful Reset commit.
- Topology recovery suite passed with additional injected Repair rebuild failure;
  ID layers, metadata, paused state and proxy were restored before a real repair.
- Runtime boundary suite passed with an injected registration failure after two
  class registrations; no partial class/property/overlay state remained.
- Consistency audit: 8 PASS, 3 FAIL. Remaining defects concern native
  Hide/Reveal reconciliation, multi-control Hide, and eye actions clearing
  unrelated selection. They are queued for C02.
- The user's open Blender file was not touched. Tests ran in separate
  background processes with disposable factory-startup scenes.

## Remaining C01 scope

C01 still needs native timer/exception race coverage, timer shutdown on disable,
review/removal of historical operators, and module-boundary cleanup. This
checkpoint does not mark C01/C02 complete or the add-on ready for release.
