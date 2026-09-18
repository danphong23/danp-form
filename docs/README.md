# Documentation Map

## Document classes

- **Normative** — required product behavior. Implementation must follow it.
- **Prototype baseline** — a concrete first method used to test the product behavior; replaceable if evidence shows failure.
- **Extension** — future capability that consumes core primitives without changing them.
- **Open decision** — intentionally not frozen.

## Read order

For development, begin with the [five-phase roadmap](roadmap/implementation-plan.md),
[development contract](roadmap/development-contract.md) and
[phase tasks](../tasks/README.md). ADR-009 records the accepted sequence, Source-child
controller, patch display semantics and reference-based phase-5 validation.

Current Phase 2 UI uses the [native list UX](roadmap/phase-02-native-list-ux.md),
with [task checklists](../tasks/phase-02-native-list-ux.md) and Gate P2-UX before Phase 3.
The [0.2.1 sidebar report](testing/phase-02-sidebar-performance-report.md) records
the performance fix, direct row selection, viewport visibility and Edit/Back navigation.
Remaining gate checks must be supported by their own live evidence.

1. `product/product-definition.md`
2. `product/terminology.md`
3. `core/invariants.md`
4. `core/control-model.md`
5. `core/patch-model.md`
6. `core/selection-and-targets.md`
7. `core/proportional.md`
8. `core/interpolation-baseline.md`
9. `core/operation-semantics.md`
10. `architecture/system-overview.md`
11. `architecture/data-model.md`
12. `architecture/mapping-and-sync.md`
13. `blender/interaction.md`
14. `agent/shared-primitives.md`
15. `testing/prototype-plan.md`
16. `decisions/open-decisions.md`

Also read product/leg-control-examples.md and decisions/ADR-008-hide-releases-control.md
for the agreed enabled/hidden control behavior. Other modular docs cover lifecycle,
API, testing and extensions. full-specification.md includes all docs modules (not tasks)
in the order recorded by its source markers and is not an independent source of truth.

After editing modules, run scripts/regenerate-docs.ps1 from PowerShell 7 to regenerate
the consolidated specification and both hash manifests. It preserves existing source
order and appends new docs modules; it does not modify authoritative module content.

Then run scripts/validate-docs.ps1 to check consolidated coverage/content, Markdown file
links and both hash manifests. See testing/documentation-audit.md for the latest review.
File validation is not a substitute for geometry or Blender runtime tests.
