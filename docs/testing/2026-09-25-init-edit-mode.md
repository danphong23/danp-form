# DANP Form 0.5.36 — initialization from Source Edit Mode

**Result: PASS for the reported failure and recovery paths on Blender 5.2.1 LTS.**

## Reproduction

On a disposable quad in Source Edit Mode, version 0.5.35 raised
`EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE`. It had already assigned a Source
UUID and created a detached Controller object. The live edit BMesh contained
new persistent IDs, while evaluated Mesh data had not yet received them.
The sidebar then saw partial Source metadata without a valid child Controller.

## Fix

- Init temporarily flushes Source Edit Mode to Object Mode before assigning IDs
  and evaluating Controller coordinates, then restores Edit Mode and selection.
- A new Controller must be the Source's direct child and resolve as the active
  binding before Init reports success. If a new Init fails, the new Controller,
  mesh datablock, and partial Source binding are removed.
- The sidebar displays Controller editing controls only when a valid direct
  child exists. A Source with an old UUID but no child offers Rebuild instead.
- A detached legacy Controller is marked unowned even if its UUID matches a
  Source. Selecting it exposes **Unbind DANP, Keep Mesh**; the mesh geometry is
  preserved. Rebuild then creates a valid child for the Source.
- Add-on status messages, errors, panel labels, and tooltips are in English.

## Verification

- New isolated Blender regression: **21 checks PASS** for Edit/Object Init,
  selection and coordinate preservation, immediate control creation, deliberate
  failure rollback, sidebar state, legacy detached Controller recovery, and
  independent Object Mode initialization.
- Release runner: **9 static suites and 9 Blender background suites PASS** on
  a generated two-control transform fixture. The native G/R/S suite includes
  confirm/cancel and paired Undo/Redo. The runner's combined status remains
  `INCOMPLETE` solely for the previously listed GPU overlay and large-mesh
  performance gates.
- Duplicate ownership regression and Controller lifecycle regression passed
  separately. The current user `.blend` was neither modified nor saved.

This verifies Blender operators and sidebar draw logic in isolated Blender
processes. A mouse-driven sidebar click in the user's live Blender session was
not performed for this fix.
