# Phase 2 — DANP Form lifecycle and fixed controller topology, 0.2.2

**Status: PASS for this scoped update, 2026-09-18. Broader P2-UX gates remain open.**

## Existing live session

Blender 5.2.1 LTS, workspace Layout, installed extension
`bl_ext.user_default.dan_form` version 0.2.2. Tests used the already-open
`C:/Users/abc/.AI/Code/danp-animation/Project/2. toon/girl_chibi_1.blend`.
Active object before and after was Cube in Object Mode. The existing model
`girl chibi 1` has four control definitions. Dirty was true before and after.
No separate Blender process, scene builder, save, reopen or discard was used.

## Resulting behavior

- Product, extension display and sidebar use DANP Form. Existing `dan_form`
  namespace, operators, properties and schema remain compatible; existing
  controller object names are not renamed.
- Selecting a model shows Init DANP Form and a red Remove DANP Form button.
  Init preserves an existing valid controller pose. Remove is disabled before binding and removes the owned
  controller, unused controller mesh, definitions, masks, binding properties and
  Source ID layers. It preserves model geometry, unrelated data and Source mode.
- Source Edit keeps + and Sync; Source Object/Edit can remove definitions.
  Controller panels and menus omit Sync; controller panels omit +/−. Their
  operators reject controller contexts, including calls through MCP.
- Controller coordinate editing remains allowed. Sixteen common topology
  shortcuts are intercepted only in bound Controller Edit Mode. Native menus,
  tools or MCP can bypass those shortcuts; geometry updates then validate IDs,
  counts and edge connectivity and restore the last valid pose in place.
  This recovery does not write Source geometry or switch Edit Mode.

The controller is not yet a deformation solver: automatic Source-to-proxy syncing
belongs to Phase 2; control-to-Source patch deformation belongs to Phase 4.

## Live verification

[Lifecycle regression](../../tests/live_controller_lifecycle.py) passed 37 checks
on its own removable square fixture inside this same open scene. Coverage includes
Init/re-Init, sidebar/menu contexts, the red Remove row, accepted coordinate edits,
actual native Duplicate/Delete/Subdivide/Fill, same-count BMesh edge rewiring,
missing mapping-layer recovery, repeated Init preserving a valid adjusted pose
and Source Edit Mode, unchanged Source geometry, preserved controller
Edit context, 16 keymaps, full removal in Source Edit/Object and unrelated data
preservation. Recovery assertions follow actual geometry events and do not invoke
the guard manually. The fixture, controller and owned meshes were removed in
`finally`; the original active object, selection, tool selection mode and scene
references were restored. Ordinary model topology editing remained available.

[Sidebar regression](../../tests/live_sidebar_regression.py) passed 33 checks on
the existing model. It verifies idle caches and handlers, row selection,
Source/controller overlay contexts, eyes/global display, navigation, controller
operator rejection, Source Sync/no-op and overlap deletion, and Source-coordinate
sync. Definitions, masks, revisions, Source coordinates/selection and controller
pose/selection were restored. An outer wrapper restored the original Cube context;
the controller pose comparison returned true.

Warm median synchronous costs in this run: mapping read 0.0016 ms, unchanged UI
projection 0.0024 ms and unchanged proxy sync 0.0332 ms (30 calls each). Individual
eye operations averaged 20.289 ms across three Hide/Reveal pairs. These are local
Python/operator measurements, not viewport FPS or complete input latency.

Computer Use inspected the exact returned Blender window and clicked the DANP
Form tab, the existing model, Edit Control and Back to Model. Screenshots confirmed
the red model Remove button, absence of controller Sync and +/−, and normal
navigation. The user's model was not removed through the UI. Active Cube/Object
was restored afterward; the DANP Form tab remains available for review.

The installed extension had one depsgraph handler and 16 owned keymaps afterward.
Syntax/static contract checks, documentation links/hashes and package/source
consistency were checked before commit.

## Limits

NOT RUN: interactive undo/redo, save/reopen, custom keymap variants, direct
keyboard shortcut dispatch, modal extrusion/cancel, multi-object Edit Mode,
20-control scrolling and large-mesh stress. Shortcut registration/poll coverage
does not prove every customized key binding. Native operator/BMesh recovery was
tested independently of shortcut dispatch. Disabling/unregistering the addon
removes protection. No Phase 3 patch display or Phase 4 deformation is claimed.

The earlier 0.2.1 report records behavior at that version. Its controller-side
create/Sync/delete workflow has been superseded by this model-only definition
editing contract.
