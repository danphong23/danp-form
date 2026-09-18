# ADR-004 — Each Operation Uses Current Committed Shape as Immutable Rest

**Decision:** capture current Source at operation start and use it for every preview in that operation. The original template is reset/compare data only.

**Reason:** prevents preview drift and keeps sequential modeling cumulative rather than modifier-like.
