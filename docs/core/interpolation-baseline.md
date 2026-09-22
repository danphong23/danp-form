# Patch Interpolation Prototype

**Status: Current solver; required behavior comes from core contracts**

## Product requirements

Inputs are immutable current patch P0, actual patch topology, the initial selection
intent, Controller vertices that actually moved, enabled controls outside their union,
and proportional settings. Hidden geometry is ordinary Source geometry.
Names/logical grouping must not affect the result.

Keep current patch form as the geometric starting point. Generate its deformation from
control movement and the user proportional setting; never reconstruct a patch solely
from sparse endpoint positions or pull toward the historical template. Extra detail
preservation is not mandated; a user can add controls around a feature to edit it separately.

Hard targets: moved vertices equal Q; selected-but-unchanged vertices equal P0 and
remain part of the transforming boundary; enabled control vertices outside the
selection/moved union equal P0 as stationary anchors. No-op returns P0 and clears old
preview motion. New deformation stays in currently affected patches; cleanup stays in
captured scope. These rules hold for every method.

No required formula says a patch midpoint moves half as far as a boundary. Whole Patch
and finite radius/profile may produce different interior responses. Inspect leg examples
in product/leg-control-examples.md before interpreting interpolation results.

## Current interpolation

For every vertex in the transform boundary, take its measured Controller displacement
`D[i] = Q[i] - P0[i]`; a selected point that Blender leaves unchanged has `D[i] = 0`.
Enabled control vertices outside the transform boundary are separate zero-displacement
anchors. For a free vertex, solve a weighted discrete Laplace equation on the
patch's Source edges:

```text
sum over neighbors j: (D[v] - D[j]) / length_P0(v,j) = 0
P1[v] = P0[v] + A[v] * D[v]
```

This spreads local Blender Proportional motion along the boundary smoothly into the
patch without fitting one transform to a named control. In a straight strip, edge
resistance follows its original length, retaining the spacing ratios of intermediate
rings. A free component unreachable from any constraint retains P0. With no fixed
boundary and a coherent whole-control G/R/S, a fitted transform can extend through
the patch; nonuniform targets use the constrained solve.

`A` is 1 for Whole Patch (`Radius = 0`), or the chosen profile of Source-local
rest-edge distance for finite radius. It never weakens hard control targets.
Every preview starts from immutable P0, not the previous preview. Build and
validate the complete output before writeback; copy hard targets and unchanged
control positions exactly and reject conflicting shared-patch results.

The solver minimizes edge displacement differences. It does not guarantee
volume preservation or prevent face inversion under extreme edits. More
geometric controls can constrain important features when needed.

## Required observations

- No targets change: exact unchanged geometry, with no relaxation.
- One boundary moves: target exact, other enabled controls fixed; inspect how each chosen profile/radius changes interior motion.
- One knot moves: no other enabled Source control vertex moves, even if proxy is sparse.
- One span or both loops scale: selected dense vertices hit T(P0); enabled longitudinal lines hold; hidden ones follow allowed patch motion.
- Rotate a span: selected Source line transforms exactly; inspect interior shear/smoothness without assuming exact rigid rotation of the whole patch.
- Repeat edits: next operation uses the last committed shape as P0.
- Hide/reveal: topology scope changes, hidden paths follow mesh and reappear at current positions.

## Evidence and limits

Measure smoothness, rotations, irregular topology, sampling-density sensitivity and
proportional response. Adding P0 does not prove every detail is perfectly preserved.
Choose the smallest improvement for a reproduced failure; no mandatory ARAP/harmonic,
SVD or multi-stage backend follows from product definition. Prototype engineering
parameters can change without redefining selection, hide state or hard constraints.
