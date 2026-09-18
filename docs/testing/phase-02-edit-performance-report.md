# Phase 2 — Edit Mode performance and front contours, 0.2.3

**Status: PASS for these scoped fixes, 2026-09-18.**

## Live session and cause

Blender 5.2.1 LTS, installed `bl_ext.user_default.dan_form`, Layout, already-open
`C:/Users/abc/.AI/Code/danp-animation/Project/2. toon/girl_chibi_1.blend`.
Preflight active object was `girl chibi 1` in Object Mode with 37 definitions;
Source has 1,698 vertices, 3,392 edges and 1,696 faces. Cube has 8 vertices,
12 edges, 6 faces and 6 definitions. Exactly one addon depsgraph handler was present.
Dirty was true before and after. No separate Blender process, scene builder,
file save/reopen or discard was used.

The 0.2.2 implementation resolved each edge endpoint repeatedly through
`_source_vid`, and each coordinate through `_source_co`. Profiling one network
query and one list projection recorded 3,632 per-vertex ID reads with 0.226 seconds
cumulative time. Network union was recomputed during every Source overlay redraw,
which also rebuilt world positions, shaders and GPU batches. More definitions and
overlap amplified this cost; it was measurable on this modest mesh.

## Fix

Source mapping now reads index-to-ID and edge-to-endpoint-ID tables once per
mapping build. Connectivity contains copied IDs, not retained BMesh handles.
Consumers borrow a vertex sequence for one synchronous coordinate read, instead
of acquiring Edit data once per point. Effective union caches are tied to their
mapping instance and canonical definitions/masks; callers receive list copies.

The overlay retains its shader and position batches across idle redraw. Geometry
events, proxy rebuild, model/controller context, canonical masks, selected UUID,
Show Hidden and world transforms invalidate position data. Runtime refresh and
unregister release caches. Width/X-Ray change drawing state and reuse buffers.
Controller Edit returns before geometry/GPU access. Explicit point definitions
keep visible point markers even when sharing a vertex with an edge control;
edge endpoints no longer receive large auxiliary dots.

## Measurements

All numbers are synchronous Python timings in Source Edit Mode, not total input
latency or viewport FPS. Before medians used three calls; after timings used warm
medians of 10 calls on the same 37-definition model, then 15 on the final model.

| Operation | 0.2.2, 37 definitions | 0.2.3, same 37 | 0.2.3, final 50 |
| --- | ---: | ---: | ---: |
| Effective network | 228.029 ms | 0.0956 ms | 0.2373 ms |
| Unchanged proxy sync | 52.528 ms | 0.7810 ms | 1.4272 ms |
| Valid topology guard | 0.869 ms | 0.6759 ms | 1.4787 ms |
| Forced list projection | 228 ms profiled | 1.0971 ms | 2.3300 ms |
| Overlay position collection | not isolated before | 0.5565 ms before point-marker refinement | 2.7920 ms |
| Cached GPU buffer access | rebuilt each redraw, not separately timed | 0.0122 ms | 0.0132 ms |

The final character proxy has 824 vertices and 924 edges. A separate sidebar
regression measured idle mapping/list at 0.0016/0.0039 ms and eye operators at
42.317 ms per operation across the final three Hide/Reveal pairs. Eye actions still rebuild
the proxy legitimately; those costs are distinct from idle redraw.

## Verification

[Cache/display regression](../../tests/live_edit_performance.py) passed 28 checks
using a removable fixture in this same scene. Actual geometry events verified
Source BMesh positions, proxy sync and GPU invalidation; idle calls retained buffer
identity and never called the position builder. Coverage includes explicit point
highlight, canonical shared-point hiding, Show Hidden without mask mutation,
Reveal, object transforms, controller Object pose, Controller Edit suppression,
and runtime cache refresh. Test controls and meshes were removed in `finally`.

[Lifecycle regression](../../tests/live_controller_lifecycle.py) passed all 37
checks, including native topology edits/recovery and full removal. The existing
50-definition character then passed all 34
[sidebar regression](../../tests/live_sidebar_regression.py) checks, with Source
definitions/masks/coordinates and controller pose/selection restored. Another 34
[segment/visibility checks](../../tests/live_control_segments.py) passed on removable
crossing-lines and closed-loop fixtures. Final total: 133 checks, covering span stops,
additive selection, edge/node Hide intent, partial eyes, selective reveal, scoped keys
and Hide/Show All even on an empty controller in Edit Mode.
The user's Source and Cube topology, coordinates and transforms remained
unchanged; all original definitions survived.

Computer Use selected the returned Blender window, focused the model viewport,
entered Source Edit with Tab, clicked Edit Control and Back to Model. Screenshots
confirmed Source Edit, actual controller Edit with no auxiliary colored layer,
and return to Source Edit. The original model Object Mode and mesh selection were
restored through MCP afterward. The full character was framed in the existing
front orientation for review. This proves those UI transitions, not a measured
native input-latency/FPS threshold or a modal deformation test.

Final Computer Use verification focused the actual controller viewport and pressed
H on 24 selected front-foot edges. MCP confirmed canonical masks 24E/0V, the eye
Hidden and Controller Edit retained. Alt-H restored masks 0E/0V and eye On.
Original Source selection, masks/revision and the user's Source Edit Mode were
restored. The projected-edge picking branch was exercised through a real View3D
context with a synthetic event; physical Ctrl+Alt+mouse dispatch was NOT RUN.

Syntax/static contracts, documentation links/hashes, installed-source consistency
and extension ZIP contents were checked before commit.

## Front outline scene data

The earlier 37 definitions captured anatomical rings and longitudinal handles;
they omitted substantial front contours, particularly head, ears and fingers.
The live character now has 13 additional logical groups:

- `Front.Outline.All` for selecting the complete contour set.
- `Front.Head.Outline` and `Front.Ear.Outline.L/R`.
- `Front.Body.Outline`.
- `Front.Arm.Outline.L/R` and `Front.Hand.Outline.L/R`.
- `Front.Leg.Outline.L/R` and `Front.Foot.Outline.L/R`.

These Source-backed definitions cover all 498 base-mesh edges where neighboring
face normals change front-facing sign for the current front view. Their regional
union equals the whole group, including finger contours. Logical groups may
contain multiple paths/loops or junctions; grouping does not add a constraint
hierarchy. Original 37 definitions, identities and geometry remain intact; Cube
retains its existing six controls. `Front.Outline.All` is active for review.

This is a setup of the current scene, not a newly shipped automatic silhouette
feature. Facing-sign contours can include overlapping/occluded paths and follow
base mesh topology; they are not an exact visibility-filtered boundary of the
Subdivision render. No extra mesh vertices were introduced for fitting.

## Limits

NOT RUN: interactive undo/redo and file reopen, physical Ctrl+Alt+mouse dispatch, sustained
large-mesh FPS, modal transform movement/cancel, exact rendered-silhouette
visibility extraction and Phase 4 patch deformation. Cache refresh hooks were
tested directly; that is not evidence of interactive undo/redo. The scene remains
unsaved so the user can review the added definitions before saving.
