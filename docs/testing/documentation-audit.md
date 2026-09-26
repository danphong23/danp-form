# Documentation Audit — 2026-09-18

**Status: Review of specifications; not evidence of a working add-on**

Historical snapshot as of 2026-09-18. Its final section describes the prototype
state on that date; the repository now contains a production add-on and later
implementation/release reports. Do not use the historical implementation-status
sentences below as current readiness evidence.

Reviewed all modular documentation, root guidance/readmes, ADRs and implementation tasks.
The accepted modeling idea is unchanged: Source-backed selection drives deformation
within topology patches using proportional and current patch form; enabled unselected
controls hold, hidden contours can follow mesh and reveal at current positions.

## Corrections

| Finding | Resolution |
|---|---|
| Whole Hide could be read as hiding junction nodes and breaking retained loops | Whole edge-backed Hide uses edge intent; explicit node Hide affects every incident edge |
| Sparse selection could be mistaken for implicit neighbor motion | Knot-only selects one bound vertex; spans explicitly select represented dense geometry |
| Identity/radius-shrink previews could leave earlier displacement | Capture incident-patch scope and rebuild output from P0 for every update; G17 |
| Per-update scope versus no-outside-write rules were ambiguous | Current deformation scope and bounded prior-preview cleanup are documented separately |
| Errors/busy/closed handles lacked defined write behavior | Validate generations/ownership/input, preserve legitimate owner on busy rejection, reject closed handles |
| External topology could preserve element counts | Require connectivity/faces fingerprint and explicit validation; no stale-index rollback |
| Coordinate caches and Source/world target spaces were underspecified | Freeze P0/transform frame; rebuild coordinate-dependent buffers; consistent radius units |
| Sparse/agent tests appeared before their implementation phases | Five-phase roadmap: Gate D in phase 4, Gate F in phase 5, optional Gate E after core |
| Numerical candidates were sometimes described as product mandates | Readme/authority rules distinguish normative behavior from replaceable methods |
| Prototype unsupported cases remained unclear | Reject non-manifold, Shape Keys/Multires, shared/read-only data before writes; future support stays open |
| Old 0–8 tasks contradicted the agreed product milestones | Replaced by five phase tasks with work packages, dependencies and P1–P5 gates |
| Controller follow behavior and apparent 2D lines were ambiguous | Source-child object, same local frame, 3D vertex/edge proxy and directed coordinate sync |
| Patch toggles could be mistaken for excluding solve input | Overlay display-only; effective control Hide changes actual face partition |
| One vertex/one chain could prescribe an unsupported mesh mapping | Influence is graph-connected vertices in incident patches and may branch |
| Reference testing implied an automatic fitting feature | Phase 5 tests human/agent-generated targets; automatic image processing stays extension |

## Development handoff

The five-phase [roadmap](../roadmap/implementation-plan.md),
[development contract](../roadmap/development-contract.md),
[phase tasks](../../tasks/README.md) and ADR-009 now define the implementation order.
Phase 1–3 test installation/control/sync/patch UX before numerical deformation;
phase 4 must pass geometry/quality/lifecycle, then phase 5 validates MCP/user workflow.

## Checks and limits

Regenerate full-specification.md from every docs module, then run scripts/validate-docs.ps1
to verify source coverage/content, Markdown file links and both documentation manifests.
These checks establish file consistency only, not mathematical completeness or runtime
correctness. Geometry tests G1–G21, Blender lifecycle and agent parity have not been run
because this package contains no production add-on implementation.

Core behavior is ready for a bounded prototype. Shipping proportional defaults, acceptable
quality, final interpolation method and release performance budgets still require evidence
or explicit decisions in decisions/open-decisions.md. No further product hierarchy or
solver family is implied by this audit.
