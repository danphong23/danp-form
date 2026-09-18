# Sparse Controls and Simplification

**Status: Normative behavior; optional after exact controls are validated**

Simplify/refine changes handles only, not Source topology, enabled control geometry,
hidden masks or stationary constraints. Knots bind to real Source vertices; spans
store actual dense Source paths.

Selecting a span selects its represented enabled vertices: G/R/S applies T(P0[i]).
Selecting a knot selects only its bound vertex. Omitted enabled vertices remain fixed.
The earlier knot-only linear displacement expansion is superseded. Select spans for
broad changes or hide geometry to release it.

Split spans at visibility transitions and junctions: no editable span may cross a
hidden gap. Dense control overlays may show the actual curve under coarse straight edges.
Mandatory knots include endpoints, junctions and enabled/hidden transitions; choosing
other knots is a later engineering heuristic.

Refine exposes existing handles, not hidden controls. It must not clear masks or create
Source vertices. Simplify/refine alone deforms nothing. Preserve logical selection
where unambiguous; reveal resamples current Source, including omitted vertices.
