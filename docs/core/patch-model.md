# Patch Model and Influence Boundary

**Status: Normative**

Derive patches as Source face-graph components after removing adjacency across effective
enabled control edges. Hidden edges do not cut. Names/groups have no geometric effect.

An interior open chain splits only if connectivity actually disconnects. One longitudinal
line on a cylinder may leave one patch because faces can route around the other side.
Never promise hiding a line always merges exactly two patches.

## Operation scope and constraints

Resolve selected Source vertices/spans and their nonzero targets. Include every patch
incident to moving Source geometry, including all sides of separators and junctions.
Unrelated patches are excluded; proportional radius cannot expand that set.

Capture all patches incident to resolved selection at operation start as potential scope.
Per-update affected scope may shrink when targets become zero; operation-semantics.md
requires resetting earlier preview writes to P0. Patches outside captured scope are
never written, including during cleanup.

Selected enabled vertices hit their targets. Every other enabled control vertex stays
at P0. Hidden vertices are ordinary mesh vertices, not anchors: they can follow
deformation inside this scope and proportional radius.

## Patch graphs and shared vertices

A control vertex propagates to a set of graph-connected vertices inside incident
patches, subject to proportional and hard constraints. Paths follow member-face
edges; they may branch. Do not assign one exclusive vertex chain to each control
vertex or infer horizontal/vertical/anatomical directions from control names.

Patch visualization visibility is display-only. All patches remain available to
scope/solve regardless of overlay toggles; DANP Form control Hide changes actual
partition as described below.

Use edges of member faces to build each patch graph, not shortcuts through other patches
in a global induced vertex graph. Boundary vertices can belong to multiple patches.
Shared enabled vertices have the same hard moving/fixed target in all incident solves.
Validate agreement before writeback; last-write order must not resolve conflicts.
Vertices belonging only to patches outside captured scope are never written.

The prototype rejects non-manifold/vertex-only connections rather than merging
incompatible free-vertex results. Manifold surfaces with boundary are the correctness
baseline. A deformation with no incident faces/patch returns NO_AFFECTED_PATCH before
writing; loose point/edge controls are not an alternate direct-mesh edit path.

## Hide/reveal

Recompute connectivity after hiding any control portion. If patches merge, subsequent
operations use the new patch scope. Hiding itself changes no Source coordinates.
Reveal resamples current Source and restores cuts; it does not revert shape or replay
previous operations. Partial hiding leaves retained enabled portions as cuts/constraints.

Freeze the enabled network for each deformation. Network/visibility revision changes
invalidate the transaction; do not continue with old cached patches.
