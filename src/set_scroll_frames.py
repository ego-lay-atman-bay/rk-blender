import bpy
import math

class RK_OT_set_uv_scroll_frames(bpy.types.Operator):
    bl_idname = "rk.set_uv_scroll_frames"
    bl_label = "Fit scrolling textures"
    bl_description = 'Set end frames to perfectly loop scrolling textures'
    bl_options = {'REGISTER', 'UNDO'}
 
    cycles: bpy.props.FloatProperty(
        name = "Total cycles",
        default = 2.0,
        min = 0.1,
        description = "Total number of full cycles",
    )
 
    @classmethod
    def poll(cls, context):
        if context.active_object is None:
            return False
        context.selectable_objects
        
        materials = [
            material
            for child in [context.active_object, *context.active_object.children_recursive]
            for material in getattr(child.data, 'materials', [])
            if 'uv_scroll_speed' in material
        ]

        return len(materials)
 
    def execute(self, context):
        obj = context.active_object

        if obj is None:
            self.report({'ERROR'}, "No objects")
            return {'CANCELLED'}
        
        materials = [
            material
            for child in [context.active_object, *context.active_object.children_recursive]
            for material in getattr(child.data, 'materials', [])
            if 'uv_scroll_speed' in material
        ]
        if len(materials) == 0:
            self.report({'ERROR'}, "No objects with scrolling texture")
            return {'CANCELED'}
        
        scene: bpy.types.Scene = context.scene
        fps = scene.render.fps / scene.render.fps_base

        all_total_frames: list[float] = []

        for material in materials:
            if 'uv_scroll_speed' not in material:
                continue
            
            y_speed: float = material['uv_scroll_speed']
            frames = round(abs(fps/(0.4 * y_speed)))
            all_total_frames.append(frames)
        
        if not len(all_total_frames):
            return {'CANCELED'}
        
        total_frames = round(math.lcm(*all_total_frames) * self.cycles)

        scene.frame_end = total_frames
        scene.frame_preview_end = total_frames
 
        self.report({'INFO'}, f"Set frames to {total_frames} frames")
        return {'FINISHED'}
