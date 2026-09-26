# Third-Party Notices

DANP Form does not bundle third-party source code or binary libraries.

The add-on uses Blender's Python API and Python standard-library modules. It
also attempts to import NumPy as an optional acceleration for the deformation
solver. When NumPy is unavailable, the solver uses its pure-Python fallback.
NumPy is not included in the DANP Form extension archive; this project does not
modify or redistribute it. Refer to the Blender distribution for notices that
apply to libraries bundled with Blender itself.
