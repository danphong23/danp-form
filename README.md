# DANP Form

DANP Form is a Blender add-on design for reshaping an existing template mesh through a sparse network of source-backed control lines.

The product idea is intentionally small:

```text
Source Mesh + control lines
          ↓
topology-derived patches
          ↓
move / rotate / scale selected control geometry
          ↓
interpolate displacement over adjacent patches
          ↓
write the result to the real Source Mesh
```

The **current patch shape at operation start is the geometric baseline**. DANP Form does not reconstruct a patch from sparse handles and does not continuously pull the model toward the original template. Proportional settings control how control motion spreads into an affected patch.

Enabled unselected control geometry holds its position. Hide a whole line or portion
to release its constraints and patch cuts; reveal it on the newly deformed Source.
See docs/product/leg-control-examples.md and ADR-008 for junction/partial-hide behavior.

This repository contains the redesigned specification and the Phase 1/2 prototype
add-on. Development follows the accepted five-phase roadmap: bootstrap;
controls/sync; patch visualization; Edit Mode deformation/proportional; human and
external-agent MCP validation with reference images. Start with
[implementation-plan.md](docs/roadmap/implementation-plan.md) and [tasks](tasks/README.md).

Version 0.2.5 displays DANP Form, offers model Init/Remove and keeps controller
topology fixed. Controller-to-Source deformation is still a Phase 4 task.
Existing `dan_form` extension/operator/data IDs remain compatible.
Edit Mode uses bulk ID/coordinate reads and cached overlay buffers; see the
[performance report](docs/testing/phase-02-edit-performance-report.md).
Controller Edit supports Ctrl+Alt+Click to select a span between junctions (Shift
adds), H/Alt-H for partial Hide/Reveal, and bulk Hide/Show synchronizing all eyes.
Hover picking preserves native selection until click, supports RMB/Esc cancel,
passes navigation through, and yields to native commands such as Box Select.
The optional thin cyan highlight follows native selection and Hide/Show; it has
no selection or input ownership. See the [UX audit](docs/testing/phase-02-pick-ux-audit.md).

## Start here

1. [`docs/product/product-definition.md`](docs/product/product-definition.md)
2. [`docs/core/invariants.md`](docs/core/invariants.md)
3. [`docs/core/control-model.md`](docs/core/control-model.md)
4. [`docs/core/patch-model.md`](docs/core/patch-model.md)
5. [`docs/core/selection-and-targets.md`](docs/core/selection-and-targets.md)
6. [`docs/core/interpolation-baseline.md`](docs/core/interpolation-baseline.md)
7. [`docs/testing/prototype-plan.md`](docs/testing/prototype-plan.md)
8. [`AGENTS.md`](AGENTS.md)

## Design authority

Product behavior is normative in `docs/product/` and `docs/core/`, except methods explicitly
labeled prototype candidates. Normative architecture/lifecycle and ADR documents define
data and transaction contracts. Candidates are testable and replaceable, not product
rules. Optional extensions cannot redefine core behavior.
