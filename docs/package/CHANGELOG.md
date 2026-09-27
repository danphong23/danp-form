# DANP Form — Package Changelog

## 0.5.36

- Initialize a Controller child from Object Mode or Source Edit Mode, with
  rollback if initialization fails.
- Keep Shape Key target handling explicit and route edits through the shared
  deformation transaction.
- Use Blender-native vertex/edge selection and G/R/S; align list, keyboard, and
  visibility actions with the same control masks.
- Make topology validation and repair explicit. Mesh duplicates require their
  own Controller binding.
- Log viewport overlay draw failures once per failure streak and clear stale
  display batches without interrupting the viewport.

This is an installable functional candidate. See the package README for open
release gates.
