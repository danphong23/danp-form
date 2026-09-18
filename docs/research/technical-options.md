# Technical Options — Non-Normative Notes

Earlier design drafts made harmonic interpolation plus similarity-preserving ARAP a normative production solver. That was premature because the product behavior had not first been validated with a simpler displacement model.

Useful method families remain available as research tools:

- graph/geodesic distances for topology-aware locality;
- Shepard/inverse-distance blending for a simple baseline;
- harmonic/biharmonic coordinates for smoother interpolation;
- Laplacian editing for differential-detail preservation;
- ARAP/local-global methods for strong rotational preservation;
- cages/lattices for alternate control representations.

None is selected by product definition alone. The prototype matrix in `../testing/geometry-cases.md` determines whether the baseline is sufficient and which failure deserves the next experiment.
