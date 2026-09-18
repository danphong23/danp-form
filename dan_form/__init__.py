"""DAN Form Phase 1: extension shell and Source/controller binding."""

from __future__ import annotations

import uuid

import bpy
from bpy.props import PointerProperty, StringProperty
from mathutils import Matrix


ADDON_ID = "dan_form"
SCHEMA_VERSION = "1"
SOURCE_UUID_KEY = "dan_form_source_uuid"
CONTROLLER_KEY = "dan_form_controller"
SCHEMA_KEY = "dan_form_schema_version"

bl_info = {
    "name": "DAN Form",
    "author": "DAN Form",
    "version": (0, 1, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > DAN Form",
    "category": "Mesh",
    "description": "Source-backed controller shell for template mesh editing",
}


def _is_valid_source(obj: bpy.types.Object | None) -> bool:
    return (
        obj is not None
        and obj.type == "MESH"
        and obj.library is None
        and obj.data is not None
        and obj.data.users == 1
    )


def _source_uuid(source: bpy.types.Object) -> str:
    value = source.get(SOURCE_UUID_KEY)
    if not isinstance(value, str) or not value:
        value = uuid.uuid4().hex
        source[SOURCE_UUID_KEY] = value
        source[SCHEMA_KEY] = SCHEMA_VERSION
    return value


def _find_controller(source: bpy.types.Object) -> bpy.types.Object | None:
    source_uuid = source.get(SOURCE_UUID_KEY)
    if not source_uuid:
        return None
    for obj in bpy.data.objects:
        if obj.get(CONTROLLER_KEY) == source_uuid:
            return obj
    return None


def _controller_collection(source: bpy.types.Object, scene: bpy.types.Scene) -> bpy.types.Collection:
    if source.users_collection:
        return source.users_collection[0]
    return scene.collection


def _select_only(context: bpy.types.Context, obj: bpy.types.Object) -> None:
    for candidate in context.view_layer.objects:
        candidate.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class DANFORM_PG_Scene(bpy.types.PropertyGroup):
    pass


class DANFORM_OT_initialize(bpy.types.Operator):
    bl_idname = "dan_form.initialize"
    bl_label = "Initialize DAN Form"
    bl_description = "Bind the selected mesh as a DAN Form Source and create its controller"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source = context.scene.dan_form_source
        return source is not None and source.type == "MESH"

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        source = scene.dan_form_source
        if not _is_valid_source(source):
            self.report(
                {"ERROR"},
                "Source must be an editable mesh with single-user mesh data",
            )
            return {"CANCELLED"}

        source_uuid = _source_uuid(source)
        controller = _find_controller(source)
        if controller is not None:
            scene.dan_form_controller = controller
            scene.dan_form_status = f"Ready: {source.name} / {controller.name}"
            _select_only(context, controller)
            self.report({"INFO"}, "DAN Form controller already exists")
            return {"FINISHED"}

        mesh = bpy.data.meshes.new(f"DANFORM_CTRL_{source.name}")
        mesh.from_pydata([], [], [])
        mesh.update()
        controller = bpy.data.objects.new(f"DANFORM_CTRL_{source.name}", mesh)
        _controller_collection(source, scene).objects.link(controller)

        controller.parent = source
        controller.matrix_parent_inverse = Matrix.Identity(4)
        # The proxy mesh uses Source-local coordinates. Keep the child basis at
        # identity so Source object transforms are inherited exactly once.
        controller.matrix_basis = Matrix.Identity(4)
        controller[CONTROLLER_KEY] = source_uuid
        controller[SCHEMA_KEY] = SCHEMA_VERSION
        controller["dan_form_source_name"] = source.name
        controller.display_type = "WIRE"
        controller.hide_render = True

        source[SCHEMA_KEY] = SCHEMA_VERSION
        source["dan_form_controller_name"] = controller.name
        scene.dan_form_controller = controller
        scene.dan_form_status = f"Ready: {source.name} / {controller.name}"
        _select_only(context, controller)
        self.report({"INFO"}, f"Created {controller.name}")
        return {"FINISHED"}


class DANFORM_OT_remove_controller(bpy.types.Operator):
    bl_idname = "dan_form.remove_controller"
    bl_label = "Remove Controller"
    bl_description = "Remove only the DAN Form controller object; keep the Source mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene.dan_form_controller is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        controller = scene.dan_form_controller
        source = scene.dan_form_source
        if controller is None or controller.name not in bpy.data.objects:
            scene.dan_form_controller = None
            scene.dan_form_status = "No controller"
            return {"CANCELLED"}
        bpy.data.objects.remove(controller, do_unlink=True)
        scene.dan_form_controller = None
        if source is not None:
            source.pop("dan_form_controller_name", None)
            scene.dan_form_status = f"Source ready: {source.name}"
        else:
            scene.dan_form_status = "No controller"
        self.report({"INFO"}, "Controller removed; Source preserved")
        return {"FINISHED"}


class DANFORM_PT_sidebar(bpy.types.Panel):
    bl_label = "DAN Form"
    bl_idname = "DANFORM_PT_sidebar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAN Form"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        scene = context.scene
        layout.prop(scene, "dan_form_source", text="Source")
        row = layout.row()
        row.operator(DANFORM_OT_initialize.bl_idname, icon="OUTLINER_OB_MESH")
        row = layout.row()
        row.enabled = scene.dan_form_controller is not None
        row.operator(DANFORM_OT_remove_controller.bl_idname, icon="TRASH")
        layout.separator()
        layout.label(text=scene.dan_form_status or "Select a mesh Source")
        if scene.dan_form_controller is not None:
            layout.label(text=f"Controller: {scene.dan_form_controller.name}")
            layout.label(text="Phase 1: no controls yet")


CLASSES = (
    DANFORM_PG_Scene,
    DANFORM_OT_initialize,
    DANFORM_OT_remove_controller,
    DANFORM_PT_sidebar,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dan_form_source = PointerProperty(
        name="DAN Form Source",
        type=bpy.types.Object,
        poll=lambda _self, obj: obj.type == "MESH",
    )
    bpy.types.Scene.dan_form_controller = PointerProperty(
        name="DAN Form Controller",
        type=bpy.types.Object,
    )
    bpy.types.Scene.dan_form_status = StringProperty(name="DAN Form Status", default="Select a mesh Source")


def unregister() -> None:
    for prop in ("dan_form_status", "dan_form_controller", "dan_form_source"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
