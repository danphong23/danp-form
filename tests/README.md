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

## Historical fixtures

`history/live_pick_ux.py` and `history/live_control_segments.py` depend on the
old picker operators/Scene properties, which are not registered in 0.5.36.
They are retained for the
[0.2.5 report](../docs/testing/phase-02-pick-ux-audit.md), not for current
acceptance. Do not execute them against a current live project.

Fixtures, test logs, `.blend` outputs and bytecode do not belong in the
installable extension. Generated release archives belong in ignored `dist/`.
