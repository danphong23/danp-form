# Reference Fitting Extension

**Status: Extension — not part of the first core prototype**

Reference fitting may use front/side/other images or 3D targets to calculate where selected controls should go. It must stop at target generation.

```text
reference evidence
      ↓
control target positions / transforms
      ↓
normal DANP Form target expansion
      ↓
normal patch interpolation
      ↓
Source Mesh
```

Reference code must not:

- write arbitrary Source vertices directly;
- maintain a separate deformation solver;
- introduce front/side/anatomy semantics into core controls;
- bypass operation rest, patch scope, proportional, cancel, or undo.

Camera calibration, silhouette extraction, correspondences, and multi-view optimization are separate extension problems and should be designed only after core control deformation is validated.

The accepted phase-5 test uses references without requiring this automated extension:
human or external agent observes front/side images, creates ordinary controls and
chooses target positions through the shared core path. A front/side contour is a
normal Source-backed control line, not a special solver boundary type.
