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

An ownership marker alone is insufficient authority to delete a mesh object.
When Source is missing or ownership is ambiguous, lifecycle handling keeps
objects in the scene, marks the relationship stale and offers explicit
recovery. H03 implements this in load/depsgraph handlers; the recovery action
can unbind stale markers while preserving the mesh. On Proxy deletion, Source
remains valid and can rebuild it. Interactive Undo of the recovery button is
still a separate UI check.

If Source topology changes outside DANP, the stored ID mapping is kept intact
but the pair enters a paused state. Commands do not write against stale array
indices. Undo restores the previous Source topology and mapping; Reset DANP
discarding the old definitions and rebuilding the controller is the explicit
repair operation for the current topology.

Hide/reveal is its own undoable state edit with zero Source coordinate changes. Undo/redo
restores masks and invalidates network/patch/constraint caches. Proxy rebuild and load
must not reveal everything or recover old hidden coordinates.
