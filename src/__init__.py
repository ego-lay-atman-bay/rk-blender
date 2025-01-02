# context.area: FILE_BROWSER
bl_info = {
    "name": "RK file importer",
    "blender": (4, 2, 0),
    "category": "Import-Export",
}

import bpy

from .anim_import import ImportRKAnimData
from .rk_import import ImportRKData


# Only needed if you want to add into a dynamic menu.
def menu_func_import(self, context):
    self.layout.operator(ImportRKData.bl_idname, text="Import RK File")
    self.layout.operator(ImportRKAnimData.bl_idname, text="Import RK .anim File")


# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access).
def register():
    bpy.utils.register_class(ImportRKData)
    bpy.utils.register_class(ImportRKAnimData)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportRKData)
    bpy.utils.unregister_class(ImportRKAnimData)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
