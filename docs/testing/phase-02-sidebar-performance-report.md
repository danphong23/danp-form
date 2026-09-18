# Phase 2 — Sidebar performance and navigation, 0.2.1

**Status: PASS for the scoped fixes below, 2026-09-18. This does not close every P2-UX gate.**

## Live session

Blender 5.2.1 LTS, existing open file
`C:/Users/abc/.AI/Code/danp-animation/Project/2. toon/girl_chibi_1.blend`.
Active model `girl chibi 1`, four existing definitions, workspace Layout;
1,698 vertices, 3,392 edges, 1,696 polygons on Source.
Dirty was true before and after. No scene builder, separate Blender process, save,
reopen or discard was used. Regression restores definitions, masks, revision,
coordinates, object/mode and mesh selection in a finally block.

## Root causes and changes

- `_source_id_maps` called `_ensure_source_ids` on each Object Mode read. That
  hashed the full topology, serialized Source properties and called mesh.update.
  Overlay, list projection and handlers repeated this work during redraw.
- The depsgraph handler synced every model on every event. `_sync_proxy` wrote
  coordinates and called mesh.update even when all coordinates were identical.
- Two DAN Form handler instances were present: the installed extension and the
  previous live test module. Each also owned an overlay handler. Both were
  unregistered and only the installed extension module was reloaded.

Mapping reads now use runtime caches without Source writes. Explicit initialization
assigns IDs; structural/visibility operations validate topology. Geometry updates
invalidate the mapping. List projection returns immediately for unchanged metadata
and masks. Proxy sync runs for Source geometry changes and only updates changed
coordinates. Load/undo/redo handlers invalidate projections and mapping caches.

The active UIList callback immediately updates overlay highlight, including point
controls. In Edit Mode it selects corresponding Source/proxy IDs. The overlay now
follows the active context: Source coordinates when the model is selected, current
controller mesh coordinates in controller Object Mode, and no auxiliary overlay in
Controller Edit Mode because Blender's actual selected proxy mesh is clearer.
Edit Control enters controller Edit Mode; Back to Model restores the previous Source
Object/Edit Mode.
Hide/Show Controls changes controller/overlay display only, without rebuilding the
proxy or changing canonical masks. Individual eyes retain canonical Hide/Reveal.

Related regressions fixed: Sync serialized a fresh unchanged list after editing a
detached definition dict; it now saves the modified list. Controller rebuilds could
refresh the UI during mode transitions before the new active UUID was assigned;
explicit reconciliation now keeps the row and UUID aligned.

## Measured synchronous costs

| Operation | Before, one sample | After, warm median of 30 calls |
| --- | ---: | ---: |
| ID mapping read | 22.796 ms | 0.0016 ms |
| Unchanged UI list projection | 113.931 ms | 0.0024 ms |
| Proxy sync, unchanged coordinates | 12.962 ms | 0.0334 ms |

Individual eye operators averaged about 13–22 ms per operation across regression runs
(latest installed reload: 15.277 ms), measured in three Hide/Reveal pairs per run.
These are Python/operator measurements in this specific live session,
not total interaction latency or FPS. Before samples included the old implementation
and the duplicate handler state; after samples use one registered implementation.
Cold mapping rebuilds and changed list projections still perform actual work.

## Verification

[Live regression](../../tests/live_sidebar_regression.py) ran through MCP in this
session and passed 33 assertions:

- Idle graph events skip proxy sync; cached list rows stay allocated; read-only
  lookups never assign Source IDs or modify Source properties.
- Object Mode row selection changes highlight without changing object/mode.
- Model selection keeps Source-backed color lines; controller Object Mode switches
  the overlay coordinate source to the proxy mesh; Controller Edit Mode suppresses
  the duplicate auxiliary overlay.
- Global display toggles hide/show controller, preserve masks and do not rebuild it.
- Edit Control enters proxy Edit Mode; row selection selects effective proxy IDs;
  Back restores either prior Source Object Mode or Source Edit Mode.
- Source Edit row selection selects definition IDs; controller Edit supports create,
  Sync membership and delete through mapped Source IDs.
- Source Sync persists replacement membership, changes revision once and is a no-op
  when membership is unchanged. Overlap deletion preserves shared point geometry.
- Sidebar operations leave Source coordinates unchanged. An external Source
  coordinate change still updates the corresponding proxy coordinate.

Computer Use identified the exact Blender window, then visibly confirmed row
selection/highlight, Edit Control, automatic Edit selection on another row, Back to
Model, Hide Controls and Show Controls. It ended in model Object Mode with controls
visible and Layout unchanged. No text/code was typed into Blender UI.

Compile and the existing static package/contract checks passed. The live test is
intentionally not collected as a standalone pytest test: it needs this open Blender.
The installed extension files were updated to 0.2.1 and reloaded from their real disk
location; all 29 assertions passed again and exactly one DAN Form depsgraph handler
remained. The extension ZIP was verified byte-for-byte against source and manifest.

NOT RUN in this scoped verification: file save/reopen, interactive undo/redo,
20-control scrolling, very large mesh stress/FPS and deformation (a later phase).
Cache lifecycle hooks were installed but those are not evidence of interactive
undo/redo or save/reopen validation.
