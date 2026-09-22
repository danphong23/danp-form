# Geometry Test Cases

**Status: Required prototype evidence; constraints and scope are mandatory**

Record fixture geometry, explicit selection, effective network, targets, profile/radius,
result coordinates and before/after views. Quality-only observations cannot override
hard constraints. No midpoint half-motion or universal affine response is assumed.

## G1 — No-op
All selected targets equal P0; every Source coordinate stays unchanged through previews.

## G2 — One moving boundary
Grid strip with A selected, B enabled stationary. A hits Q; B remains P0; outside scope
is untouched. Compare Whole Patch and finite profiles/radii on the same targets.

## G3 — Two boundaries scale
Both boundaries hit T(P0). Inspect interior continuity and proportional response;
do not require a fixed midpoint displacement or exact affine shape from every profile.

## G4 — Limb form
Two ring controls on a curved/bumped limb. Inspect whether patch form is useful under
proportion edits. Detail follows patch deformation; add controls for separate detail edits.

## G5 — Ring rotation (quality evidence)
One selected ring rotates, other enabled controls fixed. Measure shear/smoothness;
decide if a targeted interpolation improvement is needed.

## G6 — One exact control vertex
Only selected vertex moves; all other enabled control vertices stay P0. Patch response
obeys proportional/scope without moving stationary control neighbors.

## G7 — One sparse knot
Dense curved path with sparse A–B–C; select B only. B hits Q. A/C and every omitted
enabled Source control vertex stay P0. No automatic moving targets along AB/BC.

## G8 — Sparse span transform
Select AB span and rotate/scale it. Represented selected dense vertices hit T(P0).
Unselected spans hold except common endpoints selected by AB; hidden gaps are excluded.

## G9 — Patch connectivity
Interior open line does not split unless adjacency disconnects. Boundary-to-boundary
cut can split. Single cylinder longitudinal line need not split into two patches.

## G10 — Repeated operations
Operation B captures A's committed result as P0; historical snapshot does not pull.

## G11 — Irregular multi-boundary patch (quality evidence)
Inspect smoothness/sampling artifacts with varying displacements and valence. Reproduce
a failure before adding an advanced method; preserve all hard constraints throughout.

## G12 — Enabled longitudinal line
Limb U/L loops plus D. Scale U only, then U+L. Selected loop vertices hit Q; all
unselected enabled D/L vertices stay P0. Selected shared junctions move with loops.

## G13 — Hide longitudinal line
Hide D; derive patches again. D interior is no longer a constraint/cut, but U/L
junctions remain enabled through loops. Scale U or both loops; released vertices
receive ordinary patch output within influence. Hiding itself deforms nothing.

## G14 — Reveal at new contour
After G13 commit, reveal D. Positions/bindings match current Source exactly; no
pre-hide coordinate restore. Masks/state survive save/load and proxy rebuild.

## G15 — Partial hide and junctions
Hide middle spans and separately nodes. Retained supporting edges keep endpoints
enabled; hiding nodes disables incident cuts. Validate actual merge/connectivity,
overlapping definitions, partial loops and reveal with independently hidden edges.

## G16 — Grouping independence
Same Source topology, masks, selected IDs, targets and settings represented as separate
lines or one network yield equivalent patch partition, constraints and output. Duplicate
memberships must not add interpolation weight or invisible constraints.

## G17 — Preview returns to rest
Start at P0, move a control, then set its targets back to P0 before confirm. Every earlier
previewed vertex, including hidden paths, returns exactly to P0. Repeat with only some
selected targets returning to rest and with radius shrinking. No residual deformation
may remain outside current influence; vertices outside captured scope stay untouched.

## G18 — Hide intent at junctions
Hide whole D in the U/L/D fixture using edge intent: both loops remain enabled and D's
unsupported interior releases. Hide the U–D node explicitly: incident edges become
ineffective. Reveal an edge clears endpoint node masks but not separately edge-hidden
branches. Repeat hide/reveal: no coordinate change or duplicate state revision.

## G19 — Invalid and degenerate inputs
Test zero-length edges, tiny/large scaled coordinates, empty selection, no moving targets,
no incident faces, non-finite targets and invalid radius. Return finite validated output
or an explicit error before writes. Never divide by an empty sample sum or write NaN.

## G20 — Coordinate-space parity
Same explicit Source-local targets from local/world transforms yield equivalent output.
Use translated/rotated/nonuniformly scaled objects and reject singular transforms. Radius
comparisons use documented consistent units; unexpected mixed-space behavior fails.

## G21 — Definition lifecycle
Create an overlapping definition over hidden geometry: no silent reveal or extra weight.
Remove one overlapping definition: masks and shared supported geometry remain coherent.
Remove last membership: no Source topology edit; obsolete masks/handles are pruned.

## G22 — Selection intent and measured movement
Scale a selected planar loop along each world/local axis that leaves some selected
vertices unchanged. Those points retain P0 exactly but remain part of the transforming
boundary, so the one-control patch uses the full selected loop as its transform samples.
Repeat with Blender Proportional Editing moving unselected proxy points; they become exact
targets. Add a second unselected enabled loop and verify it remains an exact stationary
anchor. Returning all moved targets to P0 is an exact no-op.

## Measurement contract
For pure numerical fixtures record a scale L=max(rest bounding-box diagonal, 1e-12).
Use float64 candidate buffers; an initial comparison tolerance 1e-8*L is a prototype
test parameter, not a frozen production threshold. Check selected targets against Q.
Copy stationary/out-of-influence/rest-cleanup vertices from P0 exactly; a nonzero drift
cannot be excused by a loose quality tolerance. Blender storage tests compare against
stored/round-tripped targets and require unchanged vertices/cancel coordinates exact.

Record before/after and displacement maps for G4/G5/G11 and proportional comparisons.
Quality approval must name inspected fixtures/settings and unacceptable visible artifacts;
recording images without deciding acceptance does not pass Gate C.
