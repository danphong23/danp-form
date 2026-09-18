# Security and Data Handling

The core design is local/offline. Meshes, `.blend` data, control metadata, and reference images must not be uploaded by the core add-on.

Malformed metadata, stale mappings, or failed deformation must fail safely: preserve or restore Source geometry and return an explicit recoverable status where possible.
