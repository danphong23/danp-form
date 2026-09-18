# ADR-003 — Patches Are Derived from Enabled Source Control Edges

**Decision:** remove face adjacency across effective enabled control edges (hidden edges excluded; see ADR-008) and use connected components as patches. No manual barrier flag is required in core.

**Reason:** matches the intended topology rule, including open chains that do not actually separate a surface.
