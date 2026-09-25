# DANP Form — Instructions for Coding Agents

This specification separates **required product behavior** from **technical candidates**. Do not turn a candidate numerical method into a permanent architecture decision without benchmark evidence.

## Required product rules

- Source Mesh is the geometric source of truth.
- Controls are source-backed input handles; the proxy is rebuildable.
- Enabled (not DANP Form-hidden) control edges derive patches from actual topology connectivity.
- Operation Rest is the current Source state captured at operation start.
- Every preview in one operation is computed from the same immutable Operation Rest.
- Unchanged targets must produce an unchanged Source.
- Transform boundary is the union of the initial resolved selection and Controller vertices that actually move. Selected-but-unchanged vertices keep exact P0 targets; enabled control vertices outside that union are hard stationary constraints, including omitted dense vertices in sparse mode. Proportional-moved unselected vertices are exact targets.
- Shared selected junctions move; conflicting selected targets are rejected.
- DANP Form Hide releases cuts and constraints for whole or partial geometry; Reveal samples current Source positions. Read ADR-008 and core/control-model.md.
- New deformation is confined to current affected patches; cleanup of older previews stays within the captured incident-patch scope. Targets returning to P0 or radius shrinking must clear residual preview edits.
- Whole edge-backed Hide uses edge intent so other enabled lines retain shared junctions. Explicit node Hide releases all incident control edges. The canonical mask rules live in core/control-model.md.
- Proportional is applied once, at patch propagation, unless a future ADR explicitly changes that rule.
- Human, agent, and future reference-fitting inputs resolve to the same canonical control-target representation and the same mesh-deformation path.
- Committed results are real Source coordinates; the original template is not a continuous deformation prior.

## Technical-method rule

`docs/core/interpolation-baseline.md` describes a small replaceable candidate. No fixed midpoint motion or logical-group weighting is a product rule. Validate proportional, patch form and enabled-control constraints before choosing a production method.

Do not introduce harmonic fields, ARAP, SVD, PCG, cages, a permanent modifier, or a multi-stage preservation solver merely because they appeared in earlier design drafts. They are optional experiments only after a named baseline failure is reproduced.

## Work protocol

The accepted main roadmap has five phases in `docs/roadmap/implementation-plan.md`
and `tasks/README.md`. Read `docs/roadmap/development-contract.md` and ADR-009 before
starting. Controller object is Source's child; patch overlay toggles are display-only.
The post-baseline release-hardening roadmap is `docs/roadmap/release-hardening-plan.md`;
H01–H10 are separate scoped phases with explicit dependencies, verification and
commits. They do not waive any unmet P1–P5 gate. H01 is settled by ADR-017:
retain ADR-015's relative and absolute Shape Key scope, with target-safe writes
required before H02 can pass.
Implement exact controls first; sparse and automatic fitting are optional extensions.
Choose/test interpolation in phase 4, then validate human/agent MCP workflows in
phase 5 through the same primitives. Do not resurrect the replaced phase 0–8 tasks.

1. Read the task and all required normative docs.
2. Implement only the current phase.
3. Add the specified tests before broadening scope.
4. If behavior is ambiguous, consult `docs/decisions/open-decisions.md`; do not invent a product rule silently.
5. If a proposed change alters source ownership, patch semantics, target semantics, proportional placement, or writeback semantics, stop and propose an ADR.
6. Do not claim production readiness until all prototype and Blender integration gates in `docs/testing/acceptance-gates.md` pass.

## Canonical project names

- Product: `DANP Form`
- Repository: `dan-form`
- Python namespace / extension ID when implementation starts: `dan_form`
- Blender operators: `dan_form.*`

Product display name is DANP Form. Existing repository paths, extension ID,
operator IDs and stored `dan_form_*` keys stay unchanged for compatibility.
Control creation, membership Sync and definition removal belong to Source;
controller Edit Mode only adjusts existing mapped geometry. Native topology
edits on the proxy must be rejected without changing Source.

Build an installable ZIP with `scripts/package-extension.ps1`; the extension package
has `__init__.py` at its root even though the repository source lives in `dan_form/`.
