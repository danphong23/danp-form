# Blender Interaction Model

**Status: Normative UX intent; exact key binding is an implementation choice**

```text
Source: select vertices/edges → Make Control
Proxy: select a point / vertex strip / edge-span / loop → G/R/S
Transform: proportional → confirm/cancel
Release contour: DAN Form Hide Selected → other edits → Reveal
```

## Sidebar and control management — Phase 2 UX upgrade

Sidebar context follows the active Source or its bound controller. An unrelated
object or empty selection must not leave commands targeting the previous Source.
Identity binding, not display names, resolves the Source. Drawing the panel is read-only.

Make Control keeps Source active in Edit Mode with its selection intact. Definitions
may overlap partly or completely; each list entry has its own UUID/name while the
proxy deduplicates Source geometry. List selection, rename and removal are UX actions;
removal deletes only membership and unused proxy elements, never Source topology.

List states On/Partial/Hidden are derived from canonical effective geometry, not
per-definition activation flags. Whole-line Hide uses edge intent plus standalone
point intent; shared masks may change other overlapping entries. Display tooltips
explain this. Selection never implicitly reveals hidden geometry.

A colored Source control overlay makes edges/points readable without altering Source
materials or geometry. Show Overlay/X-Ray/Show Hidden are display-only and distinct
from DAN Form Hide/Reveal. Main controls precede collapsed Display and Maintenance.
See the [UX plan](../roadmap/phase-02-ux-upgrade.md) for layout, context-specific Select
actions and tests required before Phase 3. Phase 2 does not enable deformation G/R/S.

## Selection and deformation

Vertex mode selects nodes; edge mode selects full represented Source spans. Mixed
selection is a union; span endpoints are selected, not implicit stationary nodes.
Loop selection excludes hidden portions. Enabled unselected geometry holds its position.
Hidden portions are not selectable deformation handles until revealed.

The controller object is parented to Source, so object transforms follow Source.
Control vertex edits are a separate action through DAN Form transactions. Wires
remain Source-backed 3D geometry when selecting contours in front/side views.

Show Patches, including any per-patch color toggle, controls overlay display only.
It never toggles patch deformation or removes Source faces from solve input.

Own transforms through a DAN Form operation for immutable rest, cancel and one undo.
Intercept proxy hide/reveal (for example H/Alt-H) only in DAN Form context; update
Source masks, effective network, display and patch cache together. Object/collection
visibility remains display-only. A hide command cannot merely toggle proxy hide flags.

Use labels/tooltips explaining Hide releases shape constraints and cuts; Reveal adopts
the current mesh contour. No separate activate/deactivate or parent/child control UI.
Enabled shared endpoints may remain visible when a neighboring span is hidden.

Hide/reveal is a separate undo step, with no Source coordinate write. Finish/cancel the
active transform first. Preserve original mode/selection safely. Expose profile/radius
or Whole Patch, not solver-specific controls. Refine must not act as Reveal.
