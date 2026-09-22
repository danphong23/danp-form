# Proportional Semantics

**Status: Normative role and placement; exact default/profile set remains open**

Within already affected patches, proportional governs how moved control vertices
spreads into mesh interiors. It does not select patches, release enabled controls,
or define new control targets. Current patch shape is the deformation baseline.

The additive candidate computes U then applies the user's profile once:

```text
P1(v) = P0(v) + A(v) * U(v)
```

For finite radius R > 0, use shortest rest-edge metric distance inside
the patch from nonzero moved targets:

```text
x(v) = clamp(1 - d_move(v)/R, 0, 1)
A(v) = profile(x(v))
```

Whole Patch uses A=1 within affected scope, not across enabled cuts. Enabled stationary
vertices remain exactly P0 regardless of radius. Moved targets remain exactly Q.
Hidden vertices are attenuated like ordinary mesh vertices and may remain unchanged
outside radius. Zero/negative/non-finite radius requests must be rejected or represented
as an explicit separate mode; do not divide by zero.

Initial candidate profiles are dimensionless, with profile(0)=0, profile(1)=1 and range
[0,1]. Phase 4 compares LINEAR x, SMOOTH x*x*(3-2*x), and a uniform attenuation
candidate: A=1 for d_move < R, A=0 for d_move >= R. Uniform finite-radius attenuation
has a discontinuity at R; review its visual behavior, not assume it is the default.
Whole Patch uses constant A=1 without a radius cutoff. These describe attenuation,
not identical interior displacement or release of fixed controls. Shipping set and
default remain open. Radius/distances use Source-local Operation Rest units. A
world-space UI must convert or document its metric, particularly for nonuniform object
scale; do not silently mix units.

Radius/profile changes recompute from P0 and clear old motion outside new influence.
No nonzero targets means P0 output; do not compute distances to an empty moving set.
Moved control vertices still receive Q.

No fixed midpoint motion or mandatory affine deformation follows from choosing a
profile. Prototype comparisons must use identical targets/constraints while changing
profile/radius. Numerical influence method and quality require evidence.

Blender's native Proportional Editing may move enabled unselected Controller
vertices. DANP accepts those coordinates as exact targets by comparing the whole
proxy with its pre-transform pose. DANP's own Radius/profile then controls how the
resulting moved targets influence free Source vertices inside the affected patches;
it does not override Blender's proxy falloff. Sparse representation adds no second
user proportional.
