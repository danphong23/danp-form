# Control Model

**Status: Normative — clarified with the product owner on 2026-09-18**

## Geometry, not named roles

Controls are real Source vertices/edges with persistent definitions. Points, chains,
loops, disconnected sets and intersecting networks are interaction shapes. Names and
groups are selection conveniences, not front/side/anatomy roles or independently
weighted deformation components. The same effective network and targets must produce
the same result regardless of how definitions are named/grouped.

One rebuildable proxy per Source exposes geometry for selection and transforms.
Create/remove structure through DANP Form commands, not arbitrary proxy topology edits.

## Enabled control

An enabled control vertex changes only through explicit selection on the control.
Every enabled vertex outside the resolved selection stays exactly at Operation Rest.
It cannot be dragged along by another selected control or patch interpolation.
Enabled edges contribute to topology cuts even when their endpoints are selected.

A selected proxy span represents its entire stored Source span: those dense vertices
are selected geometry too. A knot-only selection does not select neighboring spans.

## DANP Form Hide and Reveal

One user-facing state: enabled or DANP Form-hidden. Hide releases hidden geometry from
both stationary constraints and topology cuts, without deleting Source elements or
definitions. Reveal restores those roles at current Source positions, never old ones.

Hide/reveal works on a whole definition or selected points/edges/spans. Hidden vertices
follow ordinary mesh deformation inside affected regions; they are not guaranteed to
move, because proportional and other enabled constraints still apply.

No control parenting, nested patch ownership or separate deactivate feature is needed.
Object/collection hiding only changes display; it is not DANP Form Hide Control.
Proxy H/Alt-H may be bound to DANP Form commands when the tool owns the context.

## Canonical masks and shared endpoints

Store hidden Source vertex IDs and edge IDs once per Source network, not per logical
membership. Hiding an overlapping edge must not leave another invisible membership
constraining it. Commands use Source IDs independent of proxy resolution.

- Hide nodes: mark the represented vertices hidden; their incident control edges become ineffective.
- Hide edges/spans: mark represented edges hidden. Endpoints remain enabled when supported by another effective edge or an unhidden standalone point/set control.
- Hide whole edge-backed definition/loop: hide its represented edges, not all endpoint nodes. This preserves junctions supported by other enabled lines. For standalone point/set components, hide their represented nodes. Mixed components use the union of these intents.
- In edge mode, selecting an edge does not turn its endpoint selection flags into extra Hide Nodes requests. Mixed explicit node/span requests are a union; only explicit node intent hides nodes. The same rule applies to numeric/agent commands.
- Effective edge: a defined control edge, not edge-hidden, with neither endpoint node-hidden.
- Effective vertex: not node-hidden and supported by an effective edge or an unhidden standalone point/set control. Vertices supported only by hidden edges are released.
- Reveal nodes clears their node masks; independently edge-hidden edges stay hidden.
- Reveal edges/spans clears their edge masks and endpoint node masks to make requested geometry usable.
- Reveal whole definition clears its represented edge/node masks; Reveal All clears all masks.

Recompute the effective network/display after every state change. Shared endpoints
still supported by enabled geometry remain available. To release them too, hide nodes.

Node masks are global: hiding a junction node releases all incident lines at that node.
Revealing an edge clears endpoint node masks, so other edges disabled only by those
node masks can become effective too. Independently edge-hidden branches stay hidden.
This is shared Source geometry, not per-control ownership; UI preview and agent results
should report the resulting effective geometry rather than promise an isolated change.

Hide/reveal is idempotent. Repeating the same command without changing masks creates
no extra state revision or meaningful undo step. It never stores a pre-hide shape.

New definitions default enabled only where canonical masks already allow them: creating
an overlapping definition must not silently reveal previously hidden geometry. Remove
definitions without deleting Source topology; retain masks for elements still defined
elsewhere and prune masks for elements no longer in the defined network.

## Junction target priority

There is one position per Source vertex. A selected target wins over an unselected
membership at that same point. Other vertices on the unselected line remain fixed.
Two incompatible selected targets return TARGET_CONFLICT; do not average them.
Hiding one branch does not release a junction still supported by an enabled branch.

## State lifecycle

Hide/reveal is an undoable structural operation. Invalidate patch/constraint/distance
caches and resync proxy without deforming Source. Persist masks through save/load and
rebuild. Freeze the effective network during deformation: finish/cancel before hiding
or revealing. Stale requests must not reuse old patch scope.
