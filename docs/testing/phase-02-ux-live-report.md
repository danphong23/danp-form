# Phase 2 UX live test report

**Date:** 2026-09-18
**Blender:** 5.2.1 LTS
**File:** `C:\Users\abc\.AI\Code\danp-animation\Project\2. toon\girl_chibi_1.blend`
**Workspace:** Layout
**Initial/final dirty state:** `true` / `true`
**Saved by test:** No

The extension ZIP was installed and enabled in the running Blender process. The
existing Source was `girl chibi 1`, initially in Edit Mode with its existing control
definitions. No scene builder, background Blender process, or file save was used.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Install/reload and overlay handler | PASS | MCP returned `FINISHED`, extension enabled, handler removed/re-added exactly once |
| Initialize/rebuild from Source Edit Mode | PASS | Source stayed active in `EDIT_MESH`; controller remained parented to Source |
| Make Control without leaving Edit Mode | PASS | Two new definitions created from the same selected edge; active object and mode stayed Source/Edit |
| Full overlap allowed | PASS | Both new definitions shared the same Source edge membership |
| Select from list | PASS | Computer Use click selected the expected Source vertex/edge IDs; mode stayed Edit |
| Hide/Reveal overlap | PASS | Computer Use made A `Hidden` and overlapping B `Partial`; MCP saw only the shared edge mask, then Reveal restored both |
| Rename | PASS | Computer Use dialog changed a control name; MCP confirmed the persisted name; original name restored afterwards |
| Definition delete | PASS | MCP deleted one duplicate definition and confirmed the other membership survived; Source topology was untouched |
| Active-model resolver | PASS | Temporary second mesh was initialized and edited, then removed; returning to the original active mesh resolved its own controller and list |
| Colored display | PASS | Controller color was cyan; Source overlay toggle changed display state without removing the draw handler or changing Source geometry |

The temporary second Source and controller were removed, and the original Source
definitions, masks, active object, mode and selection were restored. The file was
already dirty before testing, so the dirty flag cannot be attributed to this run.

Save/reopen, undo across a real application restart, and full topology-corruption
recovery were not run because the open file contained pre-existing unsaved work and
the workspace instructions prohibit replacing or saving over it for a UX test. Those
remain lifecycle evidence for Gate P2; they do not invalidate the UX checks above.
