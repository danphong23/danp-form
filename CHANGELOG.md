# Design Changelog

## 2026-09-22 — DANP Form 0.5.27 Mirror Edit stability

- Loại `is_active` của modifier khỏi dữ liệu đồng bộ: đây là trạng thái lựa
  chọn UI riêng của từng object, không phải thiết lập hình học. Trước đây
  Mirror trên Controller bị dựng lại liên tục khi Source có Subdivision được
  chọn, có thể ngắt Edit Control giữa G/R/S và làm hỏng thao tác hủy.
- Chỉ ghi metadata Controller khi giá trị thực sự đổi để tránh phát sinh cập
  nhật depsgraph không cần thiết.
- Thêm bài kiểm tra Blender cho đồng bộ lặp lại trong Edit Mode, native Mirror
  Clipping và chuỗi preview → hủy trả Source về vị trí ban đầu.

## 2026-09-22 — DANP Form 0.5.26 modifier synchronization

- Đồng bộ Mirror từ Source sang Controller theo đúng thứ tự và thiết lập RNA.
- Tự cập nhật Controller khi modifier Source đổi, mở file hoặc Undo/Redo.
- DANP writeback tôn trọng Merge/Clipping của Mirror khi tính preview trên Source.
- Bỏ qua modifier cần mặt trên proxy vertex/edge như Subdivision; Source vẫn giữ
  toàn bộ stack gốc.
- Thêm kiểm tra tĩnh và tài liệu về ranh giới Source/Controller.

## 2026-09-22 — DANP Form 0.5.24 moved-target transform bridge

- Native Controller transforms now derive targets from every proxy vertex whose
  coordinate changed during the operation, so Blender Proportional Editing is
  preserved for unselected vertices.
- Selection changes delimit operations without treating proportional motion as a
  new selection; Source writeback skips unchanged coordinates to reduce viewport
  flicker and redundant depsgraph updates.
- Added documentation for the moved-target contract and patch-local behavior.

## 2026-09-22 — DANP Form 0.5.23 cylinder interpolation and compact actions

- In full-patch mode, blend moving control transforms once and interpolate to
  fixed control boundaries by Source edge length. This preserves the longitudinal
  ratios of cylinder rings when two control loops approach each other.
- Replace the crowded Init/Reset/Reset Model/Remove row with the current primary
  action and a Manage menu for rebuilding or removing control definitions.
- Add uniform and irregular cylinder-ring regression cases.

## 2026-09-22 — DANP Form 0.5.22 topology-safe recovery

- Native Source topology edits now pause DANP with a recovery message instead
  of exposing `STALE_MAPPING` to the user or writing stale IDs.
- Added an undoable Reset action that discards the old mapping and rebuilds a
  Controller from the current Source topology.
- Added explicit orphan cleanup for DANP-owned Controller and face objects when
  their Source no longer exists; unrelated assets are not inferred or deleted.
- Modifier changes invalidate display caches while unapplied modifiers remain
  evaluated display input only; Apply operations that change base topology use
  the same Undo/Reset recovery path.

## 2026-09-21 — DANP Form 0.5.21 Source and Undo cleanup

- Rebuild every Controller coordinate from Source while retaining selection;
  a stale Controller pose can no longer survive a rebuild.
- Reject malformed control definitions, masks, IDs and unsupported schemas
  before migration or Source ID writes instead of silently discarding records.
- Remove the unused custom Box Select and G/R/S macros; native Blender Edit
  transforms remain the active interaction.
- Match multi-step native Undo/Redo against Controller poses, including cases
  where Blender has already restored Source, and rebuild derived caches.
- Add live regressions for proxy rebuild and three-step Undo/Redo history.

## 2026-09-19 — DANP Form 0.5.18 transform-field ownership

- A patch with one incident control now receives that control's full
  translation/rotation/scale transform instead of averaged boundary
  displacement vectors.
- Shared patches blend incident control transforms; enabled unselected controls
  contribute identity and remain hard stationary anchors.
- Added pure rotation/scale, shared-anchor and live Source scope regressions.
- Recorded the contract in ADR-011 and synchronized the consolidated docs/hashes.

## 2026-09-19 — DANP Form 0.5.17 shared-patch agreement

- Validate all patch-local interpolation candidates for a shared free vertex
  before Source writeback; conflicting candidates now reject with
  `TARGET_CONFLICT` instead of depending on patch iteration order.
- Added a pure regression for shared-vertex conflict rejection.

## 2026-09-19 — DANP Form 0.5.15 transform axis and patch interpolation

- Replaced averaged patch displacement with patch-local inverse-distance
  interpolation from selected and stationary Source-backed control vertices.
- A selected boundary now propagates its non-uniform G/R/S targets into every
  incident patch while adjacent enabled controls remain exact anchors.
- Added pure regression coverage for a moving boundary and non-uniform loop
  targets; no modifier, topology or Source/Controller identity behavior changed.
- Suspended the topology-lock keymap while Blender's native transform modal is
  active, so the first axis key after G/R/S is no longer consumed by the guard.

## 2026-09-19 — DANP Form 0.5.16 target validation

