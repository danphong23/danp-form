# Selection and Control Targets

**Status: Normative**

Select control geometry as on a mesh: a vertex, a strip of vertices, an edge/span,
a loop, or multiple elements. A named definition is only a selection shortcut.

## Resolve selection

1. Snapshot the enabled network and current Source P0.
2. Node selection resolves to those Source vertices only.
3. Selected edges/spans select all represented enabled Source vertices in those spans.
4. Loop/whole-control selection is the union of its enabled nodes/spans. Hidden segments stay excluded; selection does not silently reveal them.
5. Deduplicate by Source ID. Selected span endpoints count as selected even without endpoint knot flags. Unselected neighboring spans do not become selected at operation start.
6. The initial selection starts Blender's native transform. During each preview sample,
   compare every Controller vertex with its pre-transform pose. Every ID whose
   coordinate changed is an exact target, including unselected vertices moved by
   Blender Proportional Editing. Enabled control vertices that did not change are
   stationary for that sample.

Hidden geometry contributes neither targets nor stationary constraints. Explicit edit
requests for hidden elements return CONTROL_HIDDEN; reveal in a separate command.

## G/R/S targets

From the operation-start transform, pivot and orientation, Blender produces the live
Controller coordinates. DANP resolves targets from the changed-coordinate set:

```text
Q[i] = Controller[i] for every moved Controller vertex
Q[i] = P0[i]         for every enabled Controller vertex that did not move
```

A selected coarse edge transforms the existing dense curve, not a reconstructed chord.

Targets are Source-local. Convert world/orientation operations through the captured
object transform; do not assume local/world axes match. Reject singular/non-finite
transforms. Freeze the frame so equivalent human/agent targets have the same meaning.

## Knot-only selection, including sparse mode

Without Blender Proportional Editing, only the selected knot's bound vertex moves.
With Blender Proportional Editing, omitted enabled vertices may also move; DANP
detects their changed coordinates and treats them as targets. To move more of a
line deliberately, select its strip/span/loop. To let a line follow mesh
deformation, hide it first.

## Numeric/agent parity and conflicts

Explicit targets obey the same selection and Source IDs. Node-only calls do not infer
a transform for intermediate vertices. Rotate/scale a selected span using a transform
call, or supply targets for every selected dense vertex. Span coverage is explicit
selection, not proportional falloff.

At a junction, moved targets win over stationary membership. Incompatible moved
targets return TARGET_CONFLICT regardless of order. No generated moving target is
allowed outside the current Controller mapping.

Validate target count, finite values, Source-scoped IDs and selection membership before
writes. Do not discard unknown IDs/malformed partial payloads silently. Validate explicit
hidden-element requests before filtering: whole-definition selection can skip hidden
portions, but explicit hidden nodes/spans return CONTROL_HIDDEN.

A junction included in any selected span is selected; neighboring spans remain unselected
except that endpoint. Names never decide priority. Targets do not need front/side modes.

## No-op

All selected Q equal P0 means unchanged Source. Such targets are not nonzero influence
sources. Numerical comparison tolerance is a prototype parameter, not permission to
move unselected enabled control vertices.

After an earlier nonzero preview, no-op must restore previous writes to P0. Early-out
skips solving, not cleanup; see operation-semantics.md.
