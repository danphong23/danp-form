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
  Their viewport picker classes were not registered in 0.5.36. The dead
  implementations, screen-picking helpers and transient overlay preview state
  have now been removed. The historical report links were updated; current
  release discovery is unchanged.
- Sidebar, UIList, PropertyGroup and menu classes now live in `ui/panel.py`;
  `operators.py` re-exports their existing symbols and registration remains
  unchanged.
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

## Addendum — release-license preparation

The design-era `LICENSE.md` placeholder has been replaced with the complete GNU
GPL version 3 text, matching `GPL-3.0-or-later` in `blender_manifest.toml`. The
text is the unmodified GPLv3 supplied in Blender's license bundle; the file also
links to the authoritative [GNU license page](https://www.gnu.org/licenses/gpl).
The archive now includes `THIRD_PARTY_NOTICES.md`, which records that NumPy is
optional, not bundled, and has a pure-Python solver fallback. The repository
still does not identify a named copyright holder, so this does not certify
public release readiness.