- Preserve explicit target mappings, including an intentionally empty mapping,
  so invalid target counts are rejected instead of silently becoming a delta move.
- Added no-op, finite-radius scope and target-validation regressions.

## 2026-09-19 — DANP Form 0.5.13 native proportional workflow

- Native Controller Edit G/R/S now use the scene's Profile and Radius values
  during live preview and commit.
- Removed the Apply Move dialog button from the main Controller panel; the
  exact deformation operator remains registered for API/agent calls.

## 2026-09-19 — DANP Form 0.5.12 pose comparison type fix

- Proxy snapshot coordinates are converted to mathutils vectors before pose
  comparison, preventing the lifecycle guard from swallowing a valid native
  transform because of tuple/vector subtraction.

## 2026-09-19 — DANP Form 0.5.11 pose baseline initialization

- The first Controller Edit transform after addon reload now compares against
  the Source pose when no proxy snapshot exists, so it cannot be silently
  dropped.
- Entering Controller Edit establishes a valid proxy snapshot before native
  selection and transform events begin.

## 2026-09-19 — DANP Form 0.5.10 transform-observer filtering

- Controller Edit dependency-graph updates are now compared against the last
  valid proxy pose before starting a native transform session.
- Selection-only updates and topology recovery no longer create phantom native
  transactions or stale undo records.

## 2026-09-19 — DANP Form 0.5.9 View3D modal-area correction

- Modal pick tools now resolve and retain the actual View3D area when launched
  from the sidebar, keeping hover hit-testing, header text and outside-click
  exit behavior in the same coordinate space as the viewport.

## 2026-09-19 — DANP Form 0.5.8 pick-overlay UX correction

- Pick previews now bind to the actual View3D area even when the tool is
  launched from the sidebar, so hover feedback is drawn in the viewport.
- Clicking outside the viewport now exits the pick tool as a cancelled action
  and no longer reports a false “Selection confirmed” status.

## 2026-09-19 — DANP Form 0.5.7 functional-control baseline

- Revalidated list selection, definition deletion, Hide/Show, Sync, Source /
  Controller navigation, topology protection, native transform preview,
  adjacent-control pinning, commit, cancel and paired Source undo/redo on the
  open ``girl_chibi_1.blend`` test file.
- Removing a controller or the complete DANP binding now discards its runtime
  transform session, transaction and undo record, preventing stale state from
  accumulating in long Blender sessions.
- Updated live regressions to match the intended Controller workflow: valid
  coordinate edits deform Source, while rejected topology edits preserve the
  accepted pose and current model geometry.

## 2026-09-19 — DANP Form 0.5.6 direction-aware undo/redo

- Undo and redo now use separate persistent handlers and defer only the
  matching Source restore until Blender leaves its undo stack callback.
- Direction-aware records remove the previous heuristic based on Controller
  pose, so Controller mode changes during undo cannot prevent Source pairing.

## 2026-09-19 — DANP Form 0.5.5 deferred undo restoration

- Native undo/redo Source pairing is now deferred through a short Blender app
  timer instead of writing mesh data re-entrantly inside ``undo_post``.
- The restore path updates only Source; Blender already owns the Controller
  undo pose. This avoids edit-mesh recursion while retaining one logical
  operation across both domains.

## 2026-09-19 — DANP Form 0.5.4 native undo pairing

- Native Controller transforms now retain a runtime Source pre/post record.
  Blender's undo/redo callbacks pair the native proxy pose with the matching
  Source deformation, so one Ctrl+Z or Ctrl+Shift+Z restores both domains.
- The record is runtime-only and is discarded on unregister; it never changes
  persistent control identity or topology metadata.

## 2026-09-19 — DANP Form 0.5.3 native transform safety

- Removed the nested DANP modal wrapper around Blender's transform operator.
  Controller Edit now receives native G/R/S directly, so Confirm/Cancel,
  axis constraints, numeric input, snapping and Blender's undo stack remain
  under one native operator.
- Source deformation is observed from Controller Edit geometry by a runtime
  transaction/timer bridge; the proxy is never written back while the native
  transform is active. This avoids re-entrant BMesh writes that could crash
  Blender during ``transform_modal``.
- Replaced the invalid Blender 5.2 ``TRANSFORM_MOVE`` UI icon with a stable
  built-in icon.

## 2026-09-19 — DANP Form 0.5.2 native Controller Edit transform bridge

- G/R/S in Controller Edit now delegates the actual interaction to Blender's
  native transform operator, preserving axis locks, numeric entry, snapping,
  live mouse preview and cancel behavior.
- A single Source-backed deformation transaction is updated from the live
  controller target positions and committed/cancelled as one operation; the
  proxy is not overwritten during the preview.
- Source overlay evaluation now honors the active modifier's On Cage state:
  disabled cage stays on the exact base edge, enabled cage follows the
  evaluated edge segments carrying the same persistent ID.

## 2026-09-19 — DANP Form 0.5.1 Source-mesh control baseline

- Source control identity remains on the live base BMesh, while the overlay
  resolves the same persistent edge ID to Blender's evaluated visible edge
  chain; it never selects a nearest neighboring edge.
