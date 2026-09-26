# Selection UX Phase 1 — Test report

**Result: automated checks pass; the real Blender mouse gesture is not yet UI-verified.**

## Delivered

- Each control name is a selection button. A normal click replaces the current
  mesh selection; Shift-click adds the control membership anywhere on the name.
- Shift-clicking a fully selected control removes its membership. Clicking the
  only selected control again clears selection. A pencil button opens Rename.
- The clicked row becomes the one active row used by shared row actions.
- The marker is derived at panel draw from the current Edit Mode selection and
  persistent Source vertex IDs. It shows full, partial or empty selection.
- Source Edit compares against stored control vertices. Controller Edit compares
  against effective vertices after DANP Hide masks. Empty/hidden memberships are
  never treated as fully selected. Overlapping controls can show selected at once.
- Selection is a transient UX action; the operator does not register a geometry
  Undo step or modify Source geometry/control definitions.

## Automated verification

Blender 5.2.1 LTS, Windows 11; addon source version 0.5.36.

| Check | Result |
| --- | --- |
| Static suites | 9/9 pass (65 assertions) |
| Blender background suites | 10/10 pass (includes 25 checks for multi-select) |
| Selection core cases | Full/partial/none, empty membership, overlapping memberships, hidden effective membership pass |
| Icon enum compatibility | `CHECKBOX_HLT`, `RADIOBUT_ON`, `CHECKBOX_DEHLT` confirmed in Blender 5.2.1 |
| Full release-gate status | Incomplete only because existing H08 GPU review and performance p95/memory UI gates remain NOT RUN |

The new regression uses an isolated temporary Blender process and a disposable
mesh. It exercises replacement, additive selection, active-row identity,
selection-state derivation in Source and Controller Edit, overlap, Hide masks,
and confirms selection leaves Source geometry and control definitions unchanged.

## Live Blender session and remaining UI check

MCP read-only inspection found
`Project/2. toon/girl_chibi_1_compare.blend` open with the Controller in Edit Mode;
the file was already dirty. No changes were made or saved in that session.
The actual Shift-mouse gesture in the live UI was not exercised, to preserve that
dirty model. The row names and state markers were later loaded from the workspace
source and visibly confirmed in the current Blender session. The Shift event path
is covered by the operator's `invoke` implementation and source-level regression;
a physical Shift-click remains useful for final UX confirmation.

The overall release runner reports `INCOMPLETE` due unrelated H08 and performance
gates. This does not block the selection Phase 1 automated gates above.
