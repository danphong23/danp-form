# Module boundaries

The add-on is being split without changing the Source/Controller contract or
the `dan_form.*` operator IDs.  Persistent Source data remains authoritative;
runtime caches and transaction buffers are disposable.

## Current extraction boundary

- `constants.py` owns storage keys, attribute names and extension identifiers.
- `runtime.py` owns process-local caches, guards, transaction handles and
  callback state.  It never becomes a second geometry store.
- `storage.py` owns JSON-backed control definitions, masks and Source UUID
  helpers.  It does not calculate patches or write viewport UI state.
- `core/controls.py` owns pure effective-control and mask resolution over
  persistent IDs.
- `core/patches.py` owns pure face-graph partitioning; Blender code only adapts
  Mesh/BMesh data into face records and caches the returned runtime result.
- `core/graph.py` and `core/proportional.py` own the replaceable graph-distance
  and attenuation candidates used by the existing deformation facade.
- `blender/context.py` resolves the active Source/controller pair without
  trusting stale scene pointers.
- `blender/proxy.py` owns controller rebuild, Source-to-proxy sync and topology
  recovery. It receives mapping/selection functions through `ProxyDeps` rather
  than importing the facade.
- `blender/workflows.py` owns deformation transactions, mask mutation and
  Source writeback. It receives mesh/proxy/UI-independent callbacks through
  `WorkflowDeps`.
  The H02 target adapter specified by
  [ADR-017](../decisions/ADR-017-deformation-target-contract.md) defines the
  base/Basis/Shape Key coordinate contract. H02 implemented explicit target
  resolution in `blender/mesh.py`, reads in `blender/selection.py`, writes here,
  and historical target restoration in `blender/lifecycle.py`. See the
  [H02 report](../testing/2026-09-25-h02-target-io-undo.md) for verified scope;
  report evidence does not automatically certify every later revision.
- `registration.py` owns Blender class/property/handler/keymap registration;
  `blender/lifecycle.py` owns depsgraph/load/undo/redo callbacks and runtime
  invalidation. The root facade only passes itself as the compatibility API
  object.
- `operators.py` is the compatibility facade and keymap-registration adapter.
  Its `bind()` hook supplies the merged workflow adapters after package import;
  it re-exports action classes for registration and compatibility.
- `operator_actions/` groups registered operators by responsibility: structural
  edits, selection, visibility, deformation, Shape Keys and navigation. Each
  module receives workflow adapters through `bind()` and owns no persistent
  state. Unregistered viewport-picker prototypes and their hover cache were
  removed; historical experiments remain under `tests/history/`.
- `ui/panel.py` owns the PropertyGroup, UIList, menus and sidebar layout. It
  receives compatibility adapters through `bind()` and is re-exported by
  `operators.py` so registration and existing private facade callers retain
  the same class symbols. The panel rename callback writes only the selected
  control name to Source storage.
- `ui/overlay.py` owns viewport drawing and display-only patch batches. It has
  the same bind boundary and never changes Source geometry.
- `__init__.py` remains a compatibility facade for Blender adapters, core
  geometry, operators and UI modules. Lifecycle callbacks are no longer defined
  in the facade.

Existing scripts and live regression checks can continue to use the old private
facade names during the migration. New modules must import runtime state through
the runtime module so assignments cannot silently diverge from the shared state.

## Target boundary

`core` will receive IDs, connectivity, masks, coordinates and targets rather
than Blender objects. `blender` will adapt Mesh/BMesh, Source storage, proxy
sync and context. Operators and UI will only resolve user input and present
results. Agent and human commands will enter the same workflow primitives.

The extension package has `__init__.py` at its root, so packaging copies the
complete contents of the source package beside it. This is required for relative
imports and for future `core`, `blender`, `operators` and `ui` subpackages.

## Compatibility rules

Persistent keys, Source IDs, operator IDs, controller parenting and undo-visible
behavior stay unchanged during extraction. A refactor is accepted only when the
static suite, package contents and the existing open-Blender regression workflow
remain usable. Numerical interpolation changes are a separate task.
