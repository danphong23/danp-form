# ADR-014 — Source and Controller ownership

**Status: Accepted — user agreement, 2026-09-23.**

## Context

Source custom properties are copied by Blender object duplication. A copied
Source therefore keeps `dan_form_source_uuid`; resolving its Controller by UUID
alone can select the original Source's Controller. Deformation, reset, cleanup,
or background synchronization can then cross object boundaries.

## Decision

- A DANP Form Controller is owned by exactly one Source: its direct Blender
  parent. The Source is the geometric source of truth and the Controller stays
  in the Source's local coordinate frame.
- The Source does not store a second Controller pointer. Users do not perform a
  manual link step; the existing parent relation is the ownership link.
- `dan_form_controller` remains a validation marker and `dan_form_source_uuid`
  remains a namespace for persisted IDs, controls, and agent handles. Neither
  property overrides a mismatching parent.
- A usable pair has exactly one DANP-marked mesh Controller parented directly to
  the Source, matching Source UUIDs, unique Source UUID among usable pairs, and
  single-user editable Source geometry. Ambiguous or shared geometry is rejected
  before writes.
- A mesh-only duplicate is unbound. It cannot resolve or operate the original
  Controller. Initializing it gives it a fresh UUID and fresh control mapping.
- Duplicating a complete Source/Controller pair creates an independent pair. The
  duplicate retains its local control definitions and persistent element IDs,
  receives a fresh Source UUID, and its child Controller receives the same new
  owner marker.
- Copying a Controller alone never transfers ownership. When the original
  binding is known in the current session, the new Controller is left unbound.
  If a saved file contains an ambiguous set of child Controllers, DANP Form
  fails closed and asks the user to resolve the ambiguity; it never guesses by
  object name, collection order, or UUID search order.
- Binding discovery and duplicate reconciliation are based on the resulting
  scene graph and data ownership, not on a particular Blender operator or input
  gesture.
- Cleanup, undo restoration, UI callbacks, lifecycle handlers, and agent
  lookups must use the same validated binding rules. UUID-only cleanup or lookup
  must not select a first match.

## Consequences

Parenting remains the only user-facing ownership link and keeps Source/Controller
transforms aligned. UUID remains necessary for persistent control data and API
handles, but is not an object pointer. A mesh-only duplicate can carry stale
copied properties until initialized; it stays inert while unbound. A duplicate
UUID collision already present when a file is loaded may be ambiguous because
the original creation history is unavailable; such a file is blocked from
ambiguous writes until its pair is resolved.

## Validation

Add Blender integration cases for mesh-only, full-pair, and Controller-only
duplicates; shared mesh data; same-UUID conflicts; save/load; and isolation of
Source coordinates, control data, Controller state, reset, and cleanup.
