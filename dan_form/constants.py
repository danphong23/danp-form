"""Persistent DANP Form identifiers and Blender property names.

This module intentionally contains no Blender API calls.  Keeping the names in
one place prevents storage compatibility from depending on the UI or operator
modules.
"""

ADDON_ID = "dan_form"
SCHEMA_VERSION = "3"
SOURCE_UUID_KEY = "dan_form_source_uuid"
CONTROLLER_KEY = "dan_form_controller"
UNBOUND_COPY_KEY = "dan_form_unbound_copy"
SCHEMA_KEY = "dan_form_schema_version"
VID_ATTR = "dan_form_vid"
EID_ATTR = "dan_form_eid"
PROXY_VID_ATTR = "dan_form_proxy_vid"
PROXY_EID_ATTR = "dan_form_proxy_eid"
CONTROLS_KEY = "dan_form_controls"
HIDDEN_VIDS_KEY = "dan_form_hidden_vertex_ids"
HIDDEN_EIDS_KEY = "dan_form_hidden_edge_ids"
NEXT_VID_KEY = "dan_form_next_vid"
NEXT_EID_KEY = "dan_form_next_eid"
TOPOLOGY_KEY = "dan_form_topology_fingerprint"
ORIGINAL_POSITIONS_KEY = "dan_form_original_positions"
ORIGINAL_TOPOLOGY_KEY = "dan_form_original_topology"
ORIGINAL_SHAPE_KEY_NAME_KEY = "dan_form_original_shape_key_name"
ORIGINAL_TARGET_KIND_KEY = "dan_form_original_target_kind"
BASE_MESH_TARGET = "__DANP_BASE_MESH_TARGET__"
NETWORK_REVISION_KEY = "dan_form_control_network_revision"
PROXY_GENERATION_KEY = "dan_form_proxy_generation"
UI_SOURCE_UUID_KEY = "dan_form_ui_source_uuid"
FACE_SOURCE_UUID_KEY = "dan_form_face_source_uuid"
