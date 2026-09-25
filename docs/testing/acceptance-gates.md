# Acceptance Gates

**Status: Normative project gates**

## Gate A — Coherent contracts
Core, ADR-008, selection and mask rules agree. Remaining interpolation/default/quality
choices are explicit, not silently treated as frozen behavior.

## Phase completion gates — five-phase roadmap

Gate A is the documentation prerequisite. P1–P5 are required milestones, not claims
that tests have already run. Detailed steps are in [tasks](../../tasks/README.md).

| Gate | Required evidence |
| --- | --- |
| P1 — Bootstrap | Actual extension install/register/sidebar; valid Source bind; one direct child controller; Source transforms follow once; initialization preserves geometry; mesh-only/full-pair/controller-only duplicate isolation; undo/save/load/unregister |
| P2 — Controls/sync | Persistent IDs and topology validation; exact Source/proxy mapping; Source edits visibly refresh proxy; canonical whole/partial masks and overlaps; rebuild/save/load/undo without geometry changes |
| P2-UX — Phase 2 upgrade | Active-model sidebar; repeated Make Control stays Source Edit Mode; definition list/select/rename; derived On/Partial/Hidden; overlap-safe delete; clear Source control overlay; live multi-model/context/lifecycle regression |
| P3 — Patch UX | Face-connectivity fixtures, incident-patch lookup and invalidation; overlay follows Source; Show Patches changes display only, not masks/partition/geometry |
| P4 — Deformation | Gates B/C/D; point/strip/edge/loop Edit Mode G/R/S; proportional comparisons; immutable-rest preview reset; fixed constraints; cancel/undo; numeric facade and full-path measurements |
| P5 — User/agent | Gate F through actual MCP; user and agent create controls and fit reference via shared primitives; workflow quality review; robustness/regressions; documented installation and limits |

Phase 1–3 do not require interpolation. Phase 2 tests mask/definition state from
G18/G21; their deformation assertions follow in phase 4. Gate E is optional after
the five-phase core, not a phase-5 prerequisite.

P2-UX supplements P2 and must pass before P3; it is not a sixth main phase. Execute
[UX2.1–UX2.5](../../tasks/phase-02-ux-upgrade.md) on the open Blender session/file for
integration/UI tests. Record mode/selection, Source geometry and Source IDs as well
as screenshots. Assert partial/full overlap, mixed point/edge intent, no implicit
Reveal, wrong-context rejection, undo/redo and handler cleanup. Missing lifecycle
evidence remains NOT RUN; documentation validation cannot pass these runtime gates.

The latest P2-UX layout requirement is the [native list plan](../roadmap/phase-02-native-list-ux.md):
UIList scrolling/active row, inline rename, +/−, membership Sync, ↑/↓ persistence,
eye-derived state and object/mode-specific controls. Rows now highlight immediately
and select the corresponding geometry in Edit Mode; Edit Control / Back to Model
and canonical bulk Hide/Show Controls follow the updated interaction contract and
[ADR-010](../decisions/ADR-010-bulk-visibility-and-segment-selection.md). Assert all
eyes Hidden/On, partial edge Hide retains shared junctions, vertex Hide releases
incident edges, and span selection stops at effective junctions. Overlay options
remain display-only. Current scoped fixes are in the
[0.2.3 report](phase-02-edit-performance-report.md).
Scoped results and NOT RUN cases are in the [0.2.1 sidebar report](phase-02-sidebar-performance-report.md). Execute
[NL2.1–NL2.4](../../tasks/phase-02-native-list-ux.md), including undo/redo and shared
geometry/mask assertions. Prior row-box UI tests do not pass the revised layout gate.

## Gate B — Exact-control geometry
G1/G2/G3/G6/G9/G10/G12/G13/G14/G15/G16 pass their geometry/constraint assertions.
Pure fixtures verify G14 state/resampling; Blender persistence is Gate D. Record
G4/G5/G11 quality evidence. Sparse G7/G8 is deferred to Gate E.

Also pass G17–G22 preview reset, mask intent, transform selection-intent/moved-target
semantics, invalid input, coordinate-space and
definition-lifecycle assertions. G20 target-space logic can run without Blender;
object storage/integration follows in Gate D. Use geometry-cases.md measurement contract.

## Gate C — Interpolation quality decision
Review G4/G5/G11 and proportional comparisons. Accept the candidate with evidence or
run the smallest experiment for a named failure. This review can happen immediately
after Gate B; do not spend later phases building UX around a known unusable deformation.

## Gate D — Blender lifecycle
Non-agent lifecycle cases pass: mapping, hide/reveal/rebuild/save/load, cancel,
undo/redo, external coordinate sync, stale topology/network detection and multi-source.
Human/agent parity is Gate F, not a prerequisite before the facade exists.

Optional sparse integration cases belong to Gate E after the core roadmap. Unsupported features
must reject before writes. Rebuild-generation, closed/busy operations, topology fingerprint
and preview-reset recovery are required lifecycle checks.

## Gate E — Optional sparse controls
G7/G8 pass; simplify/refine does not deform Source or change masks/constraints. Partial
hide boundaries remain representable. Required only if sparse simplification ships.

## Gate F — Agent parity
Equivalent targets and visibility commands yield equivalent effective network, Source
coordinates and restore behavior through the same human/agent path.

## Production readiness
Requires passed behavior, representative quality, lifecycle/robustness and measured
performance. Detailed prose and recorded failures alone are not passing gates.

The post-baseline [H01–H10 plan](../roadmap/release-hardening-plan.md) adds release
gates without replacing P1–P5:

| Gate | Required evidence |
| --- | --- |
| H01–H02 target safety | H01 ADR/contract reviewed; H02 explicit target I/O, Edit Mode, cancel and Undo/Redo never write a different key |
| H03 ownership safety | Stale marker, Source deletion, duplicate and load do not automatically delete scene mesh data |
| H04–H05 native UI | Physical modal G/R/S, full/partial selection, key selection, display restoration and New Shape Key on a safe copy |
| H06 agent parity | Actual MCP calls target the same Source/key, controls and transaction path as UI |
| H07–H08 recovery/runtime | Topology/ID ambiguity blocks writes; repair is explicit; handlers do not perform destructive cleanup or hide failures |
| H09–H10 release | Repeatable fixture suite and UI checklist, fail on traceback, measured P95/memory, reproducible ZIP/install, documentation/version/license consistent |

Each H phase records PASS/FAIL/BLOCKED/NOT RUN. A background fixture cannot pass
a modal UI gate; exit code 0 cannot pass a run containing a Python traceback.
Outstanding H gates preclude a production-ready claim, even when P1–P5 baseline
features exist.

Record hardware, Blender version, Source/affected vertex counts, control sample counts,
median/P95 full preview latency, confirm time and peak memory. Include mesh extraction,
target generation, interpolation and Source updates; report numerical-only time separately.
Choose release budgets after representative evidence, not by weakening settled behavior.
