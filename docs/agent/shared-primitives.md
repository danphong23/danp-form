# Human and AI Shared Primitives

**Status: Normative**

AI does not receive a separate deformation solver or direct patch-writing API.

Both human and agent use the same conceptual operations:

```text
select enabled control elements
hide / reveal whole controls or Source-backed portions
translate / rotate / scale
or set explicit proxy-knot targets
set proportional settings
begin / update / commit / cancel
```

Those inputs pass through the same steps:

```text
interaction → Dense Target Set → affected patches → interpolation → Source writeback
```

That pipeline applies to deformation inputs. Hide/reveal instead updates Source masks,
recomputes the enabled network/patch caches and resamples proxy; it writes no Source
coordinates. It is a separate structural command, outside an active transform.

An agent may skip mouse simulation by providing numeric transforms/targets, but must not bypass target expansion, patch scope, proportional placement, or operation-rest semantics.
UI and agent transforms resolve through the same canonical operation input:
`MOVE`, `ROTATE` or `SCALE`, Source-local/world space, pivot, absolute
translation/rotation/scale and proportional settings. The core then resolves
selected Source IDs to absolute targets from Operation Rest and applies the same
control-owned transform field used by Controller Edit.

## Selection identity rule

The selection primitive is `dan_form.blender.selection._source_selection` and is
shared by the UI `+` operator and the agent facade. It refreshes BMesh lookup
tables but records `VID_ATTR`/`EID_ATTR` persistent IDs. BMesh vertex/edge indices
are transient diagnostics only; agents must never persist or submit them as
control membership. After topology changes, re-read the selection snapshot and
the topology fingerprint before issuing another command.
