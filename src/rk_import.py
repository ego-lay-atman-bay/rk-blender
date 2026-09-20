import math
import os
from typing import Literal

import bmesh
import bpy
import mathutils
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from luna_kit.model import rk
from luna_kit.model.rk import RKModel
from mathutils import Color, Matrix, Vector

from .utils import add_to_vertex_group, pil_to_image


class ImportRKData(Operator, ImportHelper):
    """Import RK files"""
    bl_idname = "import_scene.rk_data"
    bl_label = "Import RK Format"
    filename_ext = ".rk"

    # File browser properties
    # filepath: bpy.types
    # filepath: bpy.props.StringProperty(subtype="FILE_PATH", options={'SKIP_SAVE'}) # type: ignore
    directory: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE', 'HIDDEN'}) # type: ignore
    files: bpy.props.CollectionProperty(
        type = bpy.types.OperatorFileListElement,
        options={'SKIP_SAVE', 'HIDDEN'},
    ) # type: ignore

    shader_method: bpy.props.EnumProperty(
        items = [
            ('bsdf', 'Normal', 'Normal PrincipleBSDF shader (good for exporting textures).'),
            ('unlit', 'Unlit', 'Use unlit lighting shader (harder to export textures, but better rendering).')
        ],
        name = 'Shader method',
        default = 'unlit',
    ) # type: ignore
    
    enable_eyes: bpy.props.BoolProperty(
        name = 'Hide eyes',
        default = False,
    ) # type: ignore
    eyes_open: bpy.props.BoolProperty(
        name = 'Open eyes',
        default = False,
    ) # type: ignore
    eyes_shut: bpy.props.BoolProperty(
        name = 'Shut eyes',
        default = True,
    ) # type: ignore
    eyes_happy: bpy.props.BoolProperty(
        name = 'Happy eyes',
        default = True,
    ) # type: ignore
    eyes_frown: bpy.props.BoolProperty(
        name = 'Frown eyes',
        default = True,
    ) # type: ignore
    
    enable_costume: bpy.props.BoolProperty(
        name = 'Import costume?',
        default = False,
    ) # type: ignore
    costume_head: bpy.props.StringProperty(
        name = 'Costume head',
        default = '',
    ) # type: ignore
    costume_body: bpy.props.StringProperty(
        name = 'Costume body',
        default = '',
    ) # type: ignore
    costume_tail: bpy.props.StringProperty(
        name = 'Costume tail',
        default = '',
    ) # type: ignore
    
    texture_suffix: bpy.props.StringProperty(
        name = 'Texture suffix',
        default = '',
    ) # type: ignore

    filter_glob: bpy.props.StringProperty(
        default="*.rk",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    ) # type: ignore
    
    # @classmethod
    # def poll(cls, context):
    #     return (context.area and context.area.type == "VIEW_3D")

    def execute(self, context: bpy.types.Context):
        # This is where the file reading logic will go
        # print({'INFO'}, f"Importing {self.filepath}")
        print({'INFO'}, f"Directory {self.directory}")
        print({'INFO'}, f'files: {[file.name for file in self.files]}')
        
        if not self.directory:
            return {'CANCELLED'}
        
        for file in self.files:
            file: bpy.types.OperatorFileListElement
            
            self.import_rk_file(os.path.join(self.directory, file.name), context)
            
        # self.import_rk_file(self.filepath, context)
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.invoke_popup(context)
        # if self.filepath:
        #     return self.execute(context)
        # context.window_manager.fileselect_add(self)
        # return {'RUNNING_MODAL'}
    
    def draw(self, context) -> None:
        scene = context.scene
        layout = self.layout
        if layout is None:
            return
        
        col = layout.column(align=True)

        col.prop(self, 'shader_method')
        
        col.prop(self, 'texture_suffix')

        eyes_title, eyes_body = col.panel_prop(self, 'enable_eyes')
        eyes_title.prop(self, 'enable_eyes')

        if eyes_body is not None:
            eyes_body.enabled = self.enable_eyes

            eyes_body.prop(self, 'eyes_open')
            eyes_body.prop(self, 'eyes_shut')
            eyes_body.prop(self, 'eyes_happy')
            eyes_body.prop(self, 'eyes_frown')

        costume_title, costume_body = col.panel_prop(self, 'enable_costume')

        costume_title.prop(self, 'enable_costume')

        if costume_body is not None:
            costume_body.enabled = self.enable_costume

            costume_body.prop(self, 'costume_head')
            costume_body.prop(self, 'costume_body')
            costume_body.prop(self, 'costume_tail')

            costume_body.prop(self, 'costume')
        


    def import_rk_file(self, filename: str, context: bpy.types.Context):
        collection = context.collection

        rk_model = RKModel(filename)

        armature = bpy.data.armatures.new(rk_model.name)
        model = bpy.data.objects.new(rk_model.name, armature)

        self.report({'INFO'}, f'name: {rk_model.name}')

        # model.name = rk_model.name
        collection.objects.link(model)
        
        materials: dict[str, bpy.types.Material] = {}

        for rk_mesh in rk_model.meshes:
            if (self.enable_costume and
                'eye' not in rk_mesh.name):
                if rk_mesh.name not in [self.costume_head, self.costume_body, self.costume_tail]:
                    print(f'skipping: {rk_mesh.name}')
                    continue
                
            
            self.report({'INFO'}, f'loading mesh: {rk_mesh.name}')
            mesh = bpy.data.meshes.new(rk_mesh.name)
            obj = bpy.data.objects.new(mesh.name, mesh)
            obj.parent = model
            modifier = obj.modifiers.new('Armature', 'ARMATURE')
            modifier.object = model
            collection.objects.link(obj)

            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode = 'EDIT')
            bm = bmesh.from_edit_mesh(obj.data)

            print(f'shader method: {self.shader_method}')
            
            if rk_mesh.material not in materials:
                material = self.create_material(
                    rk_model.materials[rk_mesh.material_index],
                    self.shader_method,
                )
                
                materials[rk_mesh.material] = material
                obj.data.materials.append(material)

            self.mesh_add_faces(
                obj,
                bm,
                rk_mesh,
                rk_model,
            )

            # mesh.update()
            bmesh.update_edit_mesh(obj.data)
            bpy.ops.object.mode_set(mode = 'OBJECT')

            if self.enable_eyes:
                if rk_mesh.name.endswith('eyes_open'):
                    obj.hide_set(self.eyes_open)
                    obj.hide_render = self.eyes_open

                if rk_mesh.name.endswith('eyes_shut'):
                    obj.hide_set(self.eyes_shut)
                    obj.hide_render = self.eyes_shut

                if rk_mesh.name.endswith('eyes_frown'):
                    obj.hide_set(self.eyes_frown)
                    obj.hide_render = self.eyes_frown

                if rk_mesh.name.endswith('eyes_happy'):
                    obj.hide_set(self.eyes_happy)
                    obj.hide_render = self.eyes_happy


            # observing the game, you can see that they're not smooth shaded
            # mesh.shade_smooth()


        context.view_layer.objects.active = model
        bpy.ops.object.mode_set(mode = 'EDIT')
        bones: dict[int, tuple[bpy.types.EditBone, rk.Bone]] = {}

        for rk_bone in rk_model.bones:
            matrix = Matrix(rk_bone.matrix_4x4)
            bone = armature.edit_bones.new(rk_bone.name)
            
            translation, rotation, scale = matrix.decompose()
            
            rotation = mathutils.Quaternion((
                rotation.w,
                rotation.x,
                rotation.y,
                rotation.z,
            ))
            rotation = rotation.to_euler()
            rotation = mathutils.Euler((
                -rotation.z,
                -rotation.x,
                -rotation.y,
            ))
            # rotation.z, rotation.x, rotation.y = rotation.x, rotation.y, rotation.z
            rotation = rotation.to_quaternion()
            # rotation.rotate(mathutils.Euler((0, math.pi, 0)))
