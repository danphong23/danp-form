# ADR-002 — Control Proxy Is Rebuildable Input

**Decision:** Source owns control definitions. One lightweight proxy per Source is the normal interaction object and can be rebuilt without changing Source geometry.

**Reason:** separates dense production topology from sparse interaction while avoiding a second geometric source of truth.
