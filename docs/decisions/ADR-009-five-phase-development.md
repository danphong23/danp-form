# ADR-009 — Five-phase development and controller lifecycle

**Status: Accepted — user agreement, 2026-09-18.**

## Decision

Develop in five phases: extension/sidebar/Source/controller; Source-backed control
creation and sync; topology patch visualization; Edit Mode deformation/proportional;
user and external-agent validation through MCP with reference images.

The controller object is a child of Source, sharing its local coordinate frame.
Object move/rotate/scale follows Source exactly once. This does not create parenting
between control definitions and does not change ADR-008 enabled/hidden constraints.

Phase 2 updates displayed controller coordinates from Source. Phase 4 supplies the
reverse interaction through canonical targets and transactions, followed by Source
to proxy resync. Controller is not independent geometric truth. View-aligned wire
controls remain 3D Source-backed vertices/edges, not independent 2D geometry.

Patch display toggles are UX only. Actual partition changes come from effective
control edges and topology, including DAN Form Hide/Reveal. A selected control
vertex influences graph-connected vertices in incident patches subject to fixed
constraints/proportional; no unique unbranched vertex chain is prescribed.

## Consequences

Basic install/control/patch UX can be tested before the numerical prototype. Phase 4
must pass geometry and quality gates before its interactive deformation is accepted.
Numeric facade implementation supports phase 4 tests and phase 5 MCP validation.
Sparse controls, advanced solvers and automatic reference fitting remain optional
extensions. Phase 5 reference fitting means human/agent-driven targets through core,
not mandatory image extraction/calibration. No new solver family is frozen here.
