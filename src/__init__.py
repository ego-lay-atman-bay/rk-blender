# context.area: FILE_BROWSER
bl_info = {
    "name": "RK file importer",
    "blender": (5, 1, 0),
    "category": "Import-Export",
}

import bpy

from .anim_import import ImportRKAnimData
from .rk_import import ImportRKData, RK_FH_script_import
from .turnaround_driver import RK_OT_add_turnaround_driver

class RK_PT_RK_sidebar(bpy.types.Panel):
    bl_label = "RK Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RK Tools"
 
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if layout is None:
            return
 
        col = layout.column(align=True)
        col.label(text="Rotation")
        col.operator(RK_OT_add_turnaround_driver.bl_idname, icon='DRIVER')
 
        layout.separator()
 
        col = layout.column(align=True)
        col.label(text="Camera")
        # col.prop(scene, "rk_turnaround_mode", text="Fit Mode")
        # col.prop(scene, "rk_turnaround_margin", text="Margin")
        # op = col.operator("rk.fit_turnaround_camera", icon='CAMERA_DATA')
        # op.mode = scene.rk_turnaround_mode
        # op.margin = scene.rk_turnaround_margin


# Only needed if you want to add into a dynamic menu.
def menu_func_import(self, context: bpy.types.Context):
    self.layout.operator(ImportRKData.bl_idname, text="Import RK File")
    self.layout.operator(ImportRKAnimData.bl_idname, text="Import RK .anim File")


classes = [
    ImportRKData,
    RK_FH_script_import,
    ImportRKAnimData,
    RK_OT_add_turnaround_driver,
    RK_PT_RK_sidebar,
]


# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access).
def register():
    for c in classes:
        bpy.utils.register_class(c)
    
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
