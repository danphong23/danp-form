# Release hardening baseline — 2026-09-25

**Status: Planning audit, not a PASS report.** This note distinguishes current
evidence from work in the [H01–H10 roadmap](../roadmap/release-hardening-plan.md).
The proposal supplied for Shape Key development is design input. Current
[ADR-015](../decisions/ADR-015-shape-key-edit-target.md) remains authoritative
until H01 explicitly amends or supersedes it.

| Area | Observed state | Required phase |
| --- | --- | --- |
| Target selection | Active Shape Key workflow and P0 exist; relative and absolute are accepted by ADR-015 | H01 defines target identity and scope |
| Target I/O | Explicit key in Source Edit Mode may resolve through active BMesh; Undo target path requires coverage | H02 |
| Object ownership | Lifecycle cleanup can remove a marked scene mesh with missing Source | H03 |
| All-control Scale | Numeric and background fixture passed for 0.5.31; physical modal mouse transform not verified | H04 |
| Shape Key UX | Current selector/show-only exist; complete target/new-key workflow and regression evidence pending | H05 |
| Agent | Current facade lacks target-list/selection commands and target parity evidence | H06 |
| Topology | Fingerprint mismatch pauses edits even if visible controls appear unaffected; patch connectivity still matters | H07 |
| Runtime | Handler/error/cache boundaries need review after safety fixes | H08 |
| Test infrastructure | Historical selection suites are stale; overlay requires live GPU context; background Blender may return exit 0 with traceback | H09 |
| Release | Manifest says 0.5.31; README version was stale before this docs update; release gates not complete | H10 |

This is a code/document review and earlier test-evidence synthesis. It is not a
fresh Blender UI test, model edit, or release certification. Existing historical
reports remain dated records; do not reinterpret their old NOT RUN as PASS.

**Later on 2026-09-25:** H01 accepted
[ADR-017](../decisions/ADR-017-deformation-target-contract.md), retaining
relative and absolute keys. Target I/O and all runtime rows remain for H02–H06.
