# Patch Interpolation Prototype

**Status: Replaceable prototype candidate; required behavior comes from core contracts**

## Product requirements

Inputs are immutable current patch P0, actual patch topology, explicit selected targets,
enabled unselected stationary vertices, and proportional settings. Hidden geometry is
ordinary Source geometry. Names/logical grouping must not affect the result.

Keep current patch form as the geometric starting point. Generate its deformation from
control movement and the user proportional setting; never reconstruct a patch solely
from sparse endpoint positions or pull toward the historical template. Extra detail
preservation is not mandated; a user can add controls around a feature to edit it separately.

Hard targets: selected vertices equal Q; enabled unselected vertices equal P0. No-op
returns P0 and clears old preview motion. New deformation stays in currently affected
patches; cleanup stays in captured scope. These rules hold for every method.

No required formula says a patch midpoint moves half as far as a boundary. Whole Patch
and finite radius/profile may produce different interior responses. Inspect leg examples
in product/leg-control-examples.md before interpreting interpolation results.

The current Whole Patch (`Radius = 0`) implementation uses the operation rest
Source mesh for edge lengths. It blends transforms from selected control
groups once, then fades the resulting displacement between selected and fixed
control boundaries by their shortest metric paths. Thus an ordinary cylinder
with two control loops retains the original spacing ratios of its intermediate
rings when one loop moves. Every new operation starts from the current Source
coordinates; an already distorted model needs an explicit Reset Model if the
user wants to return to its Init pose. Finite radius uses a separate profile
and graph-distance response.

## Small displacement candidate for initial evidence

An additive test model keeps P0 and adds a control displacement field:

```text
D[i] = Q[i] - P0[i]   # selected or stationary enabled Source control vertex
P1[v] = P0[v] + A[v] * U[v]
```

A is the user proportional applied once, as defined in proportional.md. U is a technical
candidate, not a frozen product behavior. The old per-logical-component nearest-sample
blend is superseded: grouping identical control geometry must not change motion.

For a small pure-geometry experiment, test inverse-distance blending over unique enabled
Source control vertices, including stationary samples. For each non-control vertex v,
compute graph distance d(v,i) inside the patch to each sample i:

```text
eps = max(patch_bbox_diagonal * 1e-9, 1e-12)
r_i(v) = 1 / max(d(v,i), eps)^2
w_i(v) = r_i(v) / sum_j r_j(v)
U(v) = sum_i w_i(v) * D[i]
```

Deduplicate samples by persistent Source ID; ordering/group names do not add weight.
Only sample vertices belonging to this patch. Unreachable free components retain P0.
Without reachable finite samples, do not divide by zero or blend across components.
Free vertices outside finite radius retain P0 exactly; omit unnecessary interpolation
there. Distances come from immutable P0, never previous preview geometry.
Directly set all enabled control vertices to their selected/stationary targets afterward.
Check finite outputs, shared-boundary agreement and write mask before Source writes.

Build and validate complete output buffers before writing; leave no half-written patch
on error. Copy fixed P0 coordinates exactly instead of relying on attenuation alone.

This is a deliberately small test candidate, not a production solver decision. Pairwise
distances are expensive for dense controls; start with tiny fixtures, record memory/time,
and do not promise interactive dense-mesh performance. It can fail quality tests; record
that evidence rather than weakening hard-control behavior to make it pass.

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
