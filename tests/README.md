# Test inventory

## Current release entry point

Use `run_release_gates.py` with an explicit Blender executable. It discovers
root `test_*.py` suites and runs the named background suites listed in
`BACKGROUND_SUITES`, plus the disposable native-transform fixture. See the
[H09 report](../docs/testing/2026-09-25-h09-release-gates.md) for previous evidence
and unverified GPU/performance gates. A previous PASS does not certify a later
commit or replace a new UI test.

The other root `live_*.py` files are supplemental fixtures. Read each fixture's
mode, environment and restoration requirements before running it. They are
not all invoked by the release runner and are not automatically release evidence.

`live_control_multiselect.py` is a historical filename used by the release
runner, but it creates and removes objects without restoring the user's active
object, selection or mode. It now refuses to run unless Blender is in background
mode; use only through the disposable fixture runner, never through MCP in the
open user scene.

## State consistency audit

`audit_state_consistency.py` is a readiness audit for the
[2026-09-26 review](../docs/testing/2026-09-26-comprehensive-addon-review.md).
Run it only with a disposable `--factory-startup --background` Blender process.
It refuses a UI process or a scene with a saved filepath. The JSON observations
report known defects; exit code 0 means collection completed, not a PASS gate.
The injected rebuild traceback is expected evidence of missing rollback.
Convert repaired probes into normal regression gates before release acceptance.

## Historical fixtures

`history/live_pick_ux.py` and `history/live_control_segments.py` depend on the
old picker operators/Scene properties, which are not registered in 0.5.36.
They are retained for the
[0.2.5 report](../docs/testing/phase-02-pick-ux-audit.md), not for current
acceptance. Do not execute them against a current live project.

Fixtures, test logs, `.blend` outputs and bytecode do not belong in the
installable extension. Generated release archives belong in ignored `dist/`.
