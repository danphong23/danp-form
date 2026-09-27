# H09 — Large Source preview benchmark, 2026-09-27

## Result

The representative background preview is below the provisional 40 ms P95
guardrail. This closes the fresh background measurement gap for this fixture,
but it does **not** close the native UI/GPU performance or overlay gates.

The benchmark ran Blender 5.2.1 LTS on Windows 11 against an unsaved temporary
copy of `character_test_compare.blend`. The saved Source has 1,698 vertices, 3,392
edges, 1,696 faces, 49 control definitions and two Shape Keys. The benchmark
reset visibility only in that temporary copy; 726 effective control vertices
and 812 edges were selected. The active deformation target was `Key 1`.

## Measurements

Nine recorded background processes each performed four warm-up previews and 30
timed full-workflow previews, followed by one confirm/commit measurement.
Every preview affected the complete 1,698-vertex Source scope. The last six
runs used the guarded, reproducible benchmark fixture; the first three used the
same measurement path before it was packaged in that fixture.

| Run | Preview median | Preview P95 | Confirm/commit | Process peak working set |
| --- | ---: | ---: | ---: | ---: |
| 1 | 20.76 ms | 29.99 ms | 2.22 ms | 277.43 MiB |
| 2 | 26.04 ms | 32.99 ms | 1.90 ms | 277.17 MiB |
| 3 | 21.36 ms | 35.49 ms | 1.81 ms | 278.77 MiB |
| 4 | 16.89 ms | 32.66 ms | 1.66 ms | 278.49 MiB |
| 5 | 17.42 ms | 18.66 ms | 1.86 ms | 278.54 MiB |
| 6 | 17.50 ms | 18.37 ms | 1.67 ms | 278.26 MiB |
| 7 | 19.37 ms | 24.02 ms | 1.95 ms | 279.10 MiB |
| 8 | 17.96 ms | 18.86 ms | 1.89 ms | 280.21 MiB |
| 9 | 17.20 ms | 20.52 ms | 1.88 ms | 280.78 MiB |

Process peak working set is the Windows process-lifetime high-water mark and
includes Blender startup and file loading. In these runs it was 277.17–280.78
MiB. Current working set after the guarded runs was 273.05–278.58 MiB. The
process measurement does not isolate incremental preview allocations.

The provisional background guardrail is **P95 ≤ 40 ms**. It is based on the
highest of nine runs plus a 12.7% variance margin, and should only be compared
using Blender 5.2.1 and comparable hardware. This is a regression gate, not a
promised viewport frame rate.

## Optimization and verification

Profiling identified Python loops in the all-control affine fit and per-vertex
transform application as the dominant CPU work. When Blender provides NumPy,
the solver now vectorizes the same regularized affine fit, sample validation and
scope transform. The original dependency-free implementation remains the
fallback. A regression compares both results on a fully 3D affine sample set.

- Pure-Python core suite: 20/20 checks passed; NumPy was unavailable, so this
  verified the fallback.
- Blender 5.2.1 core suite: 20/20 checks passed with Blender-bundled NumPy,
  including accelerated/fallback parity.
- Guarded benchmark: 30 samples per run; all nine recorded runs were below 40 ms P95.
- The fixture script refuses UI Blender and refuses any `.blend` outside the
  system temp directory or without the `danp_h09_` prefix. It does not save.

Run the fixture benchmark with:

```powershell
python tests/run_release_gates.py `
  --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
  --benchmark-project "$env:TEMP\danp_h09_character.blend" `
  --report docs/testing/2026-09-27-release-gates-h09-benchmark.json
```

The `--benchmark-project` argument must point to a disposable copy. It is
separate from the small generated fixture used for the ordinary integration
suites. The combined runner remains `INCOMPLETE` until the C02 UI
keymap/visibility Undo-Redo/save-reopen check, H08 GPU review, native UI
performance measurement, and maintainer attribution are addressed.

One intervening full-runner attempt measured 49.97 ms P95 because the runner
executed the benchmark after all 11 Blender suites. The immediately following
standalone run was 29.62 ms P95. The benchmark now runs first; the latest
post-commit combined runner recorded 20.52 ms P95. This test-order correction
keeps the gate focused on add-on cost instead of accumulated test load; the
outlier remains recorded here rather than hidden by raising the threshold.

## Limits

Background measurements exclude native mouse input, viewport redraw and GPU
overlay drawing. They do not prove modal UI latency, animation playback
performance or fault recovery in the GPU callback. Those remain direct UI gates.
