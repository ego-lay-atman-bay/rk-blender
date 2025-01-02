import math

import bmesh
import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from luna_kit import rk
from luna_kit.rk import RKFormat
from mathutils import Matrix, Vector

from .utils import add_to_vertex_group, pil_to_image


class ImportRKData(Operator, ImportHelper):
    """Import RK files"""
    bl_idname = "import_scene.rk_data"
    bl_label = "Import RK Format"
    filename_ext = ".rk"

    # File browser properties
    # filepath: bpy.types
    filepath: StringProperty(subtype="FILE_PATH") # type: ignore


    filter_glob: StringProperty(
        default="*.rk",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    ) # type: ignore

    def execute(self, context: bpy.types.Context):
        # This is where the file reading logic will go
        self.report({'INFO'}, f"Importing {self.filepath}")
        self.import_rk_file(self.filepath, context)
        return {'FINISHED'}

    def import_rk_file(self, filename: str, context: bpy.types.Context):
        collection = context.collection

        rk_model = RKFormat(filename)

        armature = bpy.data.armatures.new(rk_model.name)
        model = bpy.data.objects.new(rk_model.name, armature)

        model.name = rk_model.name
        collection.objects.link(model)

        for rk_mesh in rk_model.meshes:
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


            if rk_mesh.material not in bpy.data.materials:
                obj.data.materials.append(
                    self.create_material(
                        rk_model.materials[rk_mesh.material_index]
                    )
                )

            self.mesh_add_faces(
                obj,
                bm,
                rk_mesh,
                rk_model,
            )

            # mesh.update()
            bmesh.update_edit_mesh(obj.data)
            bpy.ops.object.mode_set(mode = 'OBJECT')

            # observing the game, you can see that they're not smooth shaded
            # mesh.shade_smooth()


        context.view_layer.objects.active = model
        bpy.ops.object.mode_set(mode = 'EDIT')
        bones: dict[int, tuple[bpy.types.EditBone, rk.Bone]] = {}

        for rk_bone in rk_model.bones:
            matrix = Matrix(rk_bone.matrix_4x4.swapaxes(1,0))
            bone = armature.edit_bones.new(rk_bone.name)
            bone.head = matrix @ Vector((0, 0, 0))
            bone.tail = matrix @ Vector((1, 0, 0))
            bone.align_roll(matrix @ Vector((0, 0, 1)) - bone.head)
            # bone.length = 2

            for child in model.children:
                if child.type == 'MESH':
                    child.vertex_groups.new(name = rk_bone.name)

            bones[rk_bone.index] = bone, rk_bone

        for bone, rk_bone in bones.values():
            if rk_bone.parentIndex > -1:
                bone.parent = bones[rk_bone.parentIndex][0]

        bpy.ops.object.mode_set(mode = 'OBJECT')

        for child in model.children:
            if child.type == 'MESH':
                for vert, rk_vert in zip(child.data.vertices, rk_model.verts):
                    rk_vert = rk_model.verts[vert.index]
                    if len(rk_model.bones):
                        add_to_vertex_group(
                            child,
                            rk_model.bones[rk_vert.bone_index1],
                            rk_vert.weight1,
                            vert,
                        )
                        add_to_vertex_group(
                            child,
                            rk_model.bones[rk_vert.bone_index2],
                            rk_vert.weight2,
                            vert,
                        )

        model.name = rk_model.name
        model.rotation_euler[0] = math.radians(-90)
        model.scale = Vector([-0.1, 0.1, 0.1])

        model.select_set(True)

    def create_material(self, rk_material: rk.Material):
        material = bpy.data.materials.get(rk_material.name)
        if material is None:
            material = bpy.data.materials.new(rk_material.name)
        material.use_nodes = True

        if material.node_tree:
            material.node_tree.nodes.clear()
            material.node_tree.links.clear()

            nodes = material.node_tree.nodes
            links = material.node_tree.links

            output: bpy.types.ShaderNodeOutputMaterial = nodes.new(type = 'ShaderNodeOutputMaterial')

            texture_node: bpy.types.ShaderNodeTexImage = nodes.new(type = 'ShaderNodeTexImage')
            texture_node.image = pil_to_image(
                rk_material.info.image,
                rk_material.name,
                # flip_vertical = True,
                alpha = True,
            )

            principled_bsdf: bpy.types.ShaderNodeBsdfPrincipled = nodes.new(type = 'ShaderNodeBsdfPrincipled')
            principled_bsdf.inputs[2].default_value = 1

            links.new(texture_node.outputs[0], principled_bsdf.inputs[0])
            links.new(texture_node.outputs[1], principled_bsdf.inputs[4])
            links.new(principled_bsdf.outputs[0], output.inputs[0])


            if rk_material.info.Cull:
                material.use_backface_culling = True
            if rk_material.info.ClampMode:
                if rk_material.info.ClampMode == 'RK_CLAMP':
                    texture_node.extension = 'EXTEND'
                elif rk_material.info.ClampMode == 'RK_REPEAT':
                    texture_node.extension = 'REPEAT'


        return material

    def mesh_add_faces(
        self,
        obj: bpy.types.Object,
        bm: bmesh.types.BMesh,
        rk_mesh: rk.Mesh,
        rk_model: rk.RKFormat,
    ):

        # add vertices and uvs before creating the new face
        def add_vert(rk_vert: rk.Vert):
            vert = bm.verts.new((rk_vert.x, rk_vert.y, rk_vert.z))
            return vert

        for rk_vert in rk_model.verts:
            add_vert(rk_vert)

        bm.verts.index_update()
        bm.verts.ensure_lookup_table()
        # add uvs to the new face
        uv_layer = bm.loops.layers.uv.verify()
        # bm.faces.layers.tex.verify()

        bm.verts.ensure_lookup_table()
        for i, rk_tri in enumerate(rk_mesh.triangles):
            rk_tri_verts = (
                rk_model.verts[rk_tri.index1],
                rk_model.verts[rk_tri.index2],
                rk_model.verts[rk_tri.index3],
            )

            try:
                face = bm.faces.new((
                    bm.verts[rk_tri.index1],
                    bm.verts[rk_tri.index2],
                    bm.verts[rk_tri.index3],
                ))
            except ValueError:
                rk_model.verts.append(rk_model.verts[rk_tri.index1])
                rk_model.verts.append(rk_model.verts[rk_tri.index2])
                rk_model.verts.append(rk_model.verts[rk_tri.index3])

                face = bm.faces.new((
                    add_vert(rk_model.verts[rk_tri.index1]),
                    add_vert(rk_model.verts[rk_tri.index2]),
                    add_vert(rk_model.verts[rk_tri.index3]),
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