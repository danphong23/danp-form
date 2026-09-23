# Blender Integration Test Cases

**Status: Required progressively in phases 1–5; deformation follows pure geometry gates.**

## Early integration — phases 1–3

- Install/register/unregister, sidebar context and repeated Initialize → one controller per Source, no duplicate handlers/keymaps.
- Controller parented to Source with matching local frame → Source object move/rotate/nonuniform scale follows exactly once, no geometry edit.
- Save/load/undo initialization, create/remove/hide/reveal → bindings, definitions and masks survive.
- Source coordinate edits in Object/Edit Mode → displayed controller refreshes; command boundaries still validate mapping.
- Patch overlay toggle → no Source-coordinate, network-mask, revision or partition change.
- Whole/partial control Hide → patch graph recalculates from effective edges, not an assumed two-patch merge.

## Deformation and lifecycle — phase 4

- Register Source → persistent IDs survive save/reload.
- Make Control from Source selection → Source-owned definition and Proxy agree.
- Delete Proxy → rebuild yields equivalent bindings and does not alter Source coordinates.
- Coordinate-only Source edit outside DANP Form → visible Proxy refresh plus revalidation/resync at the next operation.
- Destructive topology change → stale mapping detected; deformation blocked.
- Transform preview → every mouse/numeric update uses immutable `P0`.
- Normal cancel with unchanged identity/topology → exact operation-start Source/Proxy restored.
- Confirm changed geometry → one logical undoable operation; identity confirm → successful NO_CHANGE without a meaningful extra undo edit.
- Two independent Sources in one scene → context never crosses.
- Duplicate only a Source mesh → the copy is marked unbound, has no active controls,
  and Initialize gives it a fresh empty namespace without changing the original
  Source coordinates, controls, UUID, Controller, or proxy pose.
- Duplicate a complete Source/Controller pair while the original pair is registered
  → reconcile from direct parentage, assign a fresh UUID to the new pair, preserve
  its local definitions/IDs, and confirm that edits on either pair leave the other
  pair unchanged.
- Duplicate only a Controller → the original remains the sole bound child; the
  extra object becomes unbound with its visible transform preserved.
- Load a file containing ambiguous duplicate pairs or multiple marked Controller
  children → all ambiguous writes fail closed; explicitly choosing a pair resolves
  the collision without changing either mesh's coordinates.
- Alt+D/shared Source or Controller mesh data → DANP rejects writes before either
  object changes; Make Single User allows independent registration.
- Delete/reset/undo/redo and agent UUID lookup with mesh-only or full-pair copies
  → no first-match binding, cross-pair cleanup, stale cache reuse, or Source change.
- Hide/reveal whole or partial control → zero Source coordinate change; masks and patch connectivity update together.
- Hidden contour deforms with Source → reveal follows the committed positions, including after rebuild/save/reload.
- Hide/reveal undo/redo → exact masks restored, caches invalidated, no extra recovery undo entry.
- Shared endpoints/overlapping definitions → no hidden duplicate constraint; selected junction wins over stationary membership.
- Optional sparse refine/rebuild (future extension / Gate E) → preserves hide masks and enabled stationary dense vertices; not a core-roadmap prerequisite.
- Network state change during transform/stale agent request → block stale writes; topology changes never restore through invalid indices.
- Concurrent transactions on one Source → second owner rejected.
- Move preview → return targets to P0 / shrink radius → all previous preview writes reset correctly before confirm/cancel.
- Hide whole edge-backed D → shared U/L junctions stay enabled; explicit node Hide releases incident edges.
- Equivalent local/world targets on transformed objects → same Source-local result; singular transform rejected.
- Same counts but changed face connectivity / duplicated element IDs → fingerprint/mapping validation blocks stale edits.
- Rebuild generation / closed operation token / second commit → no stale handles or repeated writes.
- Shape Keys, Multires, shared editable and read-only data → explicit prototype rejection before writes.
- Full Source/Controller pair duplicate → new Source UUID/proxy and local IDs/masks
  preserved without cross-control. A mesh-only duplicate starts unbound and clean.

## User/agent validation — phase 5

Agent parity (Phase 5 / Gate F): human numeric G/R/S and equivalent agent action produce
the same targets/Source result; equivalent whole/partial hide/reveal produces the same masks.

Actual MCP must execute shared facade commands on a dedicated test file. Human and
external agent also create controls and adjust them against front/side reference.
Use Computer Use to inspect sidebar/selection/overlay/modal behavior when testing UI;
numeric queries establish coordinate assertions. Reference workflow quality is reviewed
separately from parity on equivalent targets. Test stale/busy/closed/retry paths and
report unavailable transport as BLOCKED, not PASS.
