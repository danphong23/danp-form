"""Blender class, property, handler and keymap lifecycle."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty


def _remove_handler_instances(handler_list, callback) -> None:
    """Remove stale copies left by a module reload before registering again."""
    key = (getattr(callback, "__module__", None), getattr(callback, "__name__", None))
    for item in list(handler_list):
        if item is callback or (
            getattr(item, "__module__", None), getattr(item, "__name__", None)
        ) == key:
            handler_list.remove(item)


def _register_impl(api, registered_classes) -> None:
    for cls in api.CLASSES:
        bpy.utils.register_class(cls)
        registered_classes.append(cls)
    bpy.types.Scene.dan_form_source = PointerProperty(
        name="DANP Form Source", type=bpy.types.Object,
        poll=lambda _self, obj: obj.type == "MESH",
    )
    bpy.types.Scene.dan_form_controller = PointerProperty(name="DANP Form Controller", type=bpy.types.Object)
    bpy.types.Scene.dan_form_status = StringProperty(name="DANP Form Status", default="Select a mesh Source")
    bpy.types.Scene.dan_form_selected_control = StringProperty(name="Selected Control", default="")
    bpy.types.Scene.dan_form_control_items = CollectionProperty(type=api.DANFORM_PG_ControlItem)
    bpy.types.Scene.dan_form_control_index = IntProperty(
        name="Active Control", default=0, min=0, update=api._ui_control_index_update
    )
    bpy.types.Scene.dan_form_ui_source_uuid = StringProperty(name="UI Source UUID", default="")
    bpy.types.Scene.dan_form_overlay_enabled = BoolProperty(name="Control Overlay", default=True)
    bpy.types.Scene.dan_form_patches_enabled = BoolProperty(name="Show Patches", default=False)
    bpy.types.Scene.dan_form_overlay_hidden = BoolProperty(name="Show Hidden Controls", default=False)
    bpy.types.Scene.dan_form_overlay_xray = BoolProperty(name="X-Ray", default=False, update=api._update_overlay_display)
    bpy.types.Scene.dan_form_overlay_width = FloatProperty(name="Line Width", default=3.0, min=1.0, max=8.0)
    bpy.types.Scene.dan_form_proportional_profile = EnumProperty(
        name="Profile",
        items=(("LINEAR", "Linear", ""), ("SMOOTH", "Smooth", ""), ("UNIFORM", "Uniform", "")),
        default="LINEAR",
    )
    bpy.types.Scene.dan_form_proportional_radius = FloatProperty(name="Radius", default=0.0, min=0.0)
    _remove_handler_instances(bpy.app.handlers.depsgraph_update_post, api._depsgraph_update_post)
    bpy.app.handlers.depsgraph_update_post.append(api._depsgraph_update_post)
    _remove_handler_instances(bpy.app.handlers.undo_post, api._undo_post)
    _remove_handler_instances(bpy.app.handlers.redo_post, api._redo_post)
    _remove_handler_instances(bpy.app.handlers.load_post, api._load_post)
    _remove_handler_instances(bpy.app.handlers.undo_post, api._refresh_runtime)
    _remove_handler_instances(bpy.app.handlers.redo_post, api._refresh_runtime)
    _remove_handler_instances(bpy.app.handlers.load_post, api._refresh_runtime)
    bpy.app.handlers.undo_post.append(api._undo_post)
    bpy.app.handlers.redo_post.append(api._redo_post)
    bpy.app.handlers.load_post.append(api._load_post)
    # Extension registration can run under Blender's restricted context,
    # where no active scene or window exists yet.  Runtime caches and display
    # state are refreshed by the persistent load/undo handlers once a real
    # context is available; registration itself must remain context-free.
    try:
        api._refresh_runtime()
        scene = getattr(bpy.context, "scene", None)
        if scene is not None:
            api._update_overlay_display(scene)
    except (AttributeError, RuntimeError):
        pass
    api._register_overlay()
    api._register_topology_keymaps()
    # G/R/S must remain Blender-native in Controller Edit.  The lifecycle
    # depsgraph observer owns synchronization after the native transform;
    # registering addon macros here changes normal Edit Mode semantics.
    api._register_control_keymaps()


def register(api) -> None:
    """Register the extension atomically when Blender fails mid-sequence."""
    property_names = (
        "dan_form_source", "dan_form_controller", "dan_form_status",
        "dan_form_selected_control", "dan_form_control_items",
        "dan_form_control_index", "dan_form_ui_source_uuid",
        "dan_form_overlay_enabled", "dan_form_patches_enabled",
        "dan_form_overlay_hidden", "dan_form_overlay_xray",
        "dan_form_overlay_width", "dan_form_proportional_profile",
        "dan_form_proportional_radius",
    )
    existing_properties = {
        name for name in property_names if hasattr(bpy.types.Scene, name)
    }
    registered_classes = []
    try:
        _register_impl(api, registered_classes)
    except Exception:
        # Undo every partial side effect, retaining properties/classes that
        # existed before this registration attempt.
        for callback, handler_list in (
            (api._depsgraph_update_post, bpy.app.handlers.depsgraph_update_post),
            (api._undo_post, bpy.app.handlers.undo_post),
            (api._redo_post, bpy.app.handlers.redo_post),
            (api._load_post, bpy.app.handlers.load_post),
        ):
            _remove_handler_instances(handler_list, callback)
        for cleanup in (api._unregister_control_keymaps,
                        api._unregister_topology_keymaps,
                        api._unregister_overlay):
            try:
                cleanup()
            except (AttributeError, RuntimeError, TypeError):
                pass
        for name in property_names:
            if name not in existing_properties and hasattr(bpy.types.Scene, name):
                delattr(bpy.types.Scene, name)
        for cls in reversed(registered_classes):
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError:
                pass
        raise


def unregister(api) -> None:
    # Timer callbacks retain references to Blender objects and transaction
    # state. Stop them before teardown clears the state they may inspect.
    api._cancel_runtime_timers()
    api._unregister_control_keymaps()
    api._unregister_topology_keymaps()
    api._unregister_overlay()
    for controller in bpy.data.objects:
        previous = api._XRAY_SHOW_IN_FRONT.pop(controller.as_pointer(), None)
        if previous is not None:
            controller.show_in_front = previous
    api._XRAY_SHOW_IN_FRONT.clear()
    _remove_handler_instances(bpy.app.handlers.depsgraph_update_post, api._depsgraph_update_post)
    _remove_handler_instances(bpy.app.handlers.undo_post, api._undo_post)
    _remove_handler_instances(bpy.app.handlers.redo_post, api._redo_post)
    _remove_handler_instances(bpy.app.handlers.load_post, api._load_post)
    _remove_handler_instances(bpy.app.handlers.undo_post, api._refresh_runtime)
    _remove_handler_instances(bpy.app.handlers.redo_post, api._refresh_runtime)
    _remove_handler_instances(bpy.app.handlers.load_post, api._refresh_runtime)
    for cache in (
        api._MAPPING_CACHE, api._UI_SIGNATURES, api._ACTIVE_CONTROL_UUIDS, api._RETURN_MODES,
        api._PROXY_SNAPSHOTS, api._NETWORK_CACHE, api._PATCH_CACHE, api._PATCH_OVERLAY_CACHE,
        api._FACE_CACHE, api._OVERLAY_CACHE, api._runtime.SHAPE_EVAL_SIGNATURES,
    ):
        cache.clear()
    # Disabling/reloading during a preview must restore the captured Source
    # pose while the owning objects and transaction are still resolvable.
    for source_ptr, tx in list(api._DANP_TRANSACTIONS.items()):
        source = next((obj for obj in bpy.data.objects
                       if obj.as_pointer() == source_ptr), None)
        controller = next((obj for obj in bpy.data.objects
                           if obj.as_pointer() == tx.get("controller")), None)
        try:
            if source is not None and controller is not None and not tx.get("closed"):
                api._deform_cancel(source, controller)
        except (AttributeError, ReferenceError, RuntimeError, ValueError):
            pass
        finally:
            if api._DANP_TRANSACTIONS.get(source_ptr) is tx:
                api._DANP_TRANSACTIONS.pop(source_ptr, None)
    api._NATIVE_TRANSFORM_SESSIONS.clear()
    api._DANP_TRANSACTIONS.clear()
    api._NATIVE_UNDO_RECORDS.clear()
    api._runtime.TOPOLOGY_STATES.clear()
    api._runtime.SHAPE_PREVIEW_STATES.clear()
    api._runtime.CONTROLLER_EDIT_ACTIVE.clear()
    api._runtime.MODIFIER_SIGNATURES.clear()
    api._runtime.BINDING_OWNERS.clear()
    api._runtime.NATIVE_UNDO_TIMER = False
    api._runtime.NATIVE_TRANSFORM_TIMERS.clear()
    api._runtime.NATIVE_UNDO_TIMER_CALLBACK = None
    api._runtime.NATIVE_UNDO_DIRECTION = None
    for prop in (
        "dan_form_overlay_width", "dan_form_overlay_xray", "dan_form_overlay_hidden",
        "dan_form_overlay_enabled", "dan_form_patches_enabled",
        "dan_form_proportional_profile", "dan_form_proportional_radius", "dan_form_selected_control",
        "dan_form_ui_source_uuid", "dan_form_control_index", "dan_form_control_items",
        "dan_form_status", "dan_form_controller", "dan_form_source",
    ):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for cls in reversed(api.CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
