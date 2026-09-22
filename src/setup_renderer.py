import bpy

class RK_OT_setup_renderer(bpy.types.Operator):
    bl_idname = "rk.setup_renderer"
    bl_label = "Setup mlp renderer"
    bl_description = 'Set render settings for mlp renderer'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene: bpy.types.Scene = context.scene

        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0

        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.03
        scene.cycles.preview_adaptive_threshold = 0.03
        scene.cycles.samples = 4096
        scene.cycles.adaptive_min_samples = 0
        scene.cycles.time_limit = 0
        scene.cycles.use_denoising = False

        return {'FINISHED'}
