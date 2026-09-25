# H03 — Owned-object safety report

**Status: PASS for the H03 lifecycle safety gate.** Blender 5.2.1 LTS;
starting add-on commit `6664763`. All fixtures are disposable and run in a
factory-startup Blender process.

## Changes verified

- Load and depsgraph handlers no longer remove stale owned objects or their
  mesh datablocks. They mark the object for repair and clear the warning when
  its owner becomes resolvable again.
- The sidebar offers an explicit undoable unbind action. It clears DANP owner
  markers and parentage while preserving the object's mesh, local geometry and
  world transform.
- Duplicate binding behavior remains covered by the existing full-pair and
  mesh-only duplicate fixture.

## Evidence

- [PASS] `tests/live_owned_object_safety.py` — stale Controller/face helper
  survives load, undo and depsgraph handlers; both mesh datablocks and coordinates
  persist; explicit unbind keeps geometry and world transform; restored owner
  clears the stale warning without replacing the helper.
- [PASS] `tests/live_duplicate_bindings.py` — mesh-only/full-pair/Controller
  duplicates remain isolated and ambiguous/shared ownership fails closed.
- [PASS] Static check confirms lifecycle cleanup contains no object deletion
  and the explicit recovery operator is registered.
- [NOT RUN] Interactive Undo after clicking the recovery button in a 3D View.
  A background fixture has no native undo context; programmatic invocation
  from a GUI timer did not reproduce a real panel click, so it is not counted
  as evidence. The operator carries Blender's `UNDO` option.
- [PASS] `scripts/validate-docs.ps1` after regenerating the consolidated spec
  and SHA-256 manifests.

## Limits

The lifecycle deletion-safety gate passes. Interactive Undo remains a manual
UI check; this report does not certify all release matrix rows or the complete
release readiness of DANP Form.
