# Multiple Templates and Context

**Status: Normative — see [ADR-014](../decisions/ADR-014-source-controller-ownership.md).**

Each registered Source has a stable template UUID and at most one primary
Controller. The Controller is the Source's direct child and shares its local
coordinate frame. The parent relation is the ownership link; there is no manual
linking step and no second Source-to-Controller pointer.

Context resolution:

- active Source → inspect its direct DANP-marked mesh children and accept exactly
  one child whose owner marker matches the Source UUID;
- active Controller → resolve only its direct parent, then validate the same
  one-child rule and UUID marker;
- agent call → resolve a unique, valid bound Source UUID; ambiguous UUIDs fail
  closed.

Never use object names, collection order, or the first UUID match as identity.
UUID is a namespace for persistent element/control IDs and agent handles; it does
not override the parent relation. A usable pair also requires unique Source UUID
among bound pairs and single-user editable Source and Controller mesh data.

Duplicate behavior is based on the scene state, independent of which Blender
operation created it:

- Mesh-only duplicate → unbound mesh. It cannot resolve the original
  Controller. DANP marks it as an unbound copy; Initialize clears copied DANP
  definitions/IDs and creates a fresh, empty pair.
- Complete Source/Controller pair → independent pair with a fresh UUID. The
  pair retains its local definitions and persistent IDs. The Controller remains
  parented to the copied Source.
- Controller-only duplicate → it does not acquire Source ownership. In a live
  session, the known extra Controller is detached while preserving its world
  transform; an ambiguous file loaded without that history is presented for
  explicit resolution.
- Shared editable mesh data → reject writes and require Make Single User.

If multiple valid pairs already share a UUID when a file is loaded, no creation
history exists to identify the original. DANP must block UUID-based operations
until the user chooses the pair to keep or make independent. It must never guess.
