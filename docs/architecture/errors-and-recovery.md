# Errors and Recovery

**Status: Normative behavior; code names may be refined before implementation**

Recommended stable statuses:

```text
OK
NO_CHANGE
INVALID_INPUT
OPERATION_BUSY
OPERATION_CLOSED
NO_ACTIVE_SOURCE
SOURCE_NOT_EDITABLE
PROXY_MISSING
PROXY_CORRUPT
STALE_MAPPING
TOPOLOGY_CHANGED
CONTROL_HIDDEN
EMPTY_SELECTION
NO_MOVING_TARGET
TARGET_CONFLICT
NO_AFFECTED_PATCH
NON_FINITE_RESULT
OPERATION_STALE
UNSUPPORTED_FEATURE
```

Rules:

- mapping/proxy failure never writes Source;
- non-finite result with unchanged identity/topology restores P0/proxy and cancels; topology/deletion failures follow operation-semantics.md limits;
- missing proxy is recoverable by rebuild if Source definitions are valid;
- stale mapping requires explicit repair/recreation;
- user UI receives a short recovery-oriented message;
- agent receives a stable code plus machine-readable context.

NO_CHANGE is successful identity, not solver failure; clear prior preview writes too.
Invalid/busy/hidden/stale requests fail before new writes. An error during an existing
transaction cannot leave partial preview edits: recover/close according to operation
semantics. Report Source/element IDs and expected/actual revisions where available.

Rejecting a second/busy caller must not cancel or restore the legitimate owner's preview.
NO_MOVING_TARGET can be diagnostic context for successful NO_CHANGE, not a reason to
skip prior-preview cleanup. NO_AFFECTED_PATCH describes selected geometry with no faces.
