"""Runtime-only state for DANP Form.

Nothing in this module is authoritative model data.  Values are rebuilt or
cleared on load, undo/redo, unregister and topology/network changes.
"""

OVERLAY_HANDLE = None
SYNC_GUARD = False
UI_SYNC_GUARD = False
MAPPING_CACHE = {}
UI_SIGNATURES = {}
ACTIVE_CONTROL_UUIDS = {}
RETURN_MODES = {}
PROXY_SNAPSHOTS = {}
TOPOLOGY_KEYMAPS = []
CONTROL_KEYMAPS = []
NETWORK_CACHE = {}
PATCH_CACHE = {}
PATCH_OVERLAY_CACHE = {}
FACE_CACHE = {}
OVERLAY_CACHE = {}
XRAY_SHOW_IN_FRONT = {}
PICK_PREVIEW = {}
PICK_SESSION = 0
DANP_TRANSACTIONS = {}
# Live native Blender G/R/S sessions.  The controller remains the source of
# the interactive target positions while the Source preview is updated from a
# single immutable transaction rest.  This is intentionally runtime-only;
# control identity and topology stay in Source custom data.
NATIVE_TRANSFORM_SESSIONS = {}
NATIVE_UNDO_RECORDS = {}
NATIVE_UNDO_TIMER = False
NATIVE_UNDO_DIRECTION = None
TOPOLOGY_STATES = {}
MODIFIER_SIGNATURES = {}
# Current-session evidence for duplicate reconciliation.  This is deliberately
# runtime-only: a file loaded with an already ambiguous UUID/parent graph must
# fail closed because its creation history is unavailable.
BINDING_OWNERS = {}
