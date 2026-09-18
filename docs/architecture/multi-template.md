# Multiple Templates and Context

**Status: Normative**

Each registered Source has a stable template UUID and at most one primary Control Proxy.

Context resolution:

- active Source → resolve its SourceRecord and Proxy;
- active Proxy → resolve its owning Source UUID;
- agent call → explicit Source/template UUID.

Never rely on object names as identity.

The prototype rejects shared editable meshes with SOURCE_NOT_EDITABLE and a Make Single
User recovery action, not an automatic copy. Source UUID plus local element/control ID
is the canonical key. Independent duplicates may retain local IDs/masks but need a new
Source UUID and independent proxy. Validate duplicate UUID collisions before editing;
never choose owners by name/list order or let a copied proxy target the original Source.

If a Source is duplicated as an independent editable mesh, the duplicate receives a new template UUID while retaining copied control definitions/persistent topology IDs within its own namespace. Shared editable mesh datablocks should be made single-user before registration to avoid two Sources mutating the same geometry unexpectedly.
