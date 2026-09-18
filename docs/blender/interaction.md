# Blender Interaction Model

**Status: Normative UX intent; exact key binding is an implementation choice**

```text
Source: select vertices/edges → Make Control
Proxy: select a point / vertex strip / edge-span / loop → G/R/S
Transform: proportional → confirm/cancel
Release contour: DAN Form Hide Selected → other edits → Reveal
```

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
