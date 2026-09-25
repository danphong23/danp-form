# Deformation Target verification matrix

**Status: H01 design review complete; runtime checks are NOT RUN for this phase.**
Each row is a required follow-up fixture or UI check. `Unchanged` means compare
actual stored coordinates and animation settings, not only the viewport image.

| Case | Setup/action | Required result | Phase |
| --- | --- | --- | --- |
| T01 | Mesh without keys; deform, cancel, commit, Undo/Redo | Only base vertices change; P0/cancel exact | H02 |
| T02 | Basis plus two relative keys; edit Basis | Only Basis coordinates change; other key blocks/values/mute unchanged | H02 |
| T03 | Select relative expression key; deform/Undo | Only selected key changes; controller follows that key | H02, H05 |
| T04 | Absolute stack; select a non-Basis key; deform/Undo | Only that KeyBlock's stored coordinates change; mode/evaluation time unchanged | H02, H05 |
| T05 | Source Edit Mode active on A; explicit historical read/write B | B is addressed exactly or request fails before write; A unchanged | H02 |
| T06 | Rename/reorder/delete/replace captured key during operation | No new writes to any other key; safe cancel only if original identity proven | H02 |
| T07 | Lock active key before begin; lock after preview | Begin rejects; active preview restores only proven original target | H02, H04 |
| T08 | Switch active key during native G/R/S | Operation stops and old target restores if safe; no write to new key | H02, H04 |
| T09 | Undo/Redo while a different key is active or Source in Edit Mode | Historical target only, or stable fail before write; current key unchanged | H02 |
| T10 | Init snapshot; rename/replace original key; Reset Model | Restore only with proven target provenance; otherwise refuse without writes | H02 |
| T11 | Toggle Controller Edit and target selector | Panel reflects Source active key; proxy matches key; prior show-only state restored | H05 |
| T12 | Key has animated value/mute/driver; enter/exit Controller Edit | Values, mute, keyframes, drivers unchanged | H05 |
| T13 | Create new Shape Key from BASE, Basis, relative and absolute active key; save/reopen/Undo | New stored coordinates equal selected target, Basis added first if needed; animation/mode/evaluation time unchanged; control definitions/IDs shared | H05 |
| T14 | Agent list/select/edit key via MCP; compare UI | Same target, affected IDs, Source result and stable failures | H06 |
| T15 | Duplicate Source or full pair with multiple keys | No cross-object/key write; one Controller bound to one Source | H02, H06 |
| T16 | Topology or key point count changes after capture | Reject before stale-index write; no guessed mapping | H02, H07 |

For every coordinate case, capture all KeyBlocks and mesh vertices before/after;
assert untouched stores bytewise or within the documented float32 tolerance.
Record Blender version, Source mode, active key, key-stack mode, controller mode,
expected/actual, PASS/FAIL/NOT RUN, and whether the check ran in background or
through native UI. Blender background tests do not satisfy modal UI rows T08/T11.
