# Advanced Interpolation Options

**Status: Experimental options only**

The baseline in `../core/interpolation-baseline.md` is intentionally simple. Promote a more complex method only after a reproducible failure and benchmark evidence.

## Failure → smallest next experiment

### Visible bands or sampling-density artifacts

Try smoother displacement reconstruction or improved geometric sampling while preserving enabled unselected hard constraints, selected targets, hide masks, grouping independence and proportional placement. Do not fix artifacts by moving unselected control vertices.

### Poor behavior on irregular multi-boundary patches

Try a smoother interpolation-coordinate field. Harmonic/biharmonic coordinates are candidates, not product requirements.

### Excessive shear or detail loss under large rotation/nonuniform change

Try a constrained local differential/detail relaxation **after** the baseline displacement and prove that:

- hard control targets remain exact;
- no-target stays a no-op;
- it does not pull toward the historical template;
- the failing benchmark improves without making ordinary cases less predictable.
- finite-radius zero-influence vertices and captured-scope preview cleanup remain exact;
- logical grouping, hidden masks and shared stationary control constraints remain unchanged.

Laplacian or ARAP-like methods are possible experiments here. SVD/iterative solvers are implementation consequences of an experiment, not core invariants.

### Performance failure

Optimize distance caching/data layout or move a validated method to an accelerated backend. Do not redesign user behavior to accommodate a solver.
