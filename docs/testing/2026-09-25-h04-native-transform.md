# H04 — Native modal transform acceptance — 2026-09-25

**Status: PASS.**

## Automated evidence

- Blender background fixture: Blender 5.2.1 LTS, 23 assertions passed.
- Covers native-style Translate/Rotate/Scale, partial controls, nearby
  proportional region, stationary adjacent control, consecutive Scale, paired
  Source Undo/Redo repair, exact cancellation and runtime cleanup.
- Maximum Source error after cancel: 0.0 Source-local units.
- The cancellation path now holds the shared sync guard through Source restore
  and Controller synchronization, preventing the depsgraph observer from
  treating the restore as a fresh transform sample.

## Blender UI acceptance

The user reported on 2026-09-25 that all requested UI checks worked on a safe
copy: mouse-driven G/R/S with full and partial control selection, non-unit
object scale, with and without Shape Keys, confirm/cancel, and Undo/Redo. The
reported outcome was stable operation without the previously observed flicker
or partial mesh scaling.

This is user-reported acceptance; no video, screenshot, or UI log was attached.
The active project was not used or saved as a test fixture.

## Commit

`fix(dan-form): stabilize native transform transactions`
