# All-control Scale stability audit — 2026-09-25

## Reproduction on the open head

The active `girl chibi test | Head` has 1,072 Source vertices, 134 enabled
Controller vertices, 10 face patches, and all 134 Controller vertices selected.
Its DANP proportional radius is zero. Read-only calculations using the open
model's actual patch graph and Source coordinates reproduced the reported
behavior: a uniform Scale factor of 0.5 left some Source vertices as much as
1.104673 Source-local units away from the whole-mesh Scale result. During a
series of Scale factors, 3–10 patches changed from affine fitting to harmonic
interpolation because the old fixed `1e-6` target tolerance was below float32
coordinate noise for this mesh. A planar control loop also leaves its normal
direction underdetermined when fitted in isolation.

## Repair

If every enabled Controller vertex belongs to the captured selection, no
stationary control remains, proportional radius is zero, and the measured
targets fit one affine transform, use that transform for the entire affected
patch scope. Preserve each exact measured control position. Use a tolerance
derived from Blender's float32 coordinate precision for affine target checks.
Unselected controls still anchor their patches. Incoherent targets retain the
constrained solve. A returned-to-rest operation remains an exact no-op.

## Verification

- Read-only calculations on the current head: maximum error below 0.0000022
  Source-local units for uniform Scale, nonuniform Scale, rotation and
  translation. Across 20 uniform Scale samples, numerical-only median/P95
  computation time was 26.39/29.89 ms before and 8.91/9.28 ms after.
- Pure Python suite: 59 checks passed, including consecutive float32 Scale
  samples, exact no-op, stationary controls, partial selections and finite
  proportional radius.
- Blender 5.2.1 background two-patch fixture: six consecutive Scale samples
  passed; maximum Source error 0.00000191. It also restored the fixture Source
  after cancellation.
- Blender 5.2.1 background Shape Key, duplicate ownership, Controller
  lifecycle, sidebar regression and deformation fixture suites passed. The
  sidebar suite was corrected to re-read control definitions after Hide/Show;
  its previous assertion inspected stale in-memory copies of those definitions.
- Installed extension 0.5.31 in the open Blender. Read-only recalculation on
  the same head at Scale factors 0.98, 0.7, 0.5 and 1.0 showed maximum error
  0.000001912 and an exact no-op at 1.0. The Source still had 1,072 vertices,
  the Controller still had 134 selected vertices, and the scene stayed in
  Controller Edit Mode.

The background Blender transform operator did not move Controller geometry in
the saved-file probe, so a physical modal mouse Scale in the open UI was not
verified here. The open user scene was only read and was not saved by these
checks. It was dirty at the first diagnostic read and clean at the final
installation check.

The historical Phase 2 selection suites are not valid release gates for this
build: they call selection operators and a scene property that have not been
registered since the later Controller UX refactor. The patch overlay suite
also needs a GPU-backed UI context and cannot run in background Blender.
These gaps are separate from the Scale calculation and remain visible rather
than being counted as passes.
