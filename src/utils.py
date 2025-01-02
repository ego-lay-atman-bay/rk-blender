import math

import bpy
import mathutils
import numpy
from luna_kit import rk
from mathutils import Matrix, Vector
from PIL import Image


def pil_to_image(
    pil_image: Image.Image,
    name: str = 'NewImage',
    alpha: bool = False,
    flip_vertical: bool = False,
    flip_horizontal: bool = False,
):
    '''
    PIL image pixels is 2D array of byte tuple (when mode is 'RGB', 'RGBA') or byte (when mode is 'L')
    bpy image pixels is flat array of normalized values in RGBA order
    '''
    # setup PIL image conversion
    if flip_vertical:
        pil_image = pil_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if flip_horizontal:
        pil_image = pil_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    
    width = pil_image.width
    height = pil_image.height
    byte_to_normalized = 1.0 / 255.0
    # create new image
    bpy_image = bpy.data.images.new(name, width=width, height=height, alpha=alpha)

    # convert Image 'L' to 'RGBA', normalize then flatten 
    bpy_image.pixels.foreach_set(
        (numpy.asarray(
            pil_image.convert('RGBA'),
            dtype=numpy.float32,
        ) * byte_to_normalized).ravel(),
    )
    bpy_image.pack()
    return bpy_image

# Code from https://blender.stackexchange.com/a/90240/151009
def vec_roll_to_mat3(vec: Vector, roll: float):
    #port of the updated C function from armature.c
    #https://developer.blender.org/T39470
    #note that C accesses columns first, so all matrix indices are swapped compared to the C version

    nor = vec.normalized()
    THETA_THRESHOLD_NEGY = 1.0e-9
    THETA_THRESHOLD_NEGY_CLOSE = 1.0e-5

    #create a 3x3 matrix
    bMatrix = mathutils.Matrix().to_3x3()

    theta = 1.0 + nor[1]

    if (theta > THETA_THRESHOLD_NEGY_CLOSE) or ((nor[0] or nor[2]) and theta > THETA_THRESHOLD_NEGY):

        bMatrix[1][0] = -nor[0]
        bMatrix[0][1] = nor[0]
        bMatrix[1][1] = nor[1]
        bMatrix[2][1] = nor[2]
        bMatrix[1][2] = -nor[2]
        if theta > THETA_THRESHOLD_NEGY_CLOSE:
            #If nor is far enough from -Y, apply the general case.
            bMatrix[0][0] = 1 - nor[0] * nor[0] / theta
            bMatrix[2][2] = 1 - nor[2] * nor[2] / theta
            bMatrix[0][2] = bMatrix[2][0] = -nor[0] * nor[2] / theta

        else:
            #If nor is too close to -Y, apply the special case.
            theta = nor[0] * nor[0] + nor[2] * nor[2]
            bMatrix[0][0] = (nor[0] + nor[2]) * (nor[0] - nor[2]) / -theta
            bMatrix[2][2] = -bMatrix[0][0]
            bMatrix[0][2] = bMatrix[2][0] = 2.0 * nor[0] * nor[2] / theta

    else:
        #If nor is -Y, simple symmetry by Z axis.
        bMatrix = mathutils.Matrix().to_3x3()
        bMatrix[0][0] = bMatrix[1][1] = -1.0

    #Make Roll matrix
    rMatrix = mathutils.Matrix.Rotation(roll, 4, nor)

    #Combine and output result
    mat = rMatrix * bMatrix
    return mat

def mat3_to_vec_roll(mat):
    #this hasn't changed
    vec = mat.col[1]
    vecmat = vec_roll_to_mat3(mat.col[1], 0)
    vecmatinv = vecmat.inverted()
    rollmat = vecmatinv * mat
    roll = math.atan2(rollmat[0][2], rollmat[2][2])
    return vec, roll


def add_to_vertex_group(
    obj: bpy.types.Object,
    rk_bone: rk.Bone,
    weight: float,
    vert: bpy.types.MeshVertex,
):
    if rk_bone.name in obj.vertex_groups:
        vertex_group = obj.vertex_groups[rk_bone.name]
    else:
        vertex_group = obj.vertex_groups.new(name = rk_bone.name)
    
    vertex_group.add(
        index = [vert.index],
        weight = weight,
        type = 'ADD',
    )

def get_armatures():
    return [obj.name for obj in bpy.data.objects if obj.type == 'ARMATURE']