# 
            translation = mathutils.Vector((
                -translation.z,
                -translation.x,
                -translation.y,
            ))
            
            matrix = Matrix.LocRotScale(translation, rotation, scale)
            
            bone.head = matrix @ Vector((0, 0, 0))
            bone.tail = matrix @ Vector((10, 0, 0))
            # bone.align_roll(matrix @ Vector((10, 0, 0)) - bone.head)
            # bone.length = 2

            for child in model.children:
                if child.type == 'MESH':
                    child.vertex_groups.new(name = rk_bone.name)

            bones[rk_bone.index] = bone, rk_bone
            bone.roll

        for bone, rk_bone in bones.values():
            if rk_bone.parentIndex > -1:
                bone.parent = bones[rk_bone.parentIndex][0]

        bpy.ops.object.mode_set(mode = 'OBJECT')

        for child in model.children:
            if child.type == 'MESH':
                for vert, rk_vert in zip(child.data.vertices, rk_model.verts):
                    rk_vert = rk_model.verts[vert.index]
                    if len(rk_model.bones):
                        for bone_info in rk_vert.bones:
                            add_to_vertex_group(
                                child,
                                rk_model.bones[bone_info.bone],
                                bone_info.weight,
                                vert,
                            )
                        # add_to_vertex_group(
                        #     child,
                        #     rk_model.bones[rk_vert.bones[1].bone],
                        #     rk_vert.bones[1].weight,
                        #     vert,
                        # )

        # model.rotation_euler[0] = math.radians(-90)
        model.scale = Vector([0.1, 0.1, 0.1])

        model.select_set(True)

    def create_material(
        self,
        rk_material: rk.Material,
        method: Literal['bsdf', 'unlit'],
    ):
        material = bpy.data.materials.get(rk_material.name)
        if material is None:
            material = bpy.data.materials.new(rk_material.name)
        material.use_nodes = True
        
        if material.node_tree:
            print('creating material nodes')
            material.node_tree.nodes.clear()
            material.node_tree.links.clear()

            nodes = material.node_tree.nodes
            links = material.node_tree.links

            output: bpy.types.ShaderNodeOutputMaterial = nodes.new(type = 'ShaderNodeOutputMaterial')

            texture_node: bpy.types.ShaderNodeTexImage = nodes.new(type = 'ShaderNodeTexImage')
            image = rk_material.properties.image(self.texture_suffix)
            if image is not None:
                texture_node.image = pil_to_image(
                    image,
                    rk_material.name,
                    # flip_vertical = True,
                    alpha = True,
                )
            
            
            if rk_material.properties.Shader == 'rkponyhair0':
                uv_map_node: bpy.types.ShaderNodeUVMap = nodes.new("ShaderNodeUVMap")
                uv_map_node.location = Vector((-940.0, 315.0))

                mapping_node: bpy.types.ShaderNodeMapping = nodes.new("ShaderNodeMapping")
                mapping_node.location = Vector((-695.0, 360.0))

                links.new(uv_map_node.outputs[0], mapping_node.inputs[0])
                links.new(mapping_node.outputs[0], texture_node.inputs[0])

                # Custom property on the material so the user can tweak scroll speed
                # in the UI (shows up under Material Properties > Custom Properties).
                # Only seed it the first time - don't stomp a value the user already
                # tweaked if they re-import over an existing material.
                speed_prop = "uv_scroll_speed"
                if speed_prop not in material:
                    material[speed_prop] = rk_material.properties.UserVector0_0
                    material.id_properties_ui(speed_prop).update(
                        description = "UV Y scroll speed multiplier",
                        soft_min = -5.0,
                        soft_max = 5.0,
                    )

                # Driver on the Mapping node's Location Y.
                # inputs[1] is the Location vector socket; array index 1 within
                # it is the Y component.
                fcurve = mapping_node.inputs[1].driver_add("default_value", 1)
                driver = fcurve.driver
                driver.type = 'SCRIPTED'
                driver.expression = "(frame / (fps / fps_base) * .4) * y_speed" # .4 is a constant multiplier

                for existing in list(driver.variables):
                    driver.variables.remove(existing)

                var_fps = driver.variables.new()
                var_fps.name = "fps"
                var_fps.type = 'SINGLE_PROP'
                var_fps.targets[0].id_type = 'SCENE'
                var_fps.targets[0].id = bpy.context.scene
                var_fps.targets[0].data_path = "render.fps"

                var_fps_base = driver.variables.new()
                var_fps_base.name = "fps_base"
                var_fps_base.type = 'SINGLE_PROP'
                var_fps_base.targets[0].id_type = 'SCENE'
                var_fps_base.targets[0].id = bpy.context.scene
                var_fps_base.targets[0].data_path = "render.fps_base"

                var_speed = driver.variables.new()
                var_speed.name = "y_speed"
                var_speed.type = 'SINGLE_PROP'
                var_speed.targets[0].id_type = 'MATERIAL'
                var_speed.targets[0].id = material
                var_speed.targets[0].data_path = f'["{speed_prop}"]'
            
            match method:
                case 'unlit':
                    output.location = Vector((490.0, 290.0))
                    texture_node.location = Vector((-440.0, 380.0))
                    
                    # light_path: bpy.types.ShaderNodeLightPath = nodes.new(type = 'ShaderNodeLightPath')
                    # light_path.location = Vector((10.0, 600.0))

                    geometry: bpy.types.ShaderNodeNewGeometry = nodes.new(type = 'ShaderNodeNewGeometry')
                    geometry.location = Vector((-400, 620))

                    bakcface_flip: bpy.types.ShaderNodeMath = nodes.new(type = 'ShaderNodeMath')
                    bakcface_flip.operation = 'SUBTRACT'
                    bakcface_flip.location = Vector((-155, 550))

                    bakcface_mask: bpy.types.ShaderNodeMath = nodes.new(type = 'ShaderNodeMath')
                    bakcface_mask.operation = 'MULTIPLY'
                    bakcface_mask.location = Vector((45, 455))


                    transparent_bsdf: bpy.types.ShaderNodeBsdfTransparent = nodes.new(type = 'ShaderNodeBsdfTransparent')
                    transparent_bsdf.location = Vector((10.0, 240.0))
                    transparent_bsdf.color = Color((255, 255, 255))
                    
                    emission: bpy.types.ShaderNodeEmission = nodes.new(type = 'ShaderNodeEmission')
                    emission.location = Vector((10.0, 126.0))
                    
                    links.new(texture_node.outputs[0], emission.inputs[0])
                    
                    mix_shader: bpy.types.ShaderNodeMixShader = nodes.new(type = 'ShaderNodeMixShader')
                    mix_shader.location = Vector((260.0, 320.0))
                    
                    # links.new(light_path.outputs[0], mix_shader.inputs[0])
                    bakcface_flip.inputs[0].default_value = 1
                    links.new(geometry.outputs[6], bakcface_flip.inputs[1])

                    links.new(bakcface_flip.outputs[0], bakcface_mask.inputs[0])
                    links.new(texture_node.outputs[1], bakcface_mask.inputs[1])

                    links.new(bakcface_mask.outputs[0], mix_shader.inputs[0])
                    links.new(transparent_bsdf.outputs[0], mix_shader.inputs[1])
                    links.new(emission.outputs[0], mix_shader.inputs[2])
                    
                    links.new(mix_shader.outputs[0], output.inputs[0])
                case 'bsdf':
                    output.location = Vector((300.0, 300.0))
                    texture_node.location = Vector((-300.0, 300.0))
                    
                    principled_bsdf: bpy.types.ShaderNodeBsdfPrincipled = nodes.new(type = 'ShaderNodeBsdfPrincipled')
                    principled_bsdf.location = Vector((0.0, 300.0))
                    principled_bsdf.inputs[2].default_value = 1

                    links.new(texture_node.outputs[0], principled_bsdf.inputs[0])
                    links.new(texture_node.outputs[1], principled_bsdf.inputs[4])
                    links.new(principled_bsdf.outputs[0], output.inputs[0])
                case _:
                    raise ValueError(f'Unknown shader method: {method}')


            if rk_material.properties.Cull:
                material.use_backface_culling = True
            if rk_material.properties.ClampMode:
                if rk_material.properties.ClampMode == 'RK_CLAMP':
                    texture_node.extension = 'EXTEND'
                elif rk_material.properties.ClampMode == 'RK_REPEAT':
                    texture_node.extension = 'REPEAT'


        return material

    def mesh_add_faces(
        self,
        obj: bpy.types.Object,
        bm: bmesh.types.BMesh,
        rk_mesh: rk.Mesh,
        rk_model: rk.RKModel,
    ):

        # add vertices and uvs before creating the new face
        def add_vert(rk_vert: rk.Vert):
            vert = bm.verts.new((
                -rk_vert.pos.z,
                -rk_vert.pos.x,
                -rk_vert.pos.y,
            ))
            return vert

        for rk_vert in rk_model.verts:
            add_vert(rk_vert)

        bm.verts.index_update()
        bm.verts.ensure_lookup_table()
        # add uvs to the new face
        uv_layer = bm.loops.layers.uv.verify()
        # bm.faces.layers.tex.verify()

        # bm.verts.ensure_lookup_table()
        for i, rk_tri in enumerate(rk_mesh.triangles):
            rk_tri_verts = (
                rk_model.verts[rk_tri.x],
                rk_model.verts[rk_tri.y],
                rk_model.verts[rk_tri.z],
            )

            try:
                face = bm.faces.new((
                    bm.verts[rk_tri.x],
                    bm.verts[rk_tri.y],
                    bm.verts[rk_tri.z],
                ))
            except ValueError:
                rk_model.verts.append(rk_model.verts[rk_tri.x])
                rk_model.verts.append(rk_model.verts[rk_tri.y])
                rk_model.verts.append(rk_model.verts[rk_tri.z])

                face = bm.faces.new((
                    add_vert(rk_model.verts[rk_tri.x]),
                    add_vert(rk_model.verts[rk_tri.y]),
                    add_vert(rk_model.verts[rk_tri.z]),
                ))
                bm.verts.index_update()
                bm.verts.ensure_lookup_table()


            for l, loop in enumerate(face.loops):
                uv = loop[uv_layer].uv
                uv[0] = rk_tri_verts[l].u
                uv[1] = rk_tri_verts[l].v


            # assign material
            try:
                material_names = [m.name for m in obj.data.materials]
                material_id = material_names.index(rk_mesh.material)
            except ValueError:
                obj.data.materials.append(bpy.data.materials[rk_mesh.material])
                material_id = len(obj.data.materials) - 1

            face.material_index = material_id

class RK_FH_script_import(bpy.types.FileHandler):
    bl_idname = "RK_FH_script_import"
    bl_label = "File handler for rk import"
    bl_import_operator = "import_scene.rk_data"
    bl_file_extensions = ".rk"

    @classmethod
    def poll_drop(cls, context):
        return (
            context.region and context.region.type == 'WINDOW' and
            context.area and context.area.type == 'VIEW_3D'
        )
