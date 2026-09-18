# Leg Control Examples

**Status: Normative constraints/scope; interior motion depends on proportional and method**

A limb has upper loop U, lower loop L and longitudinal line D. These are example labels,
not core roles. D alone may not divide a cylindrical surface into two patches.

## Scale U while D is enabled

U hits its selected scale targets. L and unselected D vertices remain at P0. The U–D
junction is selected through U, so it moves too; other D vertices remain fixed.
Adjacent patch interiors deform using proportional and current patch shape.
No fixed half-motion at the midpoint is promised.

## Scale U and L while D is enabled

Both loops scale. Unselected D interior remains fixed, so it may hold a bulge between
the loops. Both selected loop–D junctions move with the loops.

## Hide D, then scale U or both loops

D edges stop cutting. Its interior vertices stop anchoring unless other enabled
geometry also supports them. Recompute patches. With U selected, L stays fixed;
with U and L selected, both loops move. Former D vertices follow allowed patch motion
under proportional, not a stored old contour.

Hide whole D uses edge intent, not Hide Nodes on its junctions. Thus U/L remain intact.
Explicitly hiding a junction node instead opens every incident control edge there.

Reveal D after commit: sample the current leg contour and restore its roles there.
No snap to old positions is allowed.

## Hide only D's middle segment

That portion stops cutting/holding; retained portions still constrain. Shared endpoints
can stay fixed through retained edges. Include endpoint nodes in Hide when they too
should be released. Actual connectivity decides whether patches merge.

## Pull part of D inward

Select a strip/span. Its vertices receive targets; other enabled geometry stays fixed,
except junctions included in the selection. No front/side deformation mode is required.

A bump inside a patch follows patch deformation. Create additional controls around/on
it for separate manipulation; the core does not infer a protected feature.
