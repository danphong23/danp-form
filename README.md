# DANP Form

Current readiness: C01 safety gates are complete and C02 visibility/selection
fixes pass static and Blender background suites. Blender UI keymap/Undo-Redo,
GPU overlay and representative performance gates remain open. See the
[2026-09-26 review](docs/testing/2026-09-26-comprehensive-addon-review.md) and
[cleanup tasks](tasks/addon-cleanup-review.md) before release or new Inspect/preview UX.

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

This repository contains the redesigned specification and the Phase 1–4 prototype
add-on. The current deformation baseline uses transform ownership: a patch with
one incident control follows that control's G/R/S transform; shared patches blend
selected transforms against unselected stationary controls. Development follows
the accepted five-phase roadmap: bootstrap;
controls/sync; patch visualization; Edit Mode deformation/proportional; human and
external-agent MCP validation with reference images. Start with
[implementation-plan.md](docs/roadmap/implementation-plan.md) and [tasks](tasks/README.md).

Version 0.5.36 targets Blender 5.1 or newer. DANP Form keeps a child Controller
bound to one Source and edits the active deformation target: Base when there are
no Shape Keys, otherwise the explicitly selected Basis or Shape Key. Target
selection, native G/R/S deformation, cancel and Undo share the transaction path.
The complete current evidence and remaining release limits are in the
[release-hardening roadmap](docs/roadmap/release-hardening-plan.md).
The target contract for base/Basis and relative/absolute Shape Keys is
[ADR-017](docs/decisions/ADR-017-deformation-target-contract.md); its safe
read/write implementation and runtime verification belong to H02.
Existing `dan_form` extension/operator/data IDs remain compatible. After topology
changes, validate or explicitly repair the mapping before editing. Duplicate
Source meshes do not inherit a live Controller binding; initialize a separate
Controller for the new Source. The Controller is its Source's direct child.
Initialization also works while the Source is in Edit Mode: DANP Form flushes
the live Edit Mesh, creates the child Controller, and restores Edit Mode.
If an older incomplete Init left a detached Controller, select that object and
use **Unbind DANP, Keep Mesh** before rebuilding the Source's Controller.
Edit Mode uses bulk ID/coordinate reads and cached overlay buffers; see the
[performance report](docs/testing/phase-02-edit-performance-report.md).
Controller Edit uses Blender's native vertex/edge selection and G/R/S transforms.
H hides selected handles, Shift-H hides unselected handles, and Alt-H reveals
canonical DANP visibility. The list eye and bulk Hide/Show use the same masks.
Blender's separate F3/native Hide changes transient proxy display flags; Alt-H
restores the canonical Controller display. The optional thin cyan highlight follows native selection and Hide/Show;
it has no selection or input ownership. The historical Ctrl+Alt+Click span and
hover picker described in the [Phase 2 UX audit](docs/testing/phase-02-pick-ux-audit.md)
are not registered in the current build.
Phase 3 now derives Source face patches from the effective control network and can
show them as a display-only translucent overlay. See the [patch report](docs/testing/phase-03-patch-report.md).
Patch connectivity and GPU submissions are cached so Show Patches does not rebuild
all face records during an Object/Edit mode switch.

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

## License

DANP Form is distributed under [GPL-3.0-or-later](LICENSE.md), matching the
extension manifest. See [third-party notices](THIRD_PARTY_NOTICES.md) for the
optional NumPy acceleration and dependency inventory.
