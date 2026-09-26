# Selection UX Phase 1 — Test report

**Result: automated checks pass; the real Blender mouse gesture is not yet UI-verified.**

## Delivered

- Each control row has a dedicated selection marker/button. A normal click
  replaces the current mesh selection; Shift-click adds the control membership.
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
| Static suites | 9/9 pass (63 assertions) |
| Blender background suites | 10/10 pass (includes 21 checks for multi-select) |
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
The actual Shift-mouse gesture and marker appearance in the sidebar were not
tested in the live UI, to preserve that dirty model. The event path is covered by
the operator's `invoke` implementation and source-level regression; a visual
mouse check remains useful before calling the interaction fully UX-verified.

The overall release runner reports `INCOMPLETE` due unrelated H08 and performance
gates. This does not block the selection Phase 1 automated gates above.
