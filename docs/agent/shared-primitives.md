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
