# ADR-008 — Enabled Controls Hold; Hidden Controls Follow Source

**Status: Accepted by the product owner, 2026-09-18**

**Decision:** enabled unselected Source control vertices are stationary. Selected
node/span/strip/loop geometry moves; a selected target wins at shared junctions.
DANP Form Hide removes constraint and cut roles for hidden geometry. Reveal samples
current Source coordinates, not pre-hide positions. Whole and partial hiding share
canonical Source element masks defined in core/control-model.md.

**Reason:** select which contours hold and which follow the mesh using selection and
hide/reveal, without parenting, nested patches or a separate deactivate feature.

**Supersedes:** display-only DANP Form hiding, separate deactivate UI, automatic moving
targets on unselected dense vertices after sparse-knot edits, and weighting by logical
control memberships. Ordinary object/collection display hiding remains separate.

**Consequences:** persist masks; resample on reveal/rebuild; invalidate caches; make
hide/reveal undoable; freeze effective network during transforms. Validate G12–G16 and
Blender lifecycle cases. Final interpolation remains subject to prototype evidence.

Whole edge-backed controls hide by edge intent so junctions retained by other enabled
lines survive. Explicit node hiding disables all incident edges at the node. The
core/control-model.md mask rules compose on shared Source geometry; they are not
per-definition ownership. These clarifications preserve the agreed two-loop/line example.
