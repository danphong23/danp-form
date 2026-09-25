# H02 — Target I/O and Undo report

**Status: PASS for the H02 runtime target-safety gate.** Blender 5.2.1 LTS;
starting add-on commit `6664763`. The fixture uses a disposable mesh and never
loads or saves the user's open project.

## Changes verified

- Source coordinate reads and writes resolve one explicit target. Object Mode
  uses the target `KeyBlock.data`; Edit Mode reads/writes that key's BMesh shape
  layer, even when a different key is active in the edit context.
- Target signatures include mesh/key identity, name, lock, point count,
  relative/absolute mode and active index. A changed target or signature stops
  preview before another write. Cancel uses the captured key reference.
- The Undo/Redo bridge writes its stored historical target through the same
  adapter. The Source Edit Mode case leaves Basis active while the bridge
  restores an expression key.
- Reset records `BASE` or `KEY`. Since Blender 5.2.1 KeyBlocks do not support
  ID properties, key proof is session-only. Load clears that proof; observed
  key-stack replacement invalidates it. Reset refuses when the original key
  cannot be proven, including a same-name replacement.

## Evidence

- [PASS] `tests/live_shape_key_support.py` — Basis and expression edits,
  untouched-key checks, Source Edit Mode explicit read/write, cancel, locked
  key, target switch/rename, Undo/Redo bridge in Source Edit Mode, absolute
  stack read/write/deform/cancel and Undo/Redo bridge, Reset on captured key and safe refusal after
  replacement or loss of session evidence, and no-key control creation.
- [PASS] Seven ownership/topology static checks and all 59 static test
  functions invoked directly; no failures. `pytest` is not installed in this
  environment, so the static functions were called through a small direct
  runner rather than the pytest runner.
- [NOT RUN] Native modal G/R/S and real interactive Undo/Redo keypresses; these
  require a separate Blender UI gate. In-operation key reorder and every
  T15/T16 combination remain for their assigned H04/H06/H07 coverage.
- [PASS] `scripts/validate-docs.ps1` after regenerating the consolidated spec
  and SHA-256 manifests.

## Limits

This report closes H02's target-routing runtime gate. It does not certify the
native modal transform UI or all release matrix rows assigned to later phases.
