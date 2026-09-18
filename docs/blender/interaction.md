# Blender Interaction Model

**Status: Normative UX intent; exact key binding is an implementation choice**

```text
Source: select vertices/edges → Make Control
Proxy: select a point / vertex strip / edge-span / loop → G/R/S
Transform: proportional → confirm/cancel
Release contour: DANP Form Hide Selected → other edits → Reveal
```

## Sidebar and control management — Phase 2 UX upgrade

Sidebar context follows the active Source or its bound controller. An unrelated
object or empty selection must not leave commands targeting the previous Source.
Identity binding, not display names, resolves the Source. Drawing the panel is read-only.

The product/sidebar name is DANP Form. Existing `dan_form` extension/operator/storage
identifiers remain compatible. When the model is active, Init DANP Form and a red
Remove DANP Form button are always visible; Remove is disabled before binding.
Init is idempotent and also rebuilds a missing controller. Remove deletes the
controller, its unused mesh, Source-owned DANP Form definitions/masks/binding and
ID attributes. It preserves model geometry, unrelated properties, attributes and
Source Object/Edit Mode. It is one undoable addon operation.

Make Control keeps Source active in Edit Mode with its selection intact. Definitions
may overlap partly or completely; each list entry has its own UUID/name while the
proxy deduplicates Source geometry. List selection, rename and removal are UX actions;
removal deletes only membership and unused proxy elements, never Source topology.

List states On/Partial/Hidden are derived from canonical effective geometry, not
per-definition activation flags. Whole-line Hide uses edge intent plus standalone
point intent; shared masks may change other overlapping entries. Display tooltips
explain this. Selection never implicitly reveals hidden geometry.

A colored Source control overlay makes edges/points readable without altering Source
materials or geometry. When the controller is selected in Object Mode, the same
colored lines are read directly from the controller mesh, so they remain exactly on
the editable proxy after a control change. In Controller Edit Mode the auxiliary
overlay is suppressed because Blender's selected wire/vertex display is already the
authoritative view; this prevents a second, confusing line from being drawn. Show
Overlay/X-Ray/Show Hidden are display-only and distinct from DANP Form Hide/Reveal;
rare display/maintenance actions belong in the list menu.
The sidebar uses a Blender-native list: inline names and eye state, shared +/− and
up/down controls, and Sync below it only in Source Edit Mode. Clicking a row immediately highlights
its effective control geometry. In Source/controller Edit Mode it also replaces the
active mesh selection with that definition; in Object Mode it keeps object/mode.
Selecting a hidden definition never reveals its canonical masks.

Edit Control activates the model's controller, enters its Edit Mode and selects the
active definition. Back to Model returns to the Source in the Object/Edit Mode used
before navigating to the controller. Hide Controls / Show Controls hides both the
controller object and Source wire overlay without changing masks or control influence.
Hiding the whole controller while it is active returns to the model first. Edit Control
shows a globally hidden controller but preserves individual definition masks.
No repeated row action boxes or persistent Display/Maintenance blocks.

Creation (+), membership Sync and definition removal (−) belong to the model.
Controller sidebar/menu omit these actions and their operators reject controller
context. Sync replaces the active definition's membership from current Source
selection, preserving UUID/name/order and canonical shared masks. Coordinate display
sync remains automatic. Rename/reorder do not change deformation or network revision.
See the [current native list plan](../roadmap/phase-02-native-list-ux.md) for the
object/mode matrix, eye behavior and tests. Phase 2 does not enable deformation G/R/S.

## Selection and deformation

Vertex mode selects nodes; edge mode selects full represented Source spans. Mixed
selection is a union; span endpoints are selected, not implicit stationary nodes.
Loop selection excludes hidden portions. Enabled unselected geometry holds its position.
Hidden portions are not selectable deformation handles until revealed.

The controller object is parented to Source, so object transforms follow Source.
Control vertex edits are a separate action through DANP Form transactions. Source
selection uses Source-backed lines; controller Object Mode uses controller-backed
lines, while Controller Edit Mode shows only the actual editable wire geometry.

Controller topology is fixed to the effective Source network. Moving existing
points is allowed; adding, extruding, duplicating, deleting, dissolving, merging,
subdividing, rewiring edges or filling faces is not. Context-specific shortcut
guards intercept common modeling keys on the controller only. Geometry events
validate IDs and connectivity, not just element counts. If a native menu/tool/MCP
command bypasses the key guard, restore the last valid proxy pose in place without
changing Source or leaving Controller Edit Mode. Source definitions and canonical
Hide/Reveal may legitimately rebuild the proxy. On reload/undo/redo/load, derive
expected topology from Source and rebuild the runtime recovery snapshot.
Phase 2 coordinate editing is still not mesh deformation; Phase 4 supplies that.

Show Patches, including any per-patch color toggle, controls overlay display only.
It never toggles patch deformation or removes Source faces from solve input.

Own transforms through a DANP Form operation for immutable rest, cancel and one undo.
Intercept proxy hide/reveal (for example H/Alt-H) only in DANP Form context; update
Source masks, effective network, display and patch cache together. Object/collection
visibility remains display-only. A hide command cannot merely toggle proxy hide flags.

Use labels/tooltips explaining Hide releases shape constraints and cuts; Reveal adopts
the current mesh contour. No separate activate/deactivate or parent/child control UI.
Enabled shared endpoints may remain visible when a neighboring span is hidden.

Hide/reveal is a separate undo step, with no Source coordinate write. Finish/cancel the
active transform first. Preserve original mode/selection safely. Expose profile/radius
or Whole Patch, not solver-specific controls. Refine must not act as Reveal.
