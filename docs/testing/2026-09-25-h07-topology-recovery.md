# H07 — Topology recovery acceptance — 2026-09-25

**Status: PASS.**

## Automated evidence

- Blender background fixture: Blender 5.2.1 LTS, 20 assertions passed.
- Covers safe disconnected additions/removals, Validate/Repair, exact persistent
  ID assignment, Controller rebuild, Shape Key and Basis preservation,
  save/reopen snapshots, count-preserving connectivity edits, control-edge loss,
  loop cuts in a disabled control patch, duplicate IDs, and no writes after a
  rejected repair.
- Static topology-recovery tests: 5 checks passed.
- Background Blender disables global Undo, so this part was checked in the UI.

## Blender UI acceptance

The user reported on 2026-09-25 that the requested Validate/Repair and Undo/Redo
workflow worked stably. The acceptance criteria were that Undo returns the
mapping to paused and Redo restores the repaired mapping. Failed validation
must leave mesh, Shape Keys, and controls untouched.

This is user-reported acceptance; no video, screenshot, or UI log was attached.
The active project was not used or saved as a test fixture.

## Commit

`feat(dan-form): make topology recovery explicit`
