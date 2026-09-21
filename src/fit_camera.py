import bpy
from mathutils import Vector
from math import tan, sin, atan, sqrt
from collections.abc import Sequence


def get_world_points(objects: Sequence[bpy.types.Object], depsgraph):
    """World-space points for the given objects - actual (deformed) mesh
    vertices where available, bounding-box corners as a fallback.

    Real vertices matter here: an object's 8 AABB corners can include
    "phantom" extremes no vertex actually occupies (e.g. a wing or a flat
    mane card whose bounding box corner sits in empty air), which silently
    inflates every fit mode. Vertices are the true, tight point cloud.
    """
    points: list[Vector] = []
    for obj in objects:
        if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
            continue
        eval_obj = obj.evaluated_get(depsgraph)
        mw = eval_obj.matrix_world
        try:
            mesh = eval_obj.data
            if eval_obj.type == 'MESH' and mesh is not None and len(mesh.vertices) > 0:
                for v in mesh.vertices:
                    points.append(mw @ v.co)
            else:
                # Curves/text/metaballs: no direct vertex list, fall back
                # to the (still evaluated, still posed) bounding box.
                for corner in eval_obj.bound_box:
                    points.append(mw @ Vector(corner))
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
    """Return (radial_points, z_center) around a Z-axis pivot.

    radial_points: list of (radius, z) - each point's OWN distance from the
    pivot axis, kept paired with its OWN height. Collapsing these into two
    separate global maxima (max radius, max height) and combining them
    afterward is wrong whenever the widest point and the tallest point
    aren't the same point (a wingtip vs. a horn tip, say) - it invents a
    worst case that never actually occurs during the rotation. Keeping the
    pairing lets the distance function find the true worst point.
    z_center: vertical center, unaffected by Z rotation.
    """
    if not points:
        return [], pivot.z
    zs = [p.z for p in points]
    z_center = (min(zs) + max(zs)) / 2
    radial_points = [
        (sqrt((p.x - pivot.x) ** 2 + (p.y - pivot.y) ** 2), p.z)
        for p in points
    ]
    return radial_points, z_center


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


def distance_for_box_extent(half_size: float, half_angle_x: float, half_angle_y: float):
    """Distance needed so a half_size cube EXACTLY fits in frame (touching
    the edges), for CUBE mode (snapshot only, not rotation-safe).

    Unlike CYLINDER's horizontal/vertical asymmetry, a cube's near corner
    maximizes the lateral offset on BOTH axes and the depth offset toward
    the camera simultaneously (it's the same corner doing all three at
    once), so both axes get the same `half_size` proximity correction.
    """
    d_x = half_size + half_size / tan(half_angle_x)
    d_y = half_size + half_size / tan(half_angle_y)
    return max(d_x, d_y)


def distance_for_cylinder_extent(radial_points: list[tuple], z_center: float,
                                  half_angle_x: float, half_angle_y: float):
    """Distance needed so a Z-rotation-swept point cloud EXACTLY fits in
    frame (touching the edges) at EVERY rotation angle.

    Horizontal: independent of height. Whatever point ends up with the
    largest radius reaches its maximum lateral offset exactly when it's
    perpendicular to the view direction, i.e. at zero extra depth - so a
    single flat formula using the largest radius is already exact.

    Vertical: NOT independent of radius, and NOT safe to compute from
    global maxima. Any given point sweeps through every depth as the
    object turns, including passing directly in front of the pivot - at
    that moment it's `radius` units closer to the camera than the pivot,
    which is when ITS OWN height is most magnified. The worst case across
    the whole rotation is the point that maximizes (radius + height /
    tan(angle)) - which is generally NOT the same point that has the
    largest radius alone, or the largest height alone. Combining those two
    separate maxima (as an earlier version of this function did) invents a
    worst case with a wider wingspan than any actual point plus the full
    height of some unrelated, taller point - producing a much bigger
    distance, and much more empty margin, than the model actually needs.
    """
    if not radial_points:
        return 0.0
    max_radius = max(r for r, _ in radial_points)
    d_x = max_radius / tan(half_angle_x)
    d_y = max(
        r + abs(z - z_center) / tan(half_angle_y)
        for r, z in radial_points
    )
    return max(d_x, d_y)


def distance_for_sphere(radius: float, half_angle_x: float, half_angle_y: float):
    """Distance needed so a sphere of given radius EXACTLY fits in frame.

    Uses sin (tangent-line-to-sphere), which is the exact formula for a
    sphere rather than a flat plane at the same offset.
    """
    d_x = radius / sin(half_angle_x)
    d_y = radius / sin(half_angle_y)
    return max(d_x, d_y)


def fit_camera_to_objects(
    camera_obj: bpy.types.Object,
    objects: Sequence[bpy.types.Object],
    scene: bpy.types.Scene,
    pivot_obj: bpy.types.Object | None = None,
    margin: float = 1.1,
    depsgraph: bpy.types.Depsgraph | None = None,
):
    """Position camera_obj to frame `objects`, keeping X = 0 and
    rotation = (90deg, 0, 0), per the standard turnaround setup.

    scene: needed to resolve the camera's true render frustum (resolution,
    pixel aspect ratio, sensor fit) - see get_camera_half_angles().

    pivot_obj: the object the turnaround driver rotates (usually the
    armature). Defaults to the first of `objects`. Radial distance for the
    fit is measured from its origin, not the point cloud's centroid.

    margin: multiplier on the exact-fit distance, applied once at the end
    rather than folded into the geometry. 1.0 = object exactly touches the
    frame edges; 1.1 = camera backs off an extra 10% for breathing room,
    scaling with the model's own size instead of a flat world-space
    amount that would be invisible on a big model and overwhelming on a
    small one.
    """
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    points = get_world_points(objects, depsgraph)
    if not points:
        raise ValueError("No boundable geometry found in the given objects.")

    cam_data: bpy.types.Camera = camera_obj.data # type: ignore
    if cam_data.type != 'PERSP':
        raise ValueError("This fit logic targets a perspective camera "
                          "(orthographic needs ortho_scale, not distance).")

    half_angle_x, half_angle_y = get_camera_half_angles(camera_obj, scene)

    pivot = (pivot_obj or objects[0]).matrix_world.translation
    radial_points, z_center = fit_cylinder(points, pivot)
    distance = distance_for_cylinder_extent(radial_points, z_center, half_angle_x, half_angle_y) * margin
    target_z = z_center

    pivot_y = (pivot_obj or objects[0]).matrix_world.translation.y

    camera_obj.location.x = 0.0
    camera_obj.location.y = pivot_y - distance
    camera_obj.location.z = target_z
    camera_obj.rotation_euler = (1.5707963267948966, 0.0, 0.0)  # radians(90), 0, 0

    return distance


class RK_OT_fit_camera(bpy.types.Operator):
    bl_idname = "rk.fit_camera"
    bl_label = "Fit Camera to Selection"
    bl_options = {'REGISTER', 'UNDO'}

    margin: bpy.props.FloatProperty(
        name = "Margin", default = 0.5, min = -10.0, max = 10.0,
        description = "Margin for extra space from edge, 0 = touching edges",
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
        
        margin = 1.0 + (self.margin / 10)

        try:
            fit_camera_to_objects(
                camera_obj, objects, context.scene,
                pivot_obj = pivot_obj,
                margin = margin,
            )
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        return {'FINISHED'}
