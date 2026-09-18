# Terminology

**Status: Normative**

- **Source Mesh** — the real editable Blender mesh. Its current coordinates are the final geometric truth.
- **Template** — a Source intended for reuse. It may have an optional original snapshot for reset/compare.
- **Control Definition** — source-owned metadata identifying source vertices/edges that form a control.
- **Control Component** — one connected point/chain/loop/branch inside a logical control.
- **Control Proxy** — rebuildable points/edges shown to the user/agent for selection and transforms.
- **Proxy Knot** — an editable proxy vertex bound to an actual source control vertex.
- **Proxy Span** — a proxy edge that represents an ordered run of one or more source control edges between two proxy knots.
- **Enabled Control Network** — effective Source control edges/vertices after applying canonical hide masks; called active in older drafts.
- **DANP Form-hidden Control Geometry** — stored Source-backed definitions temporarily released from constraints/cuts, allowed to follow mesh deformation.
- **Reveal** — resample current Source positions and restore effective roles; not reset or refine.
- **Patch** — connected component of source faces after adjacency across effective enabled control edges is removed.
- **Operation Rest (`P0`)** — snapshot of current Source coordinates at operation start.
- **Control Target (`Q`)** — target position assigned to a source control vertex for the current operation.
- **Dense Target Set** — one selected or stationary target per enabled Source control vertex in scope; span coverage expands selection, not movement of unselected vertices.
- **Affected Patch Set** — patches incident to moving target geometry for the current operation.
- **Captured Patch Scope** — patches incident to selection at invoke; bounds snapshot/writeback and prior-preview cleanup even when current affected scope shrinks.
- **Proportional** — user-controlled attenuation of patch displacement as topological distance from moving targets grows.
- **Original Snapshot** — optional historical template state used for reset/compare only.
