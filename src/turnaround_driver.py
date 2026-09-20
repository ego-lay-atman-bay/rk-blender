import bpy

class RK_OT_add_turnaround_driver(bpy.types.Operator):
    """Add a Z-rotation driver to the active armature for a 360 turnaround"""
    bl_idname = "rk.add_turnaround_driver"
    bl_label = "Add Turnaround Driver"
    bl_options = {'REGISTER', 'UNDO'}
 
    total_frames: bpy.props.IntProperty(
        name="Total Frames",
        default=100,
        min=1,
        description="Frame count for one full 360 degree rotation",
    ) # type: ignore
 
    @classmethod
    def poll(cls, context):
        return context.active_object is not None
 
    def execute(self, context):
        obj = context.active_object

        if obj is None:
            return {'CANCELLED'}

        fcurve = obj.driver_add('rotation_euler', 2)
        if not isinstance(fcurve, list):
            driver = fcurve.driver
            driver.type = 'SCRIPTED'
            driver.expression = 'frame*(-radians(360)/total_frames)'
            
            for existing in list(driver.variables):
                driver.variables.remove(existing)
            
            var_total_frames = driver.variables.new()
            var_total_frames.name = 'total_frames'
            var_total_frames.type = 'SINGLE_PROP'
            var_total_frames.targets[0].id_type = 'SCENE'
            var_total_frames.targets[0].id = bpy.context.scene
            var_total_frames.targets[0].data_path = "frame_end"

 
        # --- your existing driver-setup logic goes here ---
        # e.g. something along the lines of:
        #
        # fcurve = armature.driver_add("rotation_euler", 2)  # Z rotation
        # driver = fcurve.driver
        # driver.expression = f"frame*(-radians(360)/{self.total_frames})"
        # driver.type = 'SCRIPTED'
        #
        # (kept out here since you already have this part working)
 
        self.report({'INFO'}, f"Turnaround driver added ({self.total_frames} frames)")
        return {'FINISHED'}
