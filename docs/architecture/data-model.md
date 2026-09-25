# Data Model

**Status: Normative semantics; storage layout is an implementation detail**

```text
SourceRecord
  template_uuid / schema_version
  topology_generation / control_network_revision / source_revision
  validated_topology_fingerprint
  next_vertex_id / next_edge_id / optional next_face_id
  controls[]
  hidden_source_vertex_ids[] / hidden_source_edge_ids[]
  proxy_object_reference
  optional_original_snapshot

ControlRecord
  control_uuid / optional name
  components[]

ControlComponent
  component_uuid / kind: POINT | CHAIN | LOOP | NETWORK_BRANCH | SET
  source_vertex_ids[] / source_edge_ids[]
  ordered_source_vertex_ids[]  # where ordered topology is defined
  proxy_knots[] / proxy_spans[]

Operation
  source_uuid / topology_generation_at_start / network_revision_at_start
  captured_deformation_target / target_revision_or_signature
  proxy_generation_at_start / captured_transform_frame
  P0 / proxy_start_state / resolved_selected_source_ids / enabled_network_snapshot
  captured_patch_scope / current_affected_patch_ids / dense_target_set / proportional_settings
  owner_token / state: ACTIVE | COMMITTED | CANCELLED
```

Hide masks are canonical Source element state, not per-membership active flags.
Definitions and masks persist; enabled network/patches/proxy caches are derived.

Proxy object parent is Source; matching local coordinates avoid double transforms.
Show Patches is display state, not control/mask/constraint state. Derived patch
membership/overlay buffers are rebuilt, not stored as geometric truth.
Shared vertices/edges are deduplicated before target generation and interpolation.
Source IDs live in the Source namespace; agent element keys must include Source UUID.

Hide/reveal, definition edits and proxy span changes invalidate relevant generations.
Runtime operation snapshots are not persistent project truth. Preserve masks on rebuild,
save/load and independent duplication. If migrating earlier active=false definitions,
translate their geometry into canonical hidden masks and validate overlaps; do not leave
a second runtime activation system. No released-code compatibility is implied yet.

`captured_deformation_target` denotes the base mesh or a specific Source Shape Key.
It is fixed for one transaction under ADR-015; H01 specifies stable identity and
failure behavior, and H02 consolidates target-specific I/O. It does not add a
second persistent geometry store or change Source-backed control IDs.

Network revision changes on definition/mask edits; proxy generation changes on rebuild
or representation edits, not previews. Source revision tracks DANP Form commits, not
external edits: always validate topology and resample at boundaries. Undo/load clears
caches even when revisions repeat. No-change commands do not advance revisions.
