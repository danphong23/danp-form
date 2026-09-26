# ADR-010 — Bulk canonical visibility and junction spans

**Status: Accepted — explicit user request, 2026-09-18.**

**Implementation note (2026-09-26):** The standalone viewport span/hover picker
described below was prototype code that was never registered in 0.5.36. Its
implementation and preview cache were removed during cleanup. Treat that picker
paragraph as a historical design proposal, not a current interaction contract;
reintroducing it requires a separate UX decision and current Blender UI tests.

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

Controller H hides selected canonical geometry; Shift-H keeps the selected
handles and canonically hides the rest; Alt-H reveals all from current Source
positions. These shortcuts share the same Source-backed visibility rules as the
list eye and bulk actions. Blender's separate F3/native Hide operator changes
transient proxy display flags only; Alt-H restores the canonical Controller
display. Edge selection
has edge intent: its selected endpoints are not
explicit node Hide, preserving intersecting enabled edges. Vertex selection has
node intent, releasing all incident edges under ADR-008. An overlapping logical
group observes the same canonical masks; it cannot override them.

The planned viewport picker selects a maximal visible span from the picked edge,
stopping at vertices with degree other than two in the effective network. The
behavior is not shipped. Selection from the list and Blender mesh selection are
the supported routes; any future viewport picker must preserve the rule that
selection never changes definitions, canonical masks or Source geometry.

## Scope

The complete front contour group and anatomical regional groups coexist as
overlapping selection conveniences, not a hierarchy of constraints. Phase 2
implements mapping, visibility and selection only. Patch display is phase 3 and
mesh deformation/proportional remains phase 4.
