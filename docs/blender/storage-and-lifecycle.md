# Blender Storage and File Lifecycle

**Status: Implementation-ready behavior**

Persist Source element IDs as mesh attributes and project/control records as registered properties attached to the Source object/mesh. Proxy metadata only needs enough information to resolve its Source and per-element bindings; all meaningful control definitions remain Source-owned.

On save/load:

- Source geometry/metadata and canonical hidden vertex/edge masks persist;
- proxy may persist or be rebuilt;
- runtime patch/distance/interpolation caches are discarded/recomputed.

On undo/redo:

- clear transient caches;
- at the next sync boundary validate Source metadata and resample/rebuild Proxy;
- recovery synchronization must not create a second undo entry.

On Source deletion, proxy may be deleted/orphan-marked. On Proxy deletion, Source remains valid and can rebuild it.

Hide/reveal is its own undoable state edit with zero Source coordinate changes. Undo/redo
restores masks and invalidates network/patch/constraint caches. Proxy rebuild and load
must not reveal everything or recover old hidden coordinates.
