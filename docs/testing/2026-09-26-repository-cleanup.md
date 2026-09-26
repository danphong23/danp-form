# Repository inventory and cleanup — 2026-09-26

Reviewed source baseline: `f934069` / add-on 0.5.36. This maintenance change
does not modify runtime behavior, models, or the installed Blender extension.

## Removed generated artifacts

- Tracked root `dan-form-extension.zip`: stale 0.5.34 archive, 26 entries,
  no `LICENSE.md`. Removed from the working tree; still recoverable in Git.
- Ignored `dist/`: 0.5.35 and 0.5.36 archives, two checksum sidecars, and
  `installed_backup_0.5.34_before_0.5.36`. These are generated build/installation
  artifacts, not model data or source. Build a fresh archive after release cleanup.
- Python caches: 106 `.pyc` files, totaling 1,792,712 bytes, across source,
  scripts, tests and the old installation backup.

All recursive cleanup targets were resolved and checked to remain inside this
repository before deletion. Git metadata was preserved.

## Retained and clarified

- All runtime modules: `core/harmonic.py`, graph and proportional helpers
  are imported by the current solver; their presence is not unused-file evidence.
- Current regression suites, ADRs, contracts, roadmaps and dated verification
  reports. A historical report is evidence, not junk and not a current test result.
- Generated `docs/full-specification.md`, `docs-manifest.json`, and
  `MANIFEST_SHA256.txt`: referenced by documentation tools, intentionally retained.
- Legacy picker fixtures moved to `tests/history/` with explicit warnings.
  Their operators/properties are no longer registered in 0.5.36. The historical
  report links were updated; current release discovery is unchanged.
- Historical architecture/UX status is distinguished from current H01–H10
  references. The obsolete H02 "known gap" text in module boundaries now points
  to the implemented adapters and their actual report.

## Prevention

- One release builder: `scripts/release_package.py` (Python 3.11+), output in
  ignored `dist/`. The PowerShell script delegates to it for compatibility.
- Runtime packaging selects Python modules explicitly, excluding accidental
  extra files in the source package. Documentation/tasks remain included.
- Ignore the legacy root archive and tool caches. Documentation hash generation
  and validation exclude build/cache/Git directories so generated backups cannot
  become part of the authoritative document inventory.

## Remaining release preparation

`LICENSE.md` is still a design-era placeholder, while the manifest declares
`GPL-3.0-or-later`. It requires replacement with the actual distribution license
and appropriate copyright/dependency notices before public packaging. This is
a release-content task, not a reason to delete the file during cleanup.

No add-on runtime or Blender UX regression was rerun for this inventory.
Documentation validation passed: 84 consolidated modules, 112 documents,
relative links and both hash manifests consistent. No identical standalone
Markdown files were found in the docs/tasks/test inventory; the consolidated
specification is an intentional generated copy.
No new release archive was built and no GitHub publication was performed.
