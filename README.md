# DAN Form

DAN Form is a Blender add-on design for reshaping an existing template mesh through a sparse network of source-backed control lines.

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

The **current patch shape at operation start is the geometric baseline**. DAN Form does not reconstruct a patch from sparse handles and does not continuously pull the model toward the original template. Proportional settings control how control motion spreads into an affected patch.

Enabled unselected control geometry holds its position. Hide a whole line or portion
to release its constraints and patch cuts; reveal it on the newly deformed Source.
See docs/product/leg-control-examples.md and ADR-008 for junction/partial-hide behavior.

This repository contains the redesigned specification only, without production
add-on code. Development follows the accepted five-phase roadmap: bootstrap;
controls/sync; patch visualization; Edit Mode deformation/proportional; human and
external-agent MCP validation with reference images. Start with
[implementation-plan.md](docs/roadmap/implementation-plan.md) and [tasks](tasks/README.md).

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
