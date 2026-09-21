# Phase 2 — Stability baseline and live UI verification

**Date:** 2026-09-19  
**Status:** PASS for the scoped fixes in DANP Form 0.5.0

This report records checks performed through Blender MCP on the open character
test file. It is evidence for the current source/package state, not a claim
that the remaining Phase 2–5 gates are complete.

## Fixture

- Source: `girl chibi 1`
- Controller: `DANPFORM_CTRL_girl chibi 1`
- Source mode during checks: Edit Mode
- Source modifier: Subdivision, visible in Edit Mode, On Cage
- Definitions before and after the checks: 23
- The `.blend` file was not saved by the verification run.

## Regression fixes verified

### Effective network and bulk visibility

The pure control resolver no longer adds raw edge endpoints as standalone
points after an edge is hidden. On the live Source:

1. Hide All changed `242 effective edges / 242 effective vertices` to `0 / 0`.
2. The controller rebuilt to `0 vertices / 0 edges`.
3. Show All restored `252 / 252` and rebuilt the complete controller.
4. Source object and Edit Mode remained unchanged.
5. The original state (`10 hidden edges`, `242 effective edges`) was restored.

The round trip is covered by `tests/test_core_controls.py` and a live MCP
operator check.

### Source-backed overlay

Control identity remains on the base Source BMesh, while the display adapter
uses the evaluated child-edge chain carrying the same persistent ID. This keeps
the colored control coincident with Blender's visible Subdivision cage without
allowing evaluated topology to redefine the control. Missing IDs fall back to
the exact base edge, never a nearest neighbor.

The repeatable check is `tests/live_overlay_alignment.py`.

### Definition actions and context

On the installed extension, using the actual sidebar context:

- `+` created a temporary definition from the current Source selection.
- `−` removed it and returned to the original definition count.
- Sync stored exactly the current Source vertex/edge IDs.
- `−` also worked from Controller Edit Mode.
- All temporary data was restored after the check.

### Package and lifecycle hygiene

- Extension package rebuilt as version `0.5.0`.
- Previous `User Default` package uninstalled before installation.
- ZIP contains no `__pycache__`, old monolithic `dan_form.py`, or viewport flag.
- Registration now tolerates Blender restricted install context.
- Duplicate handler instances are removed by module/name before registration.
- Final live session has one DANP Form module and one handler per lifecycle role.

## Current completion evidence

The later gates are now covered by repeatable MCP checks on the same open file:

- `tests/live_deformation_regression.py`: temporary two-quad fixture, real
  Controller Edit selection, Smooth/proportional preview, exact Cancel restore,
  and Commit through `dan_form.deform` — 10/10 checks.
- `tests/live_reference_workflow.py`: real Front Orthographic, Right/Side
  Orthographic and Perspective viewport transitions, preview/Cancel in each
  direction, then Hide/Reveal — 15/15 checks.
- `tests/live_overlay_alignment.py`: exact ID-preserving evaluated edge
  alignment while a viewport Subdivision modifier is enabled.
- `tests/live_controller_lifecycle.py` and `tests/live_sidebar_regression.py`:
  lifecycle, Source/Controller context, `+`/Sync/`−`, Hide/Show and handler
  hygiene — PASS after the final package reload.

The source/package audit also passes: the ZIP contains 21 current modules, no
`__pycache__`, no old monolithic `dan_form.py`, no obsolete viewport flag, and
no duplicate runtime module or lifecycle handler remains in Blender. Automatic
pixel-to-target image fitting is intentionally outside the accepted plan; the
agent/user supplies reviewed targets from the reference image.
