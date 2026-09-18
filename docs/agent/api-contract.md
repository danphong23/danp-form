# Agent API Contract

**Status: Logical contract; transport and exact signatures are implementation details**

```text
list_sources() / get_source(source_id)
list_controls(source_id) / get_proxy_geometry(source_id)
list_patches(source_id) / get_patch(source_id, patch_id)
get_control_visibility(source_id)
select_elements(source_id, node_ids=[], span_ids=[], control_ids=[])
begin_operation(source_id, selection, proportional, expected_network_revision)
translate(operation, delta, space)
rotate(operation, rotation, pivot, space)
scale(operation, scale, pivot, space)
set_knot_targets(operation, targets)
update_operation(operation)
commit_operation(operation) / cancel_operation(operation)

create_control_from_source_selection(...) / remove_control(...)
create_control(source_id, source_vertex_ids=[], source_edge_ids=[])
hide_control_elements(source_id, node_ids=[], span_ids=[], control_ids=[])
reveal_control_elements(source_id, source_vertex_ids=[], source_edge_ids=[], control_ids=[])
reveal_all_controls(source_id)
rebuild_proxy(...) / simplify_control(...) / refine_control(...)
```

Visibility queries enumerate hidden Source IDs even when those elements are not in the
visible proxy. Hide uses canonical masks and whole/partial selection semantics. There
is no separate set_control_active command: hide/reveal is the user-facing mechanism.

Node-only targets select only bound vertices; span transforms select represented dense
geometry. Queries report current Source positions, effective enabled network and its
revision. Hidden direct edit requests return CONTROL_HIDDEN. Stale generation/network
requests fail before Source writes. Only one deformation transaction owns a Source.

Results report status, changed vertex count, warnings and Source/network revision.
Hide/reveal returns zero coordinate changes and invalidates scope. Human and agent
use the same targets, constraints and interpolation, including shared-vertex priority.

Bind operation handles to Source UUID, topology fingerprint/generation, network revision,
proxy generation and owner token; check on every action. Rebuild can invalidate old
node/span handles without changing the effective network. Queries return revisions,
current positions and Source-scoped IDs.

Transforms are absolute relative to operation start: repeating a delta does not accumulate.
Explicit updates must resolve the complete selected target set; reject missing/extra or
non-finite IDs instead of guessing. Node-only convenience calls have node-only selection.
NO_CHANGE is a successful identity result; busy/closed/invalid requests use stable errors.

Hide/reveal reports changed masks, released/retained junctions and network revision,
with zero Source coordinate change. Unchanged repeats do not increment revision.
Queries never start a deformation transaction or write Source coordinates.

## Delivery in the five-phase roadmap

Phase 2 implements control creation/masks/rebuild as shared internal primitives.
Phase 3 supplies derived patch queries. Phase 4 provides a minimal numeric facade
for the same transaction/targets as UI; phase 5 verifies it through actual MCP.
Source-ID-based create_control avoids requiring an agent to manipulate UI selection;
it resolves the same source-backed definition as Create from Source selection.
Patch IDs are derived handles tied to topology/network revision, not permanent IDs.
Source state is revalidated before operations; agents must requery after rebuild or
structural changes. Exact public Python/operator signatures are documented from the
implementation at handoff, not inferred from this logical list.

Simplify/refine and sparse-span APIs are optional extension capabilities. Advertise
what the installed build supports; unsupported capability requests return a clear
error rather than silently succeeding. Reference-based testing in phase 5 supplies
ordinary targets, with no additional mesh-write API or reference solver.
