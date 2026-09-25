# H06 — Agent target parity test report

**Result: PASS for the H06 API contract and disposable-fixture lifecycle.**

- Blender: 5.2.1 LTS, background factory startup.
- Fixture: disposable meshes and shape-key stacks created by
  `tests/live_agent_target_api.py`; two independent Sources.
- User's open `.blend`: inspected through Blender MCP with a read-only target
  query. The active Source returned two deformation targets. No scene data was
  changed or saved.
- Mutating API operations were exercised only against the disposable fixture.
  This verifies Blender-side facade behavior; the connected MCP transport was
  not used to mutate the user's current scene.

## Results

All six fixture scenarios passed:

1. Target listing reports Basis and keys with lock/active state and a revision.
2. Target selection uses the same registered operator as the UI; stale revisions
   fail closed.
3. Locked targets can be listed/selected but cannot begin deformation.
4. Absolute coordinates for the complete selected persistent-ID set write to
   the captured key and commit by operation handle.
5. Changing target during an operation rejects writes; cancel restores the
   captured target.
6. Base cancellation restores exact data, and operations remain Source-local
   with two Sources present.

The fixture also rejects missing/extra IDs, duplicate or invalid IDs, and
non-finite coordinates before Source writes. It checks that a second Source's
coordinates remain unchanged.

## Gate boundary

H06 API parity and lifecycle pass. A live mutating MCP call against the user's
dirty file was not required for this phase and was not performed. The Blender
MCP query was read-only; all writes and rollback cases used the disposable
fixture. UI parity relies on the shared selection operator and transaction /
solver path; modal UX remains covered by H04 acceptance.
