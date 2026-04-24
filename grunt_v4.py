"""
Halo 3 Grunt - High quality render using pip bpy 5.0.1 with OIDN denoising.
Full PBR materials, subsurface scattering, multi-light setup.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
import numpy as np

try:
    from opensimplex import OpenSimplex
    HAS_NOISE = True
except ImportError:
    HAS_NOISE = False

random.seed(42)
rng = np.random.default_rng(42)
noise = OpenSimplex(seed=7) if HAS_NOISE else None

# ── helpers ──────────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=True)
    for col in [bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                bpy.data.lights, bpy.data.images, bpy.data.curves]:
        for item in col:
            col.remove(item)

def new_mat(name, base_color, roughness=0.6, metallic=0.0,
            emission=None, emission_strength=1.0, alpha=1.0,
            sss_radius=None, sss_scale=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out   = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf  = nt.nodes.new('ShaderNodeBsdfPrincipled')
    out.location  = (400, 0)
    bsdf.location = (0, 0)

    bsdf.inputs['Base Color'].default_value    = (*base_color, 1.0)
    bsdf.inputs['Roughness'].default_value     = roughness
    bsdf.inputs['Metallic'].default_value      = metallic
    bsdf.inputs['Alpha'].default_value         = alpha

    # SSS
    if sss_scale > 0 and sss_radius:
        bsdf.inputs['Subsurface Weight'].default_value = sss_scale
        bsdf.inputs['Subsurface Radius'].default_value = sss_radius

    if emission:
        bsdf.inputs['Emission Color'].default_value    = (*emission, 1.0)
        bsdf.inputs['Emission Strength'].default_value = emission_strength

    if alpha < 1.0:
        try:
            mat.blend_method  = 'BLEND'
            mat.shadow_method = 'CLIP'
        except AttributeError:
            pass  # bpy 5.x removed these; transparency handled differently

    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

def add_noise_displacement(obj, scale=0.02, freq=3.0):
    if not HAS_NOISE:
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=2, use_grid_fill=True)
    for v in bm.verts:
        n  = v.normal.normalized()
        d  = noise.noise3(v.co.x * freq, v.co.y * freq, v.co.z * freq)
        v.co += n * d * scale
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

def link(obj, col=None):
    if col:
        col.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)
    return obj

def primitive(ptype, name, loc, scale, rot=(0,0,0), mat=None, segments=32, rings=16):
    if ptype == 'sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=1, location=loc, segments=segments, ring_count=rings)
    elif ptype == 'cylinder':
        bpy.ops.mesh.primitive_cylinder_add(
            radius=1, depth=2, location=loc, vertices=segments)
    elif ptype == 'cube':
        bpy.ops.mesh.primitive_cube_add(location=loc)
    elif ptype == 'cone':
        bpy.ops.mesh.primitive_cone_add(
            radius1=1, radius2=0.1, depth=2, location=loc, vertices=segments)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.rotation_euler = rot
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    if mat:
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    return obj

def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj

def add_subsurf(obj, levels=2):
    mod = obj.modifiers.new('Subsurf', 'SUBSURF')
    mod.levels = levels
    mod.render_levels = levels
    return obj

# ── clear scene first ────────────────────────────────────────────────────────
clear_scene()

# ── materials ────────────────────────────────────────────────────────────────

SKIN_COLOR    = (0.55, 0.28, 0.08)
SKIN_DARK     = (0.30, 0.14, 0.04)
ARMOR_COLOR   = (0.08, 0.08, 0.10)
VISOR_COLOR   = (0.02, 0.60, 0.90)
METHANE_COLOR = (0.12, 0.12, 0.14)
TUBE_COLOR    = (0.50, 0.42, 0.00)
PLASMA_COLOR  = (0.05, 0.55, 0.85)
LENS_COLOR    = (0.90, 0.55, 0.05)
CLAW_COLOR    = (0.75, 0.65, 0.40)

m_skin    = new_mat('skin',    SKIN_COLOR,  roughness=0.75, metallic=0.0,
                    sss_radius=(0.8,0.4,0.2), sss_scale=0.15)
m_skin2   = new_mat('skin2',   SKIN_DARK,   roughness=0.80, metallic=0.0,
                    sss_radius=(0.5,0.25,0.1), sss_scale=0.10)
m_armor   = new_mat('armor',   ARMOR_COLOR, roughness=0.35, metallic=0.70)
m_visor   = new_mat('visor',   VISOR_COLOR, roughness=0.05, metallic=0.2,
                    emission=VISOR_COLOR, emission_strength=2.5, alpha=0.85)
m_methane = new_mat('methane', METHANE_COLOR, roughness=0.30, metallic=0.80)
m_tube    = new_mat('tube',    TUBE_COLOR,  roughness=0.55, metallic=0.05)
m_plasma  = new_mat('plasma',  PLASMA_COLOR, roughness=0.20, metallic=0.50,
                    emission=PLASMA_COLOR, emission_strength=1.5)
m_lens    = new_mat('lens',    LENS_COLOR,  roughness=0.05, metallic=0.1,
                    emission=LENS_COLOR, emission_strength=4.0)
m_claw    = new_mat('claw',    CLAW_COLOR,  roughness=0.50, metallic=0.05)

# ── scene ────────────────────────────────────────────────────────────────────

# ── torso ────────────────────────────────────────────────────────────────────
# Wide, squat, barrel-shaped body — classic Grunt silhouette
torso = primitive('sphere', 'torso', (0, 0, 0.85), (0.52, 0.44, 0.48),
                  mat=m_skin, segments=48, rings=24)
add_noise_displacement(torso, scale=0.018, freq=4.0)
smooth(torso); add_subsurf(torso, 2)

# Upper chest bump / collar
chest = primitive('sphere', 'chest_bump', (0, -0.10, 1.08), (0.30, 0.25, 0.22),
                  mat=m_skin, segments=32, rings=16)
smooth(chest)

# Belly — slightly different skin tone
belly = primitive('sphere', 'belly', (0, 0.12, 0.58), (0.38, 0.30, 0.34),
                  mat=m_skin2, segments=32, rings=16)
smooth(belly)

# Hips / lower body
hips = primitive('sphere', 'hips', (0, 0, 0.45), (0.42, 0.37, 0.28),
                 mat=m_skin, segments=32, rings=16)
smooth(hips); add_subsurf(hips, 1)

# ── head ─────────────────────────────────────────────────────────────────────
# Large, wide head sitting almost directly on the shoulders
head = primitive('sphere', 'head', (0, -0.05, 1.48), (0.42, 0.38, 0.40),
                 mat=m_skin, segments=48, rings=24)
add_noise_displacement(head, scale=0.015, freq=5.0)
smooth(head); add_subsurf(head, 2)

# Forehead crest — bony ridge characteristic of Grunts
for i, (bx, bz, bs) in enumerate([
        (0.00, 1.78, (0.14, 0.10, 0.10)),
        (-0.10, 1.72, (0.10, 0.08, 0.08)),
        ( 0.10, 1.72, (0.10, 0.08, 0.08)),
        (-0.18, 1.64, (0.08, 0.06, 0.07)),
        ( 0.18, 1.64, (0.08, 0.06, 0.07)),
]):
    b = primitive('sphere', f'crest_{i}', (bx, -0.10, bz), bs,
                  mat=m_skin2, segments=16, rings=8)
    smooth(b)

# Side cheek armour plates
for side in (-1, 1):
    cp = primitive('sphere', f'cheek_{side}', (side*0.32, 0.0, 1.44),
                   (0.14, 0.10, 0.18), mat=m_armor, segments=20, rings=10)
    smooth(cp)

# ── mask / breathing apparatus ───────────────────────────────────────────────
# Grunt breathing mask covers the lower face
mask = primitive('sphere', 'mask', (0, -0.28, 1.38), (0.30, 0.18, 0.22),
                 mat=m_armor, segments=32, rings=16)
smooth(mask)

# Central visor / eye lens (single wide visor)
visor = primitive('sphere', 'visor', (0, -0.36, 1.50), (0.28, 0.08, 0.14),
                  mat=m_visor, segments=32, rings=16)
smooth(visor)

# Side eye lenses (small goggle-style)
for side in (-1, 1):
    eye = primitive('sphere', f'eye_{side}', (side*0.18, -0.36, 1.52),
                    (0.10, 0.07, 0.09), mat=m_lens, segments=20, rings=10)
    smooth(eye)

# Mask breathing grille bumps
for i in range(3):
    gx = (i - 1) * 0.10
    g = primitive('cylinder', f'grille_{i}', (gx, -0.40, 1.30),
                  (0.03, 0.03, 0.04),
                  rot=(math.radians(90), 0, 0), mat=m_armor, segments=8)
    smooth(g)

# ── methane tank (back-pack) ──────────────────────────────────────────────────
tank_body = primitive('cylinder', 'tank_body', (0, 0.38, 0.90),
                      (0.22, 0.22, 0.45),
                      rot=(math.radians(10), 0, 0), mat=m_methane, segments=24)
smooth(tank_body)

tank_top = primitive('sphere', 'tank_top', (0, 0.42, 1.36),
                     (0.22, 0.22, 0.14), mat=m_methane, segments=16, rings=8)
smooth(tank_top)

tank_bot = primitive('sphere', 'tank_bot', (0, 0.34, 0.44),
                     (0.22, 0.22, 0.14), mat=m_methane, segments=16, rings=8)
smooth(tank_bot)

# Tank valve / nozzle
valve = primitive('cylinder', 'valve', (0, 0.60, 1.30),
                  (0.04, 0.04, 0.10),
                  rot=(math.radians(80), 0, 0), mat=m_armor, segments=12)

# ── breathing tubes (spline-based) ────────────────────────────────────────────
def make_tube(name, pts, radius=0.035, mat=None):
    curve_data = bpy.data.curves.new(name, 'CURVE')
    curve_data.dimensions   = '3D'
    curve_data.bevel_depth  = radius
    curve_data.bevel_resolution = 4
    curve_data.use_fill_caps = True
    spline = curve_data.splines.new('NURBS')
    spline.points.add(len(pts) - 1)
    for i, (x, y, z) in enumerate(pts):
        spline.points[i].co = (x, y, z, 1)
    spline.use_endpoint_u = True
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.scene.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj

# Left tube: tank -> mask
make_tube('tube_L', [
    ( 0.15, 0.55, 1.25),
    ( 0.22, 0.30, 1.28),
    ( 0.28, 0.05, 1.35),
    ( 0.22,-0.20, 1.35),
    ( 0.16,-0.32, 1.32),
], radius=0.030, mat=m_tube)

# Right tube
make_tube('tube_R', [
    (-0.15, 0.55, 1.25),
    (-0.22, 0.30, 1.28),
    (-0.28, 0.05, 1.35),
    (-0.22,-0.20, 1.35),
    (-0.16,-0.32, 1.32),
], radius=0.030, mat=m_tube)

# ── shoulders ────────────────────────────────────────────────────────────────
for side in (-1, 1):
    pad = primitive('sphere', f'shoulder_{side}', (side*0.60, 0.0, 1.02),
                    (0.20, 0.16, 0.16), mat=m_armor, segments=24, rings=12)
    smooth(pad)

# ── arms ─────────────────────────────────────────────────────────────────────
# Gibbon-style: long relative to body, angled down and outward
arm_configs = [
    # (side, upper_loc, upper_rot, lower_loc, lower_rot)
    ( 1, ( 0.75,-0.05, 0.82), (0.30,-0.20, 0.15), ( 0.88,-0.10, 0.52), (0.55,-0.15, 0.10)),
    (-1, (-0.75,-0.05, 0.82), (0.30, 0.20,-0.15), (-0.88,-0.10, 0.52), (0.55, 0.15,-0.10)),
]
for side, uloc, urot, lloc, lrot in arm_configs:
    s = str(side)
    upper = primitive('sphere', f'upper_arm_{s}', uloc, (0.13, 0.13, 0.28),
                      rot=urot, mat=m_skin, segments=20, rings=10)
    smooth(upper)
    lower = primitive('sphere', f'lower_arm_{s}', lloc, (0.11, 0.11, 0.26),
                      rot=lrot, mat=m_skin, segments=20, rings=10)
    smooth(lower)

# ── hands (oversized with claws) ─────────────────────────────────────────────
hand_configs = [
    ( 1, ( 0.92,-0.12, 0.26)),
    (-1, (-0.92,-0.12, 0.26)),
]
for side, hloc in hand_configs:
    s = str(side)
    palm = primitive('sphere', f'palm_{s}', hloc, (0.16, 0.14, 0.13),
                     mat=m_skin, segments=20, rings=10)
    smooth(palm)
    # Three thick fingers + thumb
    finger_offsets = [
        ( 0.00, -0.04,  0.10),
        ( 0.06, -0.04,  0.08),
        (-0.06, -0.04,  0.08),
        ( side*0.12,  0.04,  0.06),
    ]
    for fi, fo in enumerate(finger_offsets):
        fx = hloc[0] + fo[0]
        fy = hloc[1] + fo[1]
        fz = hloc[2] + fo[2]
        fing = primitive('sphere', f'finger_{s}_{fi}', (fx, fy, fz),
                         (0.04, 0.04, 0.09), mat=m_skin2, segments=12, rings=6)
        smooth(fing)
        # Claw tip
        cl = primitive('cone', f'claw_{s}_{fi}',
                       (fx, fy - 0.06, fz + 0.10),
                       (0.025, 0.025, 0.055),
                       rot=(math.radians(-30), 0, 0), mat=m_claw, segments=8)

# ── legs ─────────────────────────────────────────────────────────────────────
leg_configs = [
    ( 1, ( 0.28, 0.0, 0.22), ( 0.26, 0.02, -0.02)),
    (-1, (-0.28, 0.0, 0.22), (-0.26, 0.02,  0.02)),
]
for side, thigh_loc, shin_loc in leg_configs:
    s = str(side)
    thigh = primitive('sphere', f'thigh_{s}', thigh_loc, (0.17, 0.15, 0.24),
                      mat=m_skin, segments=20, rings=10)
    smooth(thigh)
    shin_z = shin_loc[2] - 0.22
    shin = primitive('sphere', f'shin_{s}',
                     (shin_loc[0], shin_loc[1], shin_z),
                     (0.14, 0.13, 0.20), mat=m_skin, segments=20, rings=10)
    smooth(shin)

# ── feet ─────────────────────────────────────────────────────────────────────
for side in (-1, 1):
    s = str(side)
    foot = primitive('sphere', f'foot_{s}', (side*0.28, 0.10, -0.24),
                     (0.18, 0.25, 0.10), mat=m_skin2, segments=20, rings=10)
    smooth(foot)
    # Two big toe-claws
    for ti, tx in enumerate([-0.04, 0.06]):
        tc = primitive('cone', f'toe_{s}_{ti}',
                       (side*0.28 + tx, 0.26, -0.26),
                       (0.04, 0.04, 0.08),
                       rot=(math.radians(50), 0, 0), mat=m_claw, segments=8)

# ── plasma pistol (right hand) ───────────────────────────────────────────────
pp_loc = (1.10, -0.20, 0.22)
# Main body
pp_body = primitive('sphere', 'pp_body', pp_loc, (0.14, 0.22, 0.10),
                    rot=(0, 0, math.radians(15)), mat=m_plasma, segments=24, rings=12)
smooth(pp_body)

# Barrel
pp_barrel = primitive('cylinder', 'pp_barrel',
                       (pp_loc[0] + 0.05, pp_loc[1] - 0.22, pp_loc[2]),
                       (0.04, 0.04, 0.18),
                       rot=(math.radians(90), 0, math.radians(10)), mat=m_plasma, segments=12)

# Energy coil glow
pp_coil = primitive('sphere', 'pp_coil',
                    (pp_loc[0] + 0.02, pp_loc[1] - 0.15, pp_loc[2]),
                    (0.06, 0.06, 0.06), mat=m_lens, segments=16, rings=8)

# ── ground plane ─────────────────────────────────────────────────────────────
m_ground = new_mat('ground', (0.06, 0.06, 0.07), roughness=0.90, metallic=0.0)
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, -0.28))
ground = bpy.context.active_object
ground.name = 'ground'
ground.data.materials.append(m_ground)

# ── lighting ──────────────────────────────────────────────────────────────────
def add_light(name, loc, energy, color=(1,1,1), ltype='AREA', size=2.0):
    light_data = bpy.data.lights.new(name, ltype)
    light_data.energy = energy
    light_data.color  = color
    if ltype == 'AREA':
        light_data.size = size
    elif ltype == 'SPOT':
        light_data.spot_size   = math.radians(45)
        light_data.spot_blend  = 0.3
    obj = bpy.data.objects.new(name, light_data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    # Point toward scene center
    direction = Vector((0, 0, 0.8)) - Vector(loc)
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj

# Key light — warm slightly from front-left
add_light('key',   ( 2.5, -2.5, 3.5), energy=600,  color=(1.00, 0.92, 0.80), ltype='AREA', size=2.5)
# Fill light — cool from right
add_light('fill',  (-2.0, -1.5, 2.0), energy=180,  color=(0.70, 0.80, 1.00), ltype='AREA', size=3.0)
# Rim/back light — strong backlit edge
add_light('rim',   ( 0.5,  3.0, 2.5), energy=400,  color=(0.90, 0.85, 1.00), ltype='AREA', size=1.5)
# Ground bounce
add_light('bounce',(0.0,  -0.5,-0.5), energy=80,   color=(1.00, 0.85, 0.60), ltype='AREA', size=4.0)
# Plasma pistol glow point
add_light('plasma_glow', (1.1, -0.35, 0.22), energy=60, color=(0.1, 0.7, 1.0), ltype='POINT')

# ── camera ───────────────────────────────────────────────────────────────────
cam_data = bpy.data.cameras.new('Camera')
cam_data.lens        = 70
cam_data.clip_start  = 0.1
cam_data.clip_end    = 100
cam_obj = bpy.data.objects.new('Camera', cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

cam_pos    = Vector((1.8, -2.6, 1.60))
target     = Vector((0.0,  0.0, 0.90))
direction  = target - cam_pos
cam_obj.location       = cam_pos
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

# ── render settings ──────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine              = 'CYCLES'
scene.render.resolution_x        = 1280
scene.render.resolution_y        = 1280
scene.render.film_transparent     = False

scene.cycles.samples              = 256
scene.cycles.use_denoising        = True

# Try OIDN (pip bpy 5.0.1 supports it)
try:
    scene.cycles.denoiser         = 'OPENIMAGEDENOISE'
    scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    print("OIDN denoising enabled")
except Exception as e:
    scene.cycles.use_denoising    = False
    print(f"OIDN not available: {e}")

scene.cycles.device               = 'CPU'
scene.render.filepath             = '/home/user/rhino-mods/grunt_render_v4.png'
scene.render.image_settings.file_format = 'PNG'

# World background — dark bluish-grey atmosphere
world = bpy.data.worlds.new('World')
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value    = (0.03, 0.04, 0.06, 1.0)
bg.inputs['Strength'].default_value = 0.4

print("Starting render...")
bpy.ops.render.render(write_still=True)
print("Render complete: grunt_render_v4.png")
