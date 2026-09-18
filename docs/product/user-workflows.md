# User Workflows

**Status: Normative**

## Prepare and edit

Register Source, select Source topology, Make Control and repeat. Patch authoring is
automatic. On the proxy, select a point, strip, span/edge or loop; use G/R/S, choose
proportional, then confirm/cancel. Selected Source-backed geometry moves; all other
enabled control vertices hold. Named control selection is optional convenience.

## Let a contour follow the mesh

Use DAN Form Hide Control on a whole line or selected portion. It temporarily stops
holding mesh and cutting patches. Recompute actual connectivity; patches may merge.
Transform remaining enabled controls. Hidden geometry follows affected patch motion
under proportional. Reveal samples that contour at the new Source positions.

At intersections, other enabled edges may still hold a shared endpoint. Hide endpoint
nodes too if they should be released. No parenting between control definitions or
nested-control feature is required; the controller object itself is a child of Source.
Ordinary object/collection display hiding does not substitute for this command.

Hide whole edge-backed lines uses edge intent to preserve junctions on retained lines.
Node-mode Hide also disables incident edges. Selecting a hidden definition does not
reveal it; use Reveal separately.

## Repeat, rebuild and undo

Each committed result becomes the next Operation Rest. Hide/reveal itself deforms
nothing and is undoable separately. Delete/rebuild proxy without losing Source shape,
definitions or hide masks. Reveal does not reset original positions.

See leg-control-examples.md for the two-loop/longitudinal-line workflow.

## Inspect patches and fit references

Toggle Show Patches to inspect regions without changing deformation behavior. Hide
controls to change actual cuts/constraints; hiding the overlay does not do that.
Create normal Source-backed contours along front/side reference views, then adjust
points/spans/loops with proportional. Human or agent chooses targets through the
same operations; automatic silhouette extraction/calibration is a future extension.
