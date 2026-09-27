# H08 — Runtime boundaries review

**Result: PASS for callback/cache lifecycle and the reviewed write boundaries.**

## What was checked

- Dependency-graph callback has a re-entry guard and defers native transform
  completion through a timer. Undo/redo restores Source data only after the
  Blender undo handler returns.
- Load, undo, redo, and unregister invalidate derived mapping, patch, face,
  overlay, transaction, and transform-session state. Persistent Source data
  remains the authority.
- Deformation writeback routes through the shared workflow; native transforms,
  agent operations, and UI updates use the same transaction and target-aware
  write path. The only post-undo restoration path is the explicit history
  reconciliation, with guarded writes after undo.
- Expected stale topology, locked target, and invalid binding errors are
  surfaced as paused/error states. The overlay's broad exception boundary is
  intentionally retained so a GPU draw failure cannot break Blender's viewport;
  it drops cached batches so stale geometry is not displayed and logs a
  contextual traceback once per consecutive failure streak.

## Verification

- Blender 5.2.1 background runtime fixture passed 12 checks across two complete
  register/unregister cycles, handler uniqueness, overlay lifecycle, undo/load
  cache invalidation, and re-registration.
- Static regression coverage verifies overlay failures clear cached geometry,
  emit diagnostic context, and avoid flooding Blender's console during repeated
  draw failures. A GPU-backed injected-failure check remains open.
- H04 native transform, H05 target workflow, H06 agent API and H07 recovery
  fixtures pass in their phase reports.
- Existing representative performance evidence is recorded in
  [the Controller Edit performance report](phase-02-edit-performance-report.md):
  50 definitions, 824 controller vertices, 924 edges; 4.706 ms median live
  BMesh position collection and 0.0119 ms cached GPU batch access. Numerical
  uniform Scale median/P95 improved from 26.39/29.89 ms to 8.91/9.28 ms in the
  [Scale audit](2026-09-25-all-control-scale-audit.md).

## Limits

These are scoped regression baselines, not a full large-mesh release benchmark.
GPU overlay error injection and peak-memory measurement remain explicit H09
release gates. No changes were made to the user's open Blender file.
