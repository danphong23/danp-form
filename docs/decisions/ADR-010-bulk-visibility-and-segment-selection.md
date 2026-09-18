# ADR-010 — Bulk canonical visibility and junction spans

**Status: Accepted — explicit user request, 2026-09-18.**

## Decision

Hide/Show Controls above the list now applies canonical DANP Form Hide/Reveal to
every control of the active Source. This supersedes the 0.2.1 display-only bulk
button. If any effective geometry remains, Hide masks every defined edge and
explicit node; if none remains, Show clears canonical masks. All eyes derive
Hidden or On respectively. Show All intentionally reveals earlier individual
hidden portions too; it is not a saved visibility preset. The legacy operator ID
is retained, and its old viewport-only flag is cleared by the explicit bulk action.

Overlay/X-Ray/Show Hidden and Blender object/collection visibility remain display
options. They do not change masks, cuts or constraints. Hide All keeps the current
object/mode so Show All works even on an empty controller in Edit Mode. Edit Control
is disabled on Source when no effective handle remains, until controls are revealed.

Controller H hides selected canonical geometry; Alt-H reveals all from current
Source positions. Edge selection has edge intent: its selected endpoints are not
explicit node Hide, preserving intersecting enabled edges. Vertex selection has
node intent, releasing all incident edges under ADR-008. An overlapping logical
group observes the same canonical masks; it cannot override them.

Ctrl+Alt+Click selects a maximal visible span from the picked edge, stopping at
vertices with degree other than two in the effective network. Shift adds a span.
An uninterrupted closed loop selects completely. Logical names/membership do not
introduce artificial junctions. Menu/F3 can use a single selected/active edge;
MCP can supply the canonical Source edge ID. Selection never changes definitions,
canonical masks or Source geometry. Projected near edges can overlap, so selection
must remain visually reviewable; agents likewise must inspect mapping and topology.

## Scope

The complete front contour group and anatomical regional groups coexist as
overlapping selection conveniences, not a hierarchy of constraints. Phase 2
implements mapping, visibility and selection only. Patch display is phase 3 and
mesh deformation/proportional remains phase 4.
