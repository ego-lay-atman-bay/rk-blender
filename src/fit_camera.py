import bpy
from mathutils import Vector
from math import tan, sin, sqrt
from collections.abc import Sequence


def get_world_bbox_points(objects: Sequence[bpy.types.Object], depsgraph):
    """World-space bounding-box corner points for the given objects.

    Uses the evaluated (post-modifier/post-armature-deform) object so posed
    or modified geometry is accounted for, not just the rest-pose bbox.
    """
    points: list[Vector] = []
    for obj in objects:
        if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
            continue
        eval_obj = obj.evaluated_get(depsgraph)
        try:
            for corner in eval_obj.bound_box:
                points.append(eval_obj.matrix_world @ Vector(corner))
        except (AttributeError, ReferenceError):
            continue
    return points


def fit_sphere(points: list[Vector]):
    """Return (center, radius) of a simple bounding sphere."""
    if not points:
        return Vector((0.0, 0.0, 0.0)), 0.0
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    center = Vector(((min(xs) + max(xs)) / 2,
                      (min(ys) + max(ys)) / 2,
                      (min(zs) + max(zs)) / 2))
    radius = max((p - center).length for p in points)
    return center, radius


def fit_cube(points: list[Vector]):
    """Return (center, half_size) using the largest single-axis half-extent."""
    if not points:
        return Vector((0.0, 0.0, 0.0)), 0.0
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    center = Vector(((min(xs) + max(xs)) / 2,
                      (min(ys) + max(ys)) / 2,
                      (min(zs) + max(zs)) / 2))
    half_size = max((max(xs) - min(xs)) / 2,
                     (max(ys) - min(ys)) / 2,
                     (max(zs) - min(zs)) / 2)
    return center, half_size


def fit_cylinder(points: list[Vector], pivot: Vector):
    """Return (radius, half_height, z_center) around a Z-axis pivot.

    radius: farthest XY distance from pivot.x/pivot.y across all points -
            this is what must fit horizontally at the worst rotation frame.
    half_height / z_center: vertical extent, unaffected by Z rotation.
    """
    if not points:
        return 0.0, 0.0, pivot.z
    radius: float = max(sqrt((p.x - pivot.x) ** 2 + (p.y - pivot.y) ** 2) for p in points)
    zs = [p.z for p in points]
    z_center = (min(zs) + max(zs)) / 2
    half_height = (max(zs) - min(zs)) / 2
    return radius, half_height, z_center


def distance_for_box_extent(half_width: float, half_height: float, cam_data: bpy.types.Camera, margin: float = 1.1):
    """Distance needed so a flat extent of +/-half_width, +/-half_height fits
    in frame, for CYLINDER and CUBE modes (tangent-to-corner, i.e. tan-based).
    """
    fov_x = cam_data.angle_x
    fov_y = cam_data.angle_y
    d_x = (half_width + margin) / tan(fov_x / 2)
    d_y = (half_height + margin) / tan(fov_y / 2)
    return max(d_x, d_y)


def distance_for_sphere(radius: float, cam_data: bpy.types.Camera, margin: float = 1.1):
    """Distance needed so a sphere of given radius fits in frame.

    Uses sin (tangent-line-to-sphere), which is the exact formula for a
    sphere rather than a flat plane at the same offset.
    """
    fov_x = cam_data.angle_x
    fov_y = cam_data.angle_y
    d_x = (radius + margin) / sin(fov_x / 2)
    d_y = (radius + margin) / sin(fov_y / 2)
    return max(d_x, d_y)


def fit_camera_to_objects(
    camera_obj: bpy.types.Object,
    objects: Sequence[bpy.types.Object],
    pivot_obj: bpy.types.Object | None = None,
    mode = 'CYLINDER',
    margin: float = 1.1,
    depsgraph: bpy.types.Depsgraph | None = None,
):
    """Position camera_obj to frame `objects`, keeping X = 0 and
    rotation = (90deg, 0, 0), per the standard turnaround setup.

    pivot_obj: the object the turnaround driver rotates (usually the
    armature). Defaults to the first of `objects`. Only matters for
    CYLINDER mode, where radial distance is measured from its origin
    rather than the bbox centroid.
    """
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    points = get_world_bbox_points(objects, depsgraph)
    if not points:
        raise ValueError("No boundable geometry found in the given objects.")

    cam_data: bpy.types.Camera = camera_obj.data # type: ignore
    if cam_data.type != 'PERSP':
        raise ValueError("This fit logic targets a perspective camera "
                          "(orthographic needs ortho_scale, not distance).")

    if mode == 'SPHERE':
        center, radius = fit_sphere(points)
        distance = distance_for_sphere(radius, cam_data, margin)
        target_z = center.z

    elif mode == 'CUBE':
        center, half_size = fit_cube(points)
        distance = distance_for_box_extent(half_size, half_size, cam_data, margin)
        target_z = center.z

    elif mode == 'CYLINDER':
        pivot = (pivot_obj or objects[0]).matrix_world.translation
        radius, half_height, z_center = fit_cylinder(points, pivot)
        distance = distance_for_box_extent(radius, half_height, cam_data, margin)
        target_z = z_center

    else:
        raise ValueError(f"Unknown fit mode: {mode}")

    pivot_y = (pivot_obj or objects[0]).matrix_world.translation.y if mode == 'CYLINDER' \
        else (fit_sphere(points)[0].y if mode == 'SPHERE' else fit_cube(points)[0].y)

    camera_obj.location.x = 0.0
    camera_obj.location.y = pivot_y - distance
    camera_obj.location.z = target_z
    camera_obj.rotation_euler = (1.5707963267948966, 0.0, 0.0)  # radians(90), 0, 0

    return distance


class RK_OT_fit_camera(bpy.types.Operator):
    bl_idname = "rk.fit_camera"
    bl_label = "Fit Camera to Selection"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name = "Fit Mode",
        items = [
            ('CYLINDER', "Cylinder (Recommended)",
             "Correct at every frame of a Z-axis turnaround"),
            ('SPHERE', "Sphere", "Safe under rotation around any axis"),
            ('CUBE', "Cube", "Rest-pose framing only, can clip while rotating"),
        ],
        default = 'CYLINDER',
    ) # type: ignore
    margin: bpy.props.FloatProperty(
        name="Margin", default = 1.1, min = 0.0, max = 3.0,
        description="Padding multiplier applied to the computed distance",
    ) # type: ignore

    def execute(self, context: bpy.types.Context):
        camera_obj: bpy.types.Camera | None = context.scene.camera
        if camera_obj is None:
            self.report({'ERROR'}, "No active scene camera.")
            return {'CANCELLED'}

        objects = context.selected_objects
        if not objects:
            self.report({'ERROR'}, "Select the object(s) to frame.")
            return {'CANCELLED'}

        # Prefer an armature in the selection as the rotation pivot,
        pivot_obj = next((o for o in objects if o.type == 'ARMATURE'), objects[0])
        if objects == [pivot_obj]:
            objects.extend(pivot_obj.children_recursive)

        try:
            fit_camera_to_objects(
                camera_obj, objects,
                pivot_obj = pivot_obj,
                mode = self.mode,
                margin = self.margin,
            )
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        return {'FINISHED'}

