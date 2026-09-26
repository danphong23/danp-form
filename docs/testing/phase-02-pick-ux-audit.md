# Phase 2 — Pick / visibility UX audit (0.2.5)

> Historical evidence for 0.2.5. The custom picker is not registered in 0.5.36.
> Its fixtures are retained under `tests/history/` and are excluded from the
> current release gates. Results below describe that historical revision.

## Assessment

The previous UX was not reliable enough to close Phase 2 interaction review.
Passing earlier lifecycle/cache tests did not exercise native event routing,
sidebar-origin mouse coordinates or selection-only cache invalidation. The user's
screenshots exposed actual defects. The cyan layer itself is drawing, not geometry
and not an input handler; the modal picker was the input owner causing conflicts.

The current repair keeps Blender native selection as the authority. Cyan is an
optional thin mark of enabled edges, orange is native selection, and magenta is a
temporary pick preview. No new deformation rules or phase 3/4 feature is introduced.

## Findings and repair

| Finding | Cause | Repair / remaining limit |
| --- | --- | --- |
| Pick prevents pan/zoom/cancel/native selection | BLOCKING modal flag and unhandled events returned RUNNING_MODAL; RMB was not cancel | Remove blocking, explicit RMB/Esc, MMB/wheel/trackpad PASS_THROUGH; native command ends preview and passes input |
| Upper/lower spans cannot be picked | Sidebar event coordinates remained UI-relative after context override | Convert global mouse coordinates to WINDOW; verify four boundary directions on cube. Exact failing character edge IDs were not supplied |
| A back edge can win opaque picking | Distance/depth picker had no Source occlusion | Ray-test candidate against visible Source; X-Ray/wireframe intentionally permit back edges. Other objects/modifiers are not an exact GPU-depth picking implementation |
| Hide/Show needs a row click to recover cyan | Rebuilt Edit geometry could start entirely selected, so overlay omitted all edges | Preserve surviving selection and leave new handles unselected; cyan appears without row action |
| Click empty space leaves selected span black | Cyan batches omitted selected edges but did not invalidate on selection-only changes | Include BMesh native selection/hide flags in token |
| Hide resets unrelated controller edits | Rebuild always resampled every position from Source | Keep surviving handle positions; only newly revealed IDs sample Source |
| Box Select does not work during pick | Modal retained keyboard/mouse input | Yield to B and native Box Select. Overlay has no input callback and cannot block selection |
| Whole-control shortcut always adds | Mandatory Shift shortcut modifier was treated as Add | Replace by default; explicit Add option / hover Shift handles accumulation |
| X-Ray targets stale model and leaks display state | Scene pointer and unregister restored only one controller | Apply to all owned controllers in scene; restore all saved object display states on unregister |
| Controller Show Hidden appears to do nothing | Canonically hidden geometry does not exist in controller | Expose Preview Hidden only on Source; it is display-only |
| Thick duplicate highlight competes with native wire | Same visual weight in Source and Controller Edit | Cap Controller Edit cyan at 1.5 px, preserve native orange, allow Overlay off |
| Drawing can affect other callbacks | Custom line width/depth were not restored | Save/restore previous GPU depth and line width; reset point size to default |

## Verification

Blender 5.2.1 LTS, Windows; the already-open
`Project/2. toon/girl_chibi_1.blend`, Layout. No separate Blender process and no
scene builder were used. File was dirty before and after; no save occurred.

| Live suite | Checks | Result |
| --- | ---: | --- |
| live_controller_lifecycle.py | 37 | PASS |
| live_sidebar_regression.py | 34 | PASS |
| live_edit_performance.py | 38 | PASS |
| live_control_segments.py | 43 | PASS |
| live_pick_ux.py | 45 | PASS |
| Total | 197 | PASS |

The new suite directly invokes modal methods with synthetic events in live View3D
context; this verifies return values and real BMesh flags, not Blender's physical
event dispatch. It executes native Box Select and verifies actual selected vertices.
It also verifies preview/cancel, repeated Add/Subtract, global sidebar coordinates,
front/back visibility, native viewport X-Ray, GPU depth/line-width restoration,
Show All and selection-only GPU batch invalidation.

The character's 924 enabled edge seeds all resolved graph spans without errors.
With empty native selection all 924 edges had cyan endpoint geometry (1848 entries).
This connectivity check is not proof that every overlapping projected edge can be
individually clicked. Idle batch access including selection scanning: 0.772 ms
median / 0.958 ms P95 over 100 samples. Final sidebar eye operation mean: 53.661 ms
median over three Hide/Show pairs on the 50-definition character. These timings
exclude complete viewport rendering and full physical interaction latency.

Computer Use identified the Blender window and observed the installed UI. An input
attempt was rejected after user input; another capture showed the foreground
browser. Physical pick, RMB, wheel, pan and B dispatch were therefore NOT RUN to
completion in this repair. One capture was also rejected by automatic approval
review for targeting an unrelated ChatGPT window; no input was sent there.
Do not report these synthetic events as physical Computer Use evidence.

Source and controller coordinate/connectivity hashes matched pre-test values;
Source retained 1698V/3392E/1696F, controller 824V/924E, and 50 character definitions.
Owned fixtures were removed. The original Controller Edit selection, display/view
options and user visibility are restored; no model fitting or file save is part of
this audit.

## Remaining gates

- Physically verify pick → wheel/MMB → RMB and pick → B/C/G/Tab in the target Blender window when the foreground is stable; verify custom keymaps and emulated three-button input.
- Verify actual interactive undo/redo of repeated picks and Hide/Show, then save/reopen lifecycle in a dedicated user-authorized test session. No save/reopen is claimed here.
- Projected coincident edges and shared logical definitions remain ambiguous: active matching list row selects a shared whole control; otherwise selection asks for a row. No hidden guess is introduced.
- Pick Segment selects a graph span between junctions; it does not select a patch face. Actual patch visualization is Phase 3; Source deformation/proportional is Phase 4.
- The single source module remains large. Extract input/selection and overlay/cache adapters before adding Phase 4 transactions, with the same behavioral suites. Refactoring is not a substitute for the remaining interaction gates.

0.2.5 repairs reproduced code-level defects, but this report does not assert
production readiness or completion of all Blender integration acceptance gates.
