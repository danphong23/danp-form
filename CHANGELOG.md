# Design Changelog

## 2026-09-18 — DANP Form 0.2.5 pick and visibility UX repair

- Removed blocking pick input; hover no longer mutates selection. RMB/Esc cancels, navigation passes through, and native commands such as Box Select stop picking and receive their normal input.
- Corrected sidebar-to-viewport coordinate conversion, opaque Source occlusion and native X-Ray/wireframe overlay depth.
- Added Ctrl subtraction to repeat picking and corrected Shift being incorrectly interpreted as Add in the whole-control shortcut.
- Included native selection/hide flags in cyan batch invalidation; clicking empty space and Hide/Show no longer leave stale black spans or require a list-row refresh.
- Preserved surviving controller pose and selection during canonical rebuild; newly revealed handles sample Source and start unselected.
- Capped controller Edit highlight at 1.5 px, kept preview usable with Overlay off, scoped Preview Hidden to Source, and restored all owned controllers' X-Ray display state on unregister.
- Restored prior GPU depth and line width after drawing so the highlight does not leak these settings into other viewport callbacks.
- Passed 197 live checks across five suites in the user's open Blender file, including 45 new input/visibility regressions. All 924 enabled character edge seeds resolved spans; idle batch access measured 0.772 ms median / 0.958 ms P95 including native selection scanning.
- Computer Use event validation was interrupted by foreground window changes; synthetic modal event checks and native Box Select execution through MCP are not equivalent to physical mouse/keyboard dispatch. See the [audit](docs/testing/phase-02-pick-ux-audit.md).

## 2026-09-18 — DANP Form 0.2.4 selection setup and X-Ray

- Added a compact Setup block in the sidebar with Hover Pick Segment, Hover Pick Control, Add to Selection, Clear, Select All Controls and visible Overlay/X-Ray/Show Hidden switches.
- Hover tools preview the resolved segment/control under the pointer, commit on click, cancel with Esc, and accept Shift or Add to Selection for multi-selection.
- Added Ctrl+Alt+S and Ctrl+Alt+C modal shortcuts for segment/control hover picking.
- X-Ray now also enables the controller's in-front wire display, so hidden control edges are visible through the model; turning it off restores normal depth behavior.

## 2026-09-18 — DANP Form 0.2.3 performance and control selection

- Replaced repeated per-vertex ID/coordinate reads with bulk BMesh/Mesh access and cached Source edge connectivity.
- Cached the effective network and GPU overlay buffers; geometry/context/masks/highlight/transforms invalidate them while idle redraw reuses buffers.
- Kept explicit point handles visible without drawing large dots over every edge endpoint.
- Added Ctrl+Alt+Click junction-span selection (Shift adds), scoped H/Alt-H canonical partial Hide/Reveal and edge intent that retains shared junctions.
- Changed Hide/Show Controls to canonical bulk visibility, synchronizing every list eye; see ADR-010. Overlay options remain display-only.
- Controller Edit now reads the live controller BMesh and highlights all enabled proxy edges cyan while leaving Blender's native orange selection visible above it.
- Control overlay depth now follows the opaque mesh by default; X-Ray is the explicit mode that draws through the mesh.
- Added Ctrl+Shift+Click to select a whole logical control under the cursor; shared edges use the active list row or fail explicitly instead of guessing.
- Live 50-definition character measurement: 4.706 ms median for invalidated BMesh position collection and 0.0119 ms for cached batch access.
- Passed 38 cache/highlight, 37 lifecycle/protection, 34 sidebar and 36 segment/visibility checks (145 total) in the existing open Blender file; Computer Use verified canonical H/Alt-H and Controller Edit readability.
- Added front contour definitions to the user's live character without modifying its geometry; these are scene data, not an automatic silhouette addon feature. See the [performance and contour report](docs/testing/phase-02-edit-performance-report.md).

## 2026-09-18 — DANP Form 0.2.2 lifecycle and controller protection