- Sidebar definition delete passes the selected row UUID explicitly and is
  available from Source and Controller contexts; Sync and creation remain
  Source-only.
- Updated the live overlay and lifecycle checks to verify exact base-edge
  endpoints with a viewport Subdivision modifier enabled.

## 2026-09-19 — DANP Form 0.5.0 stability baseline

- Fixed bulk Hide/Show so hidden edge endpoints are not resurrected as orphaned
  control vertices; the empty-network round trip is now idempotent in Blender.
- Source overlays use persistent base-edge IDs and leave modifier evaluation
  outside the control identity contract.
- Controller-side Delete now uses the same active-definition action as Source
  Edit, and extension registration tolerates Blender's restricted install
  context without duplicating handlers.
- Removed the obsolete viewport-hidden Source flag from runtime and package
  data; display overlay and canonical Hide/Reveal remain separate states.

## 2026-09-19 — Edit Mode control workflow regression fix

- Fixed Init in Source Edit Mode assigning zero to every persistent vertex and
  edge ID in the live BMesh. A selected loop now retains every distinct member
  through Create, Sync, list selection and Delete instead of collapsing to
  `1V/1E` and selecting the whole mesh.
- Moved mutable UI-sync and pick-session guards onto the shared runtime module
  so callbacks from extracted operator modules observe the same state as the
  facade and registration lifecycle.
- Revalidated the real sidebar buttons in the open character test file: a
  20-edge loop created a `20V/20E` control, Sync replaced it with a `16V/16E`
  loop, and creating another active control retained its `10V/10E` membership.

## 2026-09-19 — Module extraction foundation

- Moved persistent identifiers into `dan_form/constants.py`.
- Moved runtime-only caches and transaction state into `dan_form/runtime.py`.
- Moved JSON-backed Source definitions and mask helpers into `dan_form/storage.py`.
- Moved effective control resolution, patch partitioning, graph distance and
  proportional attenuation into Blender-independent `dan_form/core` modules;
  the facade still adapts persistent IDs and cache ownership.
- Moved proxy rebuild, Source-to-controller sync and topology recovery into
  `dan_form/blender/proxy.py` with explicit adapter dependencies.
- Moved add-on registration, Scene properties and handler/keymap lifecycle into
  `dan_form/registration.py`; the root facade retains the public entry points.
- Moved operators, picking, UIList/sidebar classes and viewport overlay drawing
  into `operators.py` and `ui/overlay.py` with explicit facade binding.
- Moved deformation transactions, mask mutation and Source writeback into
  `dan_form/blender/workflows.py` with explicit `WorkflowDeps` adapters.
- Kept compatibility names in the facade while existing live regression scripts
  are migrated to their owning modules.
- Updated extension packaging to include the complete package contents, not only
  the facade `__init__.py`.
- Recorded the boundary and compatibility contract in
  `docs/architecture/module-boundaries.md`.

## 2026-09-18 — DANP Form 0.3.1 patch mode-switch performance

- Fixed Object Mode patch face extraction from an O(face × edge) scan to an O(face + edge) lookup table.
- Cached Source face connectivity across mode changes and reused a topology token instead of comparing thousands of ID mappings on every redraw.
- Grouped translucent patch triangles into six palette GPU batches at most; a 104-patch character no longer submits 104 draw batches.
- Optimized incident control lookup by computing each control's effective membership once per partition.
- Live measurement improved cached face reads to about 0.05 ms, cached overlay to about 4.7 ms, and first partition construction to about 172 ms. Mode-switch fixture checks pass with Show Patches enabled.

## 2026-09-18 — DANP Form 0.3.0 patch graph and display

- Added runtime Source face partitioning through effective enabled control edges, with stable Source-ID face/edge membership, incident control lookup and cache invalidation.
- Added display-only translucent patch batches and a compact Source-only Show Patches switch. Patch colors never edit Source or change masks, network revision or deformation scope.
- Added grid fixture coverage for internal cuts, boundary edges, point controls, cache reuse, Hide/Reveal merging and restoration; verified the live character at 104 patches covering 1696 faces.
- Kept Phase 1/2 lifecycle, performance, segment and pick suites green after the Phase 3 runtime additions. See the [Phase 3 report](docs/testing/phase-03-patch-report.md).

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
## 2026-09-19 — DANP Form 0.5.19 native transform transaction lifecycle

- Added macro-backed Controller Edit `G/R/S` operations with an explicit Begin → native Blender transform → Finish sequence.
- Captured Source/Controller rest before the first native transform delta; preview writes remain absolute to that rest.
- Removed timer-based native commit for the user-facing path; Confirm is now owned by the macro Finish step and Cancel restores the captured rest.
- Added cancellation safety for native transforms that restore the controller pose without a usable operator-stack callback.
## 2026-09-20 — DANP Form 0.5.20 selection-safe control creation

- Refresh BMesh lookup indices before reading Source selection.
- Allow agent/API callers to provide a control name at creation time.
- Keep persistent DANP vertex/edge layers authoritative across proxy rebuilds.
