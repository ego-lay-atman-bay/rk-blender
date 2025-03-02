"""
Currently it expects you to load `pony_type01.anim`, because I currently
have it hardcoded to load a specific animation from that file.
"""

import math

import bmesh
import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from luna_kit.model import anim
from luna_kit.model.anim import Anim
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
        bone_indexes = [bone for bone in bones]
        
        rk_anim = Anim(filename)

        animation_name = "gen_trot"
        
        fps = rk_anim.animations[animation_name].fps
        frame_step = context.scene.render.fps / fps

        current_frame = 0
        
        def to_relative_rotation(bone: bpy.types.PoseBone, rotation: Quaternion, frame: list[anim.BoneTransformation]) -> Euler:
            parent_rotation = (0,0,0,0)
            
            if bone.parent:
                parent_index = bone_indexes.index(bone.parent)
                parent_rotation = to_relative_rotation(bone.parent, frame[parent_index].quaternion, frame)
            
            return (
                rotation[0] - parent_rotation[0],
                rotation[1] - parent_rotation[1],
                rotation[2] - parent_rotation[2],
                rotation[3] - parent_rotation[3],
            )
        
        def to_relative_location(bone: bpy.types.PoseBone, location: Vector):
            parent_location = Vector((0,0,0))
            if bone.parent:
                parent_location = to_relative_location(bone.parent, bone.parent.location)
            
            return location + parent_location
        
        
        def get_rotation(bone_transformation: anim.BoneTransformation):
            return Quaternion((
                (bone_transformation.rotation[0]-90)/256,
                bone_transformation.rotation[1]/256,
                bone_transformation.rotation[2]/256,
                (bone_transformation.rotation[3]+90)/256,
            ))
        
        for frame_index in range(rk_anim.animations[animation_name].start, rk_anim.animations[animation_name].end):
            frame = rk_anim.frames[frame_index]
            print('adding frame', current_frame)
            for bone_index, bone_transformation in enumerate(frame):
                bone = bones[bone_index]

                # rotation = get_rotation(bone_transformation)
                location = Vector((
                    -bone_transformation.position.z,
                    -bone_transformation.position.x,
                    -bone_transformation.position.y,
                ))
                
                relative_rotation = bone_transformation.quaternion

                # relative_rotation = to_relative_rotation(bone, bone_transformation.quaternion, frame)
                
                rotation = Quaternion((
                    relative_rotation.w,
                    relative_rotation.x,
                    relative_rotation.y,
                    relative_rotation.z,
                ))
                # rotation = rotation.to_euler()
                # rotation.z, rotation.x, rotation.y = rotation.x, rotation.y, rotation.z
                # rotation = rotation.to_quaternion()
                    # location = to_relative_location(bone, location)
                
                # rotation.rotate(Euler((0, math.radians(90), math.radians(90))))

                # rotation.negate()
                # as_euler = rotation.to_euler('XYZ')
                # as_euler.z, as_euler.y = as_euler.y, as_euler.z
                # rotation = as_euler.to_quaternion()
                # rotation.invert()
                
                # as_euler = rotation.to_euler('XYZ')
                # as_euler.y, as_euler.z = as_euler.z, as_euler.y
                # as_euler.rotate_axis('Z', math.radians(90))
                # rotation = as_euler.to_quaternion()
                
                # rotation.y, rotation.z = rotation.z, rotation.y
                # rotation.x, rotation.w = rotation.w, rotation.x
                # rotation.rotation_difference

                last = bone.matrix
                new = Matrix.LocRotScale(location, rotation, Vector((1,1,1)))
                
                final = last @ new
                
                bone.matrix = final
                # bone.rotation_quaternion = rotation
                # bone.location = location
                # bone.scale = Vector((bone_transformation.scale/256,) * 3)
                bone.keyframe_insert('rotation_quaternion', frame = current_frame, group = animation_name)
                bone.keyframe_insert('location', frame = current_frame, group = animation_name)
                # bone.keyframe_insert('scale', frame = frame_index * fps, group = animation_name)

            current_frame += frame_step
    
        context.scene.frame_end = math.ceil(current_frame)
