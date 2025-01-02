import math

import bmesh
import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from luna_kit import rk
from luna_kit.anim import Anim
from mathutils import Euler, Matrix, Quaternion, Vector

from .utils import add_to_vertex_group, get_armatures, pil_to_image


class ImportRKAnimData(Operator, ImportHelper):
    """Import RK animation files"""
    bl_idname = "import_scene.rk_anim_data"
    bl_label = "Import RK Anim Format"
    filename_ext = ".anim"

    # File browser properties
    # filepath: bpy.types
    filepath: StringProperty(subtype="FILE_PATH") # type: ignore

    filter_glob: StringProperty(
        default="*.anim",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    ) # type: ignore

    def execute(self, context: bpy.types.Context):
        # This is where the file reading logic will go
        self.report({'INFO'}, f"Importing {self.filepath}")
        if context.object.type != 'ARMATURE':
            pass
        self.import_anim_file(self.filepath, context)
        return {'FINISHED'}

    def import_anim_file(self, filename: str, context: bpy.types.Context):
        if context.object is None or context.object.type != 'ARMATURE':
            self.report({'INFO', f'No armature selected'})
            return
        
        # rig = context.armature
        bones = context.object.pose.bones
        
        rk_anim = Anim(filename)

        fps = 15
        
        animation_name = "gen_trot"

        current_frame = 0
        
        def to_relative_rotation(bone: bpy.types.PoseBone, rotation: Quaternion):
            parent_rotation = Quaternion((0,0,0,0))
            if bone.parent:
                parent_rotation = to_relative_rotation(bone.parent, bone.parent.rotation_quaternion)
            
            return rotation - parent_rotation
        
        def to_relative_location(bone: bpy.types.PoseBone, location: Vector):
            parent_location = Vector((0,0,0))
            if bone.parent:
                parent_location = to_relative_location(bone.parent, bone.parent.location)
            
            return location + parent_location
        
        for frame_index in range(rk_anim.animations[animation_name].start, rk_anim.animations[animation_name].end):
            frame = rk_anim.frames[frame_index]
            print('adding frame', current_frame)
            for bone_index, bone_transformation in enumerate(frame):
                bone = bones[bone_index]

                rotation = Quaternion((
                    bone_transformation.rotation[0]/(2**10),
                    bone_transformation.rotation[1]/(2**10),
                    bone_transformation.rotation[2]/(2**10),
                    bone_transformation.rotation[3]/(2**10),
                ))
                location = Vector((
                     bone_transformation.position[0]/(2**8),
                    -bone_transformation.position[1]/(2**8),
                    -bone_transformation.position[2]/(2**8),
                ))
                
                rotation.rotate(Euler((0, 0, math.radians(90))))
                rotation.negate()
                rotation.x, rotation.z = rotation.z, rotation.x
                # rotation.z, rotation.w = rotation.w, rotation.z
                # rotation.rotation_difference

                

                # if bone.parent:
                #     rotation = rotation + bone.parent.rotation_quaternion
                    # location = to_relative_location(bone, location)
                
                bone.rotation_quaternion = rotation
                bone.location = location
                # bone.scale = Vector((bone_transformation.scale/256,) * 3)
                bone.keyframe_insert('rotation_quaternion', frame = current_frame, group = animation_name)
                bone.keyframe_insert('location', frame = current_frame, group = animation_name)
                # bone.keyframe_insert('scale', frame = frame_index * fps, group = animation_name)

            current_frame += fps
    
        context.scene.frame_end = current_frame
