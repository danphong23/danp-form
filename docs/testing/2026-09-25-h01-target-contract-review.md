# H01 review — Deformation Target contract

**Date:** 2026-09-25. **Starting commit:** `e7051dd`.
**Scope:** documentation and source review only; Blender scene and add-on Python
were not modified. H01 is a contract gate, not a runtime feature gate.

## Source inventory and decision trace

| Concern | Current code path | H01 decision and following gate |
| --- | --- | --- |
| Target discovery | `blender.mesh._active_shape_key`, `_shape_key_signature` | `BASE` only without keys; otherwise active KeyBlock, Basis included; identity guard in ADR-017; H02 |
| Controller resync | `operators.DANFORM_OT_select_shape_key`, `DANFORM_OT_focus_controller`, `blender.proxy` | Idle target switch resyncs proxy; structural command; H05 |
| P0/preview/cancel | `blender.workflows.deform_begin/update/cancel` | Captured target and immutable P0; no redirected write; H02/H04 |
| Source Edit Mode | `blender.selection._source_positions`, `blender.workflows.write_source_positions` | Explicit target must match live BMesh or use safe path/refuse; current path is a known gap; H02 |
| Native Undo/Redo | `blender.lifecycle._restore_native_undo_records` | Historical captured target, never current active key by convenience; H02 |
| Reset Model | `operators.DANFORM_OT_reset_source`, Init snapshot name | Name-only match is insufficient provenance; H02 |
| UI display/lock | `operators.DANFORM_OT_select_shape_key`, `focus_controller`, `show_only_shape_key` | Active key as single selection; show-only may change, values/mute may not; H05 |
| New Shape Key | No DANP creation command in current build | Explicit idle command copies selected target's stored coordinates; H05 |
| Agent | `dan_form.agent` transaction facade | Same target resolver and statuses; list/select target missing; H06 |
| Duplicate/topology | Source ownership and fingerprint adapters | Target owner and count participate in validity; no cross-object write; H02/H07 |

The outside proposal's useful target abstraction is adopted as an adapter
boundary. Its proposed relative-only first release and setting key values to
isolate a target are not adopted: ADR-015 already accepts relative and absolute,
and display isolation must preserve animated values/mute. `Save As Shape Key`,
corrective drivers and multi-object operations remain outside H01–H10.

## Contract review

- [PASS] ADR-017 distinguishes base mesh, Basis, relative and absolute key.
- [PASS] Target owner/identity and fail-closed behavior are explicit; name/index
  alone cannot authorize historical writes or Reset.
- [PASS] Adapter boundary leaves the core solver target-agnostic and keeps one
  Source-owned control network and patch graph.
- [PASS] UI and agent selection, lock/display behavior and error statuses point
  to the same contract.
- [PASS] New Shape Key copies the selected target's stored coordinates and
  preserves animation state; it is a separate H05 structural command.
- [PASS] [T01–T16 matrix](deformation-target-matrix.md) assigns runtime
  scenarios to H02/H04/H05/H06/H07, including untouched-key assertions.
- [NOT RUN] Blender runtime fixtures and physical modal UI checks; their gates
  belong to H02–H06 and cannot be inferred from this document review.
- [PASS] `scripts/validate-docs.ps1`: 71 consolidated modules, 98 documents;
  local links and both documentation hash manifests consistent. Staged diff
  whitespace validation is recorded at commit time.

**H01 handoff:** ADR-017 and the target contract are accepted for implementation.
The first code phase, H02, must fix explicit target I/O and provenance before
any target workflow is considered release-safe.
