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
- Delete Control snapshots definitions, masks, revision, proxy mesh/generation,
  and proxy runtime snapshot. A rebuild failure restores the pre-operation state.
- Unregister cancels an open preview to Operation Rest and clears runtime state.
- Added `live_operation_ownership.py` to the release runner and a singular-matrix
  regression to the core suite.

## Results

- Release runner: 9/9 static suites and 11/11 Blender background suites passed;
  overall status `INCOMPLETE` because H08 GPU overlay review and P95/peak-memory
  measurement were not run. UI gate passes in its report remain historical
  evidence, not UI interaction on this revision.
- Operation ownership regression: 5/5 assertions passed — second caller keeps
  the preview; native bridge rejects a different caller; unmapped target does
  not write; Delete rolls back after injected rebuild failure; unregister
  restores and clears an active preview.
- Consistency audit: 8 PASS, 3 FAIL. Remaining defects concern native
  Hide/Reveal reconciliation, multi-control Hide, and eye actions clearing
  unrelated selection. They are queued for C02.
- The user's open Blender file was not touched. Tests ran in separate
  background processes with disposable factory-startup scenes.

## Remaining C01 scope

R04 has failure-injection coverage for Delete only. Create, Sync, Hide, Reveal,
Reset, and Repair still need rollback coverage. C01 also needs registration
failure rollback, timer/exception race coverage, review/removal of historical
operators, and module-boundary cleanup. This checkpoint does not mark C01/C02
complete or the add-on ready for release.
