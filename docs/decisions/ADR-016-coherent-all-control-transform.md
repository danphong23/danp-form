# ADR-016 — One affine transform when every control is selected

**Status: Implemented, 2026-09-25**

## Problem

The Controller is split into face patches by control edges. A native Scale of
every enabled Controller vertex is one coherent transform, but each patch was
fitted independently. Near-planar rings do not determine motion along their
normal, so free vertices in those patches could scale less than the rest of the
mesh. The fixed `1e-6` sample residual threshold was smaller than Blender's
float32 coordinate noise on the current head; successive mouse samples switched
different patches between affine and harmonic interpolation.

On `girl chibi test | Head` (1,072 Source vertices, 134 selected Controller
vertices, 10 patches), a read-only simulated Scale at factor 0.5 had up to
1.104673 Source-local units of error against a whole-mesh Scale. Across tested
factors, between 3 and 10 patches switched to harmonic interpolation.

## Decision

When every enabled Controller vertex was selected at operation start, there are
no stationary control vertices, the DANP proportional radius is zero, and the
measured targets fit one affine transform, apply that transform once over the
operation's captured affected-patch scope. Exact measured control targets still
override the fitted positions. An unchanged target set returns P0 exactly.

The fit check allows eight float32 units of precision at the largest sample
coordinate, with a `1e-7` floor. If targets are not coherent, retain the
existing patch-local constrained solve. Partial selections, stationary
controls, finite proportional radius, topology boundaries, and Shape Key
writeback keep their existing behavior. This adds no persistent state or new
solver family.

## Evidence and verification

The same read-only head simulation gave a maximum error below `0.0000022`
for uniform Scale, non-uniform Scale, rotation, and translation after the change.
Across 20 uniform Scale samples, numerical-only median/P95 time changed from
26.39/29.89 ms to 8.91/9.28 ms in Blender 5.2.1 on the current head.
Regression tests cover separate near-planar patches, float32 target rounding,
consecutive Scale factors, exact no-op, and existing fixed/partial controls.
