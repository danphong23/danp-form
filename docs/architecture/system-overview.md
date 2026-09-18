# System Overview

**Status: Normative architecture**

```text
           Source Mesh
  geometry + source-owned control definitions
          ▲                 │
          │ write           │ build/sync
          │                 ▼
  Deformation Operation ← Control Proxy
          ▲                 ▲
          │                 │
   canonical targets     User / AI
          ▲
          │
 Future reference fitting (target producer only)
```

## Persistent truth

Source-owned:

- current mesh coordinates/topology;
- persistent element IDs;
- logical control definitions;
- canonical hidden vertex/edge masks;
- Source/template UUID;
- minimal settings that must survive save/reload.

## Rebuildable state

- Control Proxy geometry;
- effective network/patch partition cache derived from persistent hide masks;
- topology distance caches;
- interpolation work buffers;
- overlays/diagnostics.

## Core services

Conceptual responsibilities:

- Context resolution — Source ↔ Proxy ↔ template identity.
- Persistent IDs — stable source element references.
- Control repository — create/remove definitions and whole/partial hide masks; derive enabled Source geometry.
- Proxy builder/sync — rebuild interaction geometry from Source.
- Patch service — derive face components from effective enabled control cuts.
- Target builder — selection/G/R/S/agent input → Dense Target Set.
- Deformation operation — capture P0, interpolate, preview, commit/cancel.
- Agent facade — same primitive actions without mouse simulation.

No service boundary requires a specific numerical interpolation family.
