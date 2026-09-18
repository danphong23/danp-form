# Selection and Control Targets

**Status: Normative**

Select control geometry as on a mesh: a vertex, a strip of vertices, an edge/span,
a loop, or multiple elements. A named definition is only a selection shortcut.

## Resolve selection

1. Snapshot the enabled network and current Source P0.
2. Node selection resolves to those Source vertices only.
3. Selected edges/spans select all represented enabled Source vertices in those spans.
4. Loop/whole-control selection is the union of its enabled nodes/spans. Hidden segments stay excluded; selection does not silently reveal them.
5. Deduplicate by Source ID. Selected span endpoints count as selected even without endpoint knot flags. Unselected neighboring spans do not become selected.
6. Resolve one target per selected vertex. Every other enabled control vertex gets stationary target Q[i]=P0[i].

Hidden geometry contributes neither targets nor stationary constraints. Explicit edit
requests for hidden elements return CONTROL_HIDDEN; reveal in a separate command.

## G/R/S targets

From the operation-start transform, pivot and orientation:

```text
Q[i] = T(P0[i])  for resolved selected Source geometry
Q[i] = P0[i]     for all other enabled Source control vertices
```

A selected coarse edge transforms the existing dense curve, not a reconstructed chord.

Targets are Source-local. Convert world/orientation operations through the captured
object transform; do not assume local/world axes match. Reject singular/non-finite
transforms. Freeze the frame so equivalent human/agent targets have the same meaning.

## Knot-only selection, including sparse mode

Only the knot's bound vertex moves. Omitted enabled vertices between knots remain
stationary; do not implicitly generate moving targets for them. To move more of a
line, select its strip/span/loop. To let it follow mesh deformation, hide it first.
This supersedes the previous automatic sparse-knot displacement-expansion exception.

## Numeric/agent parity and conflicts

Explicit targets obey the same selection and Source IDs. Node-only calls do not infer
a transform for intermediate vertices. Rotate/scale a selected span using a transform
call, or supply targets for every selected dense vertex. Span coverage is explicit
selection, not proportional falloff.

At a junction, selected targets win over stationary membership. Incompatible selected
targets return TARGET_CONFLICT regardless of order. No generated moving target is
allowed outside the selected Source geometry.

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