- Corrected product/sidebar naming to DANP Form; retained extension, operator and data IDs for existing files.
- Added persistent model Init and red Remove DANP Form buttons; removal clears owned setup without deleting or reshaping the model.
- Removed Sync and definition creation/deletion from controller contexts; those actions use the model selection.
- Added scoped topology shortcut guards and ID/connectivity recovery for native menu or MCP geometry changes, preserving the last valid controller pose.
- Passed 37 lifecycle/protection checks and 33 sidebar checks in the existing open Blender file, with Computer Use visual verification; see the [report](docs/testing/phase-02-controller-lifecycle-report.md).

## 2026-09-18 — Phase 2 UX implementation

- Resolved sidebar context from the active Source or its bound controller, including multiple models.
- Kept Make Control and structural control actions in the user's Source/controller Edit Mode context.
- Added overlap-safe control list actions: select, rename, derived On/Partial/Hidden state, Hide/Reveal and definition-only delete.
- Added a colored Source-backed overlay and readable controller wire color with display-only toggles.
- Fixed persistent ID reads in Edit Mode by using BMesh layers, and aligned the package manifest with the 0.2.0 implementation.
- Verified the live workflow through MCP and Computer Use on the open Blender file; see the [live report](docs/testing/phase-02-ux-live-report.md).

## 2026-09-18 — Accepted five-phase development plan

- Replaced phase 0–8 tasks with bootstrap, controls/sync, patch visualization, deformation/proportional and user/agent MCP validation.
- Added work packages, dependencies, test evidence and P1–P5 completion gates for each phase.
- Recorded ADR-009 and development contracts for Source-child controller, directed sync, display-only patch overlay and graph-connected influence.
- Moved interpolation/default decisions to phase 4 evidence; kept sparse and automatic image fitting optional after core.
- Aligned README, coding-agent instructions, prototype sequence and Blender/agent acceptance coverage; regenerated consolidated spec and hashes.

## 2026-09-18 — Documentation consistency audit

- Clarified whole-line edge Hide versus explicit node Hide so shared leg-loop junctions remain consistent.
- Defined captured scope and preview reset when targets return to rest or influence shrinks.
- Synchronized target spaces, cache generations, topology fingerprints, owner/closed handles and recovery limits.
- Distinguished unsupported prototype safety defaults from future feature decisions.
- Added G17–G21 and measurable fixture/performance reports; deferred optional sparse lifecycle checks to their phase.
- Corrected documentation authority and README wording so numerical candidates remain replaceable.
- Added a review record and repeatable consolidated-spec/link/hash validation.

## 2026-09-18 — Enabled/hidden control behavior agreement

- Added ADR-008 and concrete leg examples for selected loops, stationary longitudinal lines and hidden contours following mesh.
- Replaced separate deactivation/display-only DANP Form hiding with canonical whole/partial Hide/Reveal masks.
- Made enabled unselected Source vertices hard stationary, including omitted sparse vertices; removed automatic sparse-knot neighbor movement.
- Specified shared junction priority, current-position reveal, persistence/cache/undo behavior and grouping independence.
- Reclassified interpolation as a replaceable candidate, removing fixed midpoint/affine promises; added G12–G16 and synchronized phase gates.

## 2026-09-18 — Core simplification redesign

- Reframed DANP Form around patch-rest shape plus sparse control motion.
- Removed harmonic/ARAP/SVD/PCG and staged shape-preservation pipelines from core requirements.
- Replaced the old normative solver with a simple, testable displacement-blend prototype baseline.
- Defined partial control selection and sparse-control target expansion explicitly.
- Defined proportional as a single patch-propagation stage.
- Kept source/proxy mapping, persistent IDs, rebuild, cancel, undo, multi-template context, and same human/AI primitives.
- Moved reference fitting and advanced interpolation methods to extensions.
- Replaced production-ready claims with prototype and evidence gates.
- Rebuilt `full-specification.md` from modular documents.
