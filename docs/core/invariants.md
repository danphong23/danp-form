# Core Invariants

**Status: Normative**

1. **Source is truth.** Completed deformation exists as ordinary Source coordinates.
2. **Proxy is input.** Deleting the proxy must not revert the Source.
3. **Current shape is rest.** Every operation captures the current committed Source as `P0`.
4. **One operation, one rest state.** Preview N never becomes the rest state for preview N+1.
5. **No original-template pull.** Historical positions are not silently blended into normal deformation.
6. **No-op means no geometry change.** If all resolved control targets equal `P0`, the operation must return `P0` exactly within storage round-trip.
7. **Patches come from topology.** An open control chain divides a surface only if removing adjacency across its source edges actually disconnects faces.
8. **Enabled unselected geometry holds.** Every enabled Source control vertex outside explicit resolved node/span/loop selection stays at P0, even when omitted from a sparse proxy. At a shared vertex, a selected target wins.
9. **No write outside scope.** Vertices outside captured incident-patch scope are untouched. Preview cleanup resets prior writes within that scope before applying current output.
10. **Proportional is a patch-propagation control.** It is not silently applied again during sparse target expansion.
11. **Topology is preserved by deformation.** G/R/S deformation changes coordinates, not Source connectivity.
12. **Human and AI share the path.** They produce the same canonical control targets and call the same deformation operation.
13. **Reference fitting is downstream of target generation only.** It never gets its own mesh-writing solver.
14. **Normal cancel is exact.** With unchanged identity/topology, cancel restores Source and Proxy to operation-start state. Topology/deletion errors follow explicit recovery limits, never stale index writes.
15. **Commit is cumulative modeling.** The committed result becomes the next operation's rest shape.
16. **Hide releases, Reveal adopts.** DANP Form-hidden geometry neither cuts nor constrains; Reveal samples the current Source without restoring old positions.
17. **Partial state is geometry-backed.** Whole/partial hide masks are canonical Source IDs, not per-logical-membership state.
18. **Grouping is not geometry.** Identical effective network, targets and settings yield equivalent results regardless of names/groups.
19. **Preview can return to rest.** Returning targets to P0 or shrinking influence clears earlier preview displacement instead of leaving residual deformation.
