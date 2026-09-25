# H09 — Operational release gate report

**Operational result: PASS. Full release extras: INCOMPLETE.**

- Blender 5.2.1 LTS on Windows 11.
- Source revision: `ece81932388c6645583e60bb5646631e441b9740`.
- Add-on version in `bl_info` at test time: `0.5.31` (version mismatch is
  corrected in H10).
- The supplied project was copied to a temporary directory by the runner before
  the native-transform fixture. The original dirty project was not saved or
  changed.

## Passed

- 9 static suites, 60 checks.
- 8 Blender background suites, 169 explicit assertions. This includes all-control
  Scale, Shape Key behavior, ownership safety, topology recovery, target UX,
  agent target API, runtime registration/cache lifecycle, and native
  G/R/S plus cancel/Undo/Redo on a disposable copy.
- Harness self-test intentionally raised an assertion and was correctly
  classified as a failure.
- Direct UI acceptance for H04, H05, and H07 is linked from their respective
  reports.

## Not run

- GPU-backed overlay error injection/review.
- A fresh large-mesh release benchmark that records complete preview median/P95
  and process peak memory together.

The combined runner returns `INCOMPLETE` when either item is absent; it does not
hide that result. The executed operational suites all pass. This report supports
an installable functional candidate, not a performance-certified production
release.
