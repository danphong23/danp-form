# DANP Form 0.5.36

DANP Form is a Blender extension for shaping a Source mesh through a sparse,
editable Controller child. It uses Blender's normal vertex and edge selection
and G/R/S tools, then transfers the control motion to the Source surface.

## Install

In Blender Preferences, choose **Install from Disk** and select this DANP Form
ZIP. Enable the extension, then open a 3D View and choose **DANP Form** in the
sidebar (`N`).

## First use

1. Select a mesh to use as the Source.
2. In the DANP Form panel, initialize its Controller.
3. Edit the Controller and create controls from selected Source vertices or
   edges.
4. Select Controller handles and use Blender's normal **G**, **R**, or **S**.
5. Use the panel's visibility controls to hide, reveal, or manage control lines.

Every Source owns its Controller child. Duplicating a mesh does not make its
controls share a binding; initialize the duplicate separately. Shape Key target
changes are explicit in the panel.

## Topology and recovery

Changing Source topology can invalidate persistent control IDs. DANP Form pauses
deformation when it detects a stale mapping. Undo the topology edit to restore the
previous mapping, or use Validate/Repair or Reset DANP Controls to create a new
mapping on the current topology. **Reset Model** returns to the captured Init
pose and is a separate, undoable action.

This build is an installable functional candidate. Direct UI keymap/visibility
Undo/Redo/save-reopen, GPU overlay review, native UI performance, and final
maintainer attribution are still under review; do not treat it as release
certification.

## License

DANP Form is distributed under GPL-3.0-or-later; the package includes the full
license text and third-party notices for optional NumPy acceleration.
