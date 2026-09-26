# H10 — Installable package verification

**Result: PASS for the functional install candidate.**

- Add-on/manifest version: 0.5.35; Blender minimum: 5.1.0.
- Package layout: flattened Blender extension root with `__init__.py`,
  `blender_manifest.toml`, runtime modules, license, English/Vietnamese README,
  changelog, and the linked docs/tasks.
- Blender 5.2.1 LTS smoke test extracted the ZIP into an isolated add-on folder,
  imported it, registered it, and unregistered it successfully.
- Validator checks ZIP integrity, unique/safe paths, required root files,
  extension ID, matching manifest/`bl_info` version, and absence of tests,
  bytecode, and cache directories.
- Documentation validator checks consolidated specification, relative links,
  and both generated SHA256 manifests.

The generated archive and its commit/hash sidecar are delivered under `dist/`;
build it with `python scripts/release_package.py`. The H09 GPU-overlay review and
combined large-mesh P95/peak-memory measurement remain unverified, so this is a
functional candidate and carries no performance-certified production claim.

## Historical status

This report records the 0.5.35 candidate tested on 2026-09-25. It does not
describe the current 0.5.36 package, and no generated archive is kept in the
repository's `dist/` directory. Rebuild and validate a candidate from the
current checkout; see the 2026-09-26 package report for the latest result.
