import bpy
from mathutils import Vector
from math import tan, sin, atan, sqrt
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


def get_camera_half_angles(camera_obj: bpy.types.Object, scene: bpy.types.Scene):
    """Return (half_angle_x, half_angle_y) — the camera's true horizontal and
    vertical half-FOV, as it will actually render.

    cam_data.angle_x / angle_y are NOT used here on purpose: they're derived
    straight from sensor_width/sensor_height, which ignores the render
    resolution's aspect ratio. Blender only shows/uses sensor_height when
    sensor_fit == 'VERTICAL'; in 'AUTO' or 'HORIZONTAL' (the common cases)
    sensor_height is a stale/irrelevant value, so angle_y silently doesn't
    match what actually gets rendered - this is what was causing content to
    clip top/bottom.

    view_frame(scene=...) instead returns the camera's real frustum corners
    in local space, already accounting for sensor_fit, resolution_x/y and
    pixel aspect ratio, so it matches the render exactly.
    """
    frame = camera_obj.data.view_frame(scene=scene)  # 4 corners, local space
    half_width = max(abs(p.x) for p in frame)
    half_height = max(abs(p.y) for p in frame)
    depth = abs(frame[0].z)
    return atan(half_width / depth), atan(half_height / depth)


def distance_for_box_extent(half_size: float, half_angle_x: float, half_angle_y: float, margin: float = 1.1):
    """Distance needed so a half_size cube fits in frame, for CUBE mode
    (snapshot only, not rotation-safe).

    Unlike CYLINDER's horizontal/vertical asymmetry, a cube's near corner
    maximizes the lateral offset on BOTH axes and the depth offset toward
    the camera simultaneously (it's the same corner doing all three at
    once), so both axes get the same `half_size` proximity correction.
    """
    d_x = half_size + (half_size + margin) / tan(half_angle_x)
    d_y = half_size + (half_size + margin) / tan(half_angle_y)
    return max(d_x, d_y)


def distance_for_cylinder_extent(radius: float, half_height: float,
                                  half_angle_x: float, half_angle_y: float, margin: float = 1.1):
    """Distance needed so a Z-rotation-swept shape (radius from the pivot,
    plus a fixed half_height) fits in frame at EVERY rotation angle.

    The horizontal and vertical constraints are NOT independent here. The
    point that reaches maximum radius does so exactly when it's
    perpendicular to the view direction, i.e. at zero extra depth - so the
    horizontal-only formula is already exact on its own.

    Full-height material, though, sweeps through every depth as the object
    turns, including passing directly in front of the pivot - up to
    `radius` units closer to the camera than the pivot itself. That's the
    moment it's most magnified, so the vertical requirement has to budget
    for being that much closer, not just for half_height alone. Omitting
    this term (as a flat half_height / tan(angle) would) undershoots the
    distance and lets the object clip top/bottom during the turnaround.
    """
    d_x = (radius + margin) / tan(half_angle_x)
    d_y = radius + (half_height + margin) / tan(half_angle_y)
    return max(d_x, d_y)


def distance_for_sphere(radius: float, half_angle_x: float, half_angle_y: float, margin: float = 1.1):
    """Distance needed so a sphere of given radius fits in frame.

    Uses sin (tangent-line-to-sphere), which is the exact formula for a
    sphere rather than a flat plane at the same offset.
    """
    d_x = (radius + margin) / sin(half_angle_x)
    d_y = (radius + margin) / sin(half_angle_y)
    return max(d_x, d_y)


def fit_camera_to_objects(
    camera_obj: bpy.types.Object,
    objects: Sequence[bpy.types.Object],
    scene: bpy.types.Scene,
    pivot_obj: bpy.types.Object | None = None,
    mode = 'CYLINDER',
    margin: float = 1.1,
    depsgraph: bpy.types.Depsgraph | None = None,
):
    """Position camera_obj to frame `objects`, keeping X = 0 and
    rotation = (90deg, 0, 0), per the standard turnaround setup.

    scene: needed to resolve the camera's true render frustum (resolution,
    pixel aspect ratio, sensor fit) - see get_camera_half_angles().

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

    half_angle_x, half_angle_y = get_camera_half_angles(camera_obj, scene)

    if mode == 'SPHERE':
        center, radius = fit_sphere(points)
        distance = distance_for_sphere(radius, half_angle_x, half_angle_y, margin)
        target_z = center.z

    elif mode == 'CUBE':
        center, half_size = fit_cube(points)
        distance = distance_for_box_extent(half_size, half_angle_x, half_angle_y, margin)
        target_z = center.z

    elif mode == 'CYLINDER':
        pivot = (pivot_obj or objects[0]).matrix_world.translation
        radius, half_height, z_center = fit_cylinder(points, pivot)
        distance = distance_for_cylinder_extent(radius, half_height, half_angle_x, half_angle_y, margin)
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
        
        print('Objects: ', objects)

        try:
            fit_camera_to_objects(
                camera_obj, objects, context.scene,
                pivot_obj = pivot_obj,
                mode = self.mode,
                margin = self.margin,
            )
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        return {'FINISHED'}
