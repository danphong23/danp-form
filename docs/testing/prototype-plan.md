# Prototype Plan

**Status: Required validation plan before production architecture is declared stable**

## Prototype goal

Prove or falsify this narrow hypothesis:

> `current patch shape + simple topology-aware blended control displacement + one proportional attenuation` is predictable enough for DANP Form's intended modeling workflow.

Do not add an advanced preservation solver until this baseline is measured.

## Prototype scope

Include only:

- one Source Mesh;
- persistent IDs sufficient for controls;
- point/open-chain/loop controls;
- topology-derived patches;
- exact proxy first;
- node/vertex-strip/span/loop selection;
- whole/partial Hide/Reveal, enabled stationary constraints and shared-junction priority;
- G/R/S target generation;
- baseline interpolation;
- proportional Whole Patch + one finite-radius profile;
- immutable Operation Rest;
- confirm/cancel/undo;
- debug overlay for patches, targets, and displacement.

Exclude initially:

- reference images;
- automatic fitting;
- sparse simplify/refine;
- advanced solver methods;
- collision/volume terms;
- native acceleration.

## Sequence within the accepted five phases

1. Phase 1: install/Source/sidebar/controller shell and parenting tests.
2. Phase 2: persistent control IDs, exact proxy, canonical masks, external coordinate
   display sync and persistence; state fixtures before any interpolation.
3. Phase 3: topology partition fixtures and patch overlay; display toggles preserve
   geometry/network/partition.
4. Phase 4, first: pure geometry prototype, target set + patch graph → output
   coordinates. Gates B/C include constraints, G17–G21 and representative quality.
   Review the candidate before accepting interactive deformation; run the smallest
   targeted experiment if a named failure blocks quality.
5. Phase 4, next: Edit Mode G/R/S, proportional, Source preview/resync, cancel/undo,
   lifecycle Gate D and shared numeric facade. Measure full-path latency/memory.
6. Phase 5: human and external agent through MCP, equivalent-target parity Gate F
   and manual/agent-driven fit against reference images.

Reference images are excluded from the numerical prototype, but are used as workflow
evidence in phase 5. Automatic fitting remains an extension. Sparse/G7/G8/Gate E
is optional after the core roadmap and is not a prerequisite for the agent facade.
Early UI/control/patch integration does not substitute for phase-4 pure geometry
validation. Named groups must not change deformation. See the detailed
[implementation plan](../roadmap/implementation-plan.md) and [tasks](../../tasks/README.md).
