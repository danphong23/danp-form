# Mapping, Persistent IDs, and Source/Proxy Sync

**Status: Normative**

## Persistent identity

Do not use Blender element index as long-term control identity. Assign integer attributes on Source points/edges (and optionally faces) and use monotonic counters per Source.

Suggested names:

```text
.dan_form_vid
.dan_form_eid
.dan_form_fid   # optional
```

## Proxy binding

Every proxy knot stores the Source vertex ID it represents. Every proxy span identifies one control component and the ordered Source vertex/edge run it represents.

The controller object is parented directly to Source with matching Source-local
coordinate frame and no extra object offset. Source object transforms carry it once;
they are not control-edit operations. Proxy wires are 3D vertex/edge geometry with
no faces, even when users draw/select contours from front/side views. Exact proxy
is implemented first; sparse spans remain optional future representation.

## Sync boundaries

Before transform, hide/reveal, simplify/refine, agent target query, or explicit validation:

1. resolve Source/Proxy pair;
2. validate Source topology generation/fingerprint;
3. validate persistent IDs/control membership;
4. rebuild proxy if missing/corrupt but definitions are valid;
5. copy current Source positions to proxy knots;
6. for deformation only, resolve selection and capture P0/potential incident-patch scope.

After commit, resync proxy from the newly committed Source.

## Coordinate changes outside DAN Form

Safe when topology remains valid. Visible proxy coordinates must refresh from Source
after external coordinate edits, including Source Edit Mode; implement a lightweight
dirty/event refresh in a safe context and measure it in phase 2. Command boundaries
still revalidate and sample current Source. Source always wins outside an active DAN
Form operation. Do not use continuous bidirectional coordinate writes or numerical
deformation in depsgraph handlers.

In phase 4 an owned controller-edit transaction supplies targets, updates Source
through the shared core path, then copies the resulting Source back to proxy. Phase 2
does not accept controller coordinate edits as deformation without that transaction.

## Topology changes

When persistent IDs referenced by controls disappear or become ambiguous, return `STALE_MAPPING`. Repair must be explicit; do not silently guess.

Fingerprint base connectivity including faces, not only counts/counters. External
topology edits can preserve counts/control IDs but change patches. On mismatch, block
the prototype until explicit validation/repair accepts topology and updates generations.
Never reassign ambiguous referenced IDs silently. New unreferenced IDs can be assigned
only during explicit validation, not as a side effect of starting deformation.

## Proxy deletion

Rebuild entirely from Source-owned definitions. No Source coordinate changes are allowed during rebuild. Preserve Source-owned hide
masks; rebuild is not Reveal All. Reveal resamples hidden geometry from current Source.
Visibility/network changes invalidate patch, constraint and distance caches; topology
validation includes mask IDs. No cached pre-hide coordinates are authoritative.

Create/remove validates effective union and prunes obsolete masks without revealing
overlaps. Cache keys include Source UUID, topology fingerprint, network revision and
proxy generation. Distances/weights rebuild from new P0; topology-only keys cannot
justify coordinate-dependent reuse. Source metadata cannot be overwritten from proxy.
