import bpy
import bmesh
import math
import numpy as np
from opensimplex import OpenSimplex
from scipy.interpolate import CubicSpline

noise = OpenSimplex(seed=137)

# ── Clear scene ───────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for m in list(bpy.data.materials): bpy.data.materials.remove(m)

# ── Primitive helpers ─────────────────────────────────────────────────────────

def sphere(name, loc, scale, rot=(0,0,0), segs=28, rings=18):
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=1, location=loc, rotation=rot, segments=segs, ring_count=rings)
    o = bpy.context.active_object
    o.name = name; o.scale = scale
    return o

def cyl(name, loc, scale, rot=(0,0,0), verts=20):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=1, depth=1, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.active_object
    o.name = name; o.scale = scale
    return o

def cone(name, loc, scale, rot=(0,0,0), verts=20):
    bpy.ops.mesh.primitive_cone_add(
        radius1=1, radius2=0.08, depth=1,
        location=loc, rotation=rot, vertices=verts)
    o = bpy.context.active_object
    o.name = name; o.scale = scale
    return o

def cube(name, loc, scale, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name; o.scale = scale
    return o

# ── bmesh subdivision + opensimplex displacement ──────────────────────────────

def subdivide(obj, cuts=2):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=cuts, use_grid_fill=True)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

def displace(obj, strength=0.038, freq=4.8):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    mw = obj.matrix_world
    for v in bm.verts:
        wp = mw @ v.co
        n = noise.noise3(wp.x * freq, wp.y * freq, wp.z * freq)
        v.co += v.normal * (n * strength)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

def organic(obj, strength=0.038, freq=4.8, cuts=2):
    subdivide(obj, cuts)
    displace(obj, strength, freq)

# ── scipy spline tube ─────────────────────────────────────────────────────────

def spline_tube(name, ctrl_pts, radius=0.028, segments=30, tverts=10):
    pts = np.array(ctrl_pts, dtype=float)
    t   = np.linspace(0, 1, len(pts))
    cs  = [CubicSpline(t, pts[:, i]) for i in range(3)]
    tf  = np.linspace(0, 1, segments)
    centers  = np.column_stack([cs[i](tf)    for i in range(3)])
    tangents = np.column_stack([cs[i](tf, 1) for i in range(3)])
    norms = np.linalg.norm(tangents, axis=1, keepdims=True)
    tangents /= np.where(norms < 1e-8, 1, norms)

    verts, faces = [], []
    prev_right = None
    for i, (c, tv) in enumerate(zip(centers, tangents)):
        up = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(tv, up)) > 0.85:
            up = np.array([1.0, 0.0, 0.0])
        right = np.cross(tv, up)
        r_norm = np.linalg.norm(right)
        if r_norm < 1e-8:
            right = prev_right if prev_right is not None else np.array([1.0, 0.0, 0.0])
        else:
            right /= r_norm
        prev_right = right
        up2 = np.cross(right, tv)
        for j in range(tverts):
            a = 2 * math.pi * j / tverts
            verts.append((c + radius * (math.cos(a)*right + math.sin(a)*up2)).tolist())
        if i > 0:
            for j in range(tverts):
                a = (i-1)*tverts + j
                b = (i-1)*tverts + (j+1) % tverts
                cc = i*tverts + (j+1) % tverts
                d  = i*tverts + j
                faces.append((a, b, cc, d))

    mesh = bpy.data.meshes.new(name)
    obj  = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return obj

# ── Material helper ───────────────────────────────────────────────────────────

def mat(name, color, metallic=0.0, rough=0.5, emit=None, emit_str=4.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    ns = m.node_tree.nodes; ls = m.node_tree.links
    ns.clear()
    out  = ns.new('ShaderNodeOutputMaterial')
    bsdf = ns.new('ShaderNodeBsdfPrincipled')
    ls.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value   = metallic
    bsdf.inputs['Roughness'].default_value  = rough
    if emit:
        bsdf.inputs['Emission Color'].default_value    = (*emit, 1.0)
        bsdf.inputs['Emission Strength'].default_value = emit_str
    return m

def setmat(obj, m):
    if obj.data.materials: obj.data.materials[0] = m
    else: obj.data.materials.append(m)

# ── Materials ─────────────────────────────────────────────────────────────────
M_ORANGE   = mat('Orange',    (0.85, 0.30, 0.03), rough=0.74)
M_SKIN     = mat('Skin',      (0.33, 0.14, 0.38), rough=0.90)
M_ARMOR    = mat('Armor',     (0.10, 0.11, 0.17), metallic=0.88, rough=0.20)
M_DARK_ARM = mat('DarkArmor', (0.06, 0.06, 0.11), metallic=0.72, rough=0.28)
M_METAL    = mat('Metal',     (0.46, 0.49, 0.53), metallic=0.96, rough=0.10)
M_VISOR    = mat('Visor',     (0.04, 0.26, 0.94), rough=0.02,
                  emit=(0.04, 0.32, 1.00), emit_str=6.0)
M_PLASMA   = mat('Plasma',    (0.04, 0.82, 0.24), rough=0.02,
                  emit=(0.04, 0.92, 0.28), emit_str=8.0)
M_TUBE     = mat('Tube',      (0.06, 0.06, 0.06), rough=0.96)
M_GROUND   = mat('Ground',    (0.08, 0.07, 0.06), rough=0.94)

# ═══════════════════════════════════════════════════════════════════════════════
# GRUNT MODEL
# Reference: squat body, huge head, gibbon-long arms, huge hands/feet,
#            conical methane tank, mask covers >half the head
# ═══════════════════════════════════════════════════════════════════════════════

# ── Torso ─────────────────────────────────────────────────────────────────────
torso = sphere('Torso', (0, 0.05, 0.54), (0.54, 0.47, 0.50), segs=28, rings=18)
setmat(torso, M_ORANGE)
organic(torso, strength=0.018, freq=5.2, cuts=2)

belly = sphere('Belly', (0, -0.06, 0.22), (0.50, 0.52, 0.30), segs=28, rings=18)
setmat(belly, M_ORANGE)
organic(belly, strength=0.016, freq=5.5, cuts=2)

hips = sphere('Hips', (0, 0.10, 0.16), (0.46, 0.40, 0.26))
setmat(hips, M_ORANGE)

# ── Chest armour ──────────────────────────────────────────────────────────────
chest = cube('ChestPlate', (0, -0.41, 0.60), (0.38, 0.065, 0.27))
setmat(chest, M_ARMOR)
chest_ridge = cube('ChestRidge', (0, -0.452, 0.60), (0.10, 0.034, 0.22))
setmat(chest_ridge, M_DARK_ARM)
for sx in [-0.22, 0.22]:
    cd = cube('ChestDetail', (sx, -0.448, 0.62), (0.058, 0.028, 0.058))
    setmat(cd, M_DARK_ARM)

# ── Head ──────────────────────────────────────────────────────────────────────
head = sphere('Head', (0, -0.24, 1.22), (0.44, 0.41, 0.39), segs=32, rings=20)
setmat(head, M_SKIN)
organic(head, strength=0.022, freq=4.4, cuts=2)

# Cranial crest bumps
for (ox, oy, oz, sc) in [
    ( 0.00,  0.00,  0.38, (0.17, 0.13, 0.17)),
    ( 0.16, -0.02,  0.30, (0.095, 0.085, 0.10)),
    (-0.16, -0.02,  0.30, (0.095, 0.085, 0.10)),
    ( 0.00, -0.05,  0.42, (0.082, 0.072, 0.082)),
]:
    b = sphere('Crest', (ox, -0.24+oy, 1.22+oz), sc, segs=14, rings=10)
    setmat(b, M_SKIN)
    organic(b, strength=0.010, freq=6.5, cuts=1)

# ── Face / breathing mask (covers over half the head per reference) ────────────
mask = cube('MaskMain', (0, -0.63, 1.14), (0.33, 0.112, 0.23))
setmat(mask, M_ARMOR)
mask_chin = sphere('MaskChin', (0, -0.64, 0.97), (0.25, 0.104, 0.13))
setmat(mask_chin, M_ARMOR)
mask_brow = cube('MaskBrow', (0, -0.62, 1.36), (0.28, 0.090, 0.06))
setmat(mask_brow, M_ARMOR)

# Visor — wide wrap-around
visor = sphere('Visor', (0, -0.665, 1.22), (0.255, 0.058, 0.112))
setmat(visor, M_VISOR)
for sx in [-0.105, 0.105]:
    eg = sphere('EyeGlow', (sx, -0.655, 1.265), (0.050, 0.044, 0.050))
    setmat(eg, M_VISOR)

# Mandibles (4 protrusions, 2 per side)
for sx in [-1, 1]:
    for oy, oz, sz in [(0.0, 0.0, 0.10), (0.06, -0.06, 0.08)]:
        m = sphere('Mandible', (sx*0.17, -0.62+oy, 0.99+oz), (0.052, 0.052, sz))
        setmat(m, M_SKIN)

# Nose nub above mask
nose = sphere('Nose', (0, -0.64, 1.37), (0.055, 0.055, 0.048))
setmat(nose, M_SKIN)

# ── Methane tank — conical top per Halopedia reference ────────────────────────
tank_body = cyl('TankBody', (0, 0.52, 0.70), (0.22, 0.22, 0.42), rot=(0.26, 0, 0))
setmat(tank_body, M_METAL)

tank_cone = cone('TankCone', (0, 0.34, 1.10), (0.22, 0.22, 0.30), rot=(0.26, 0, 0))
setmat(tank_cone, M_METAL)

tank_base = sphere('TankBase', (0, 0.64, 0.30), (0.22, 0.22, 0.10))
setmat(tank_base, M_METAL)

band1 = cyl('TankBand1', (0, 0.50, 0.70), (0.235, 0.235, 0.048), rot=(0.26, 0, 0))
setmat(band1, M_DARK_ARM)
band2 = cyl('TankBand2', (0, 0.40, 0.90), (0.228, 0.228, 0.040), rot=(0.26, 0, 0))
setmat(band2, M_DARK_ARM)

gauge = sphere('Gauge', (0.19, 0.31, 0.88), (0.040, 0.036, 0.040))
setmat(gauge, M_PLASMA)

for sx in [-0.25, 0.25]:
    strap = cube('Strap', (sx, 0.12, 0.62), (0.036, 0.34, 0.32))
    setmat(strap, M_DARK_ARM)

# ── Breathing tubes — scipy splines ──────────────────────────────────────────
for sx, sign in [(-1, -1), (1, 1)]:
    pts = [
        [sign*0.19, 0.36, 1.02],
        [sign*0.21, 0.12, 1.02],
        [sign*0.19, -0.18, 1.08],
        [sign*0.17, -0.54, 1.13],
    ]
    tube = spline_tube(f'Tube_{sx}', pts, radius=0.028, segments=30)
    setmat(tube, M_TUBE)

# ── Shoulders ─────────────────────────────────────────────────────────────────
for sx in [-1, 1]:
    pad = sphere('Shoulder', (sx*0.63, -0.04, 0.88), (0.205, 0.150, 0.165))
    setmat(pad, M_ARMOR)
    stud = sphere('PadStud', (sx*0.70, -0.050, 0.92), (0.046, 0.038, 0.046))
    setmat(stud, M_METAL)

# ── Arms — gibbon-long, thin upper, massive hand ──────────────────────────────
for sx in [-1, 1]:
    # Thin upper arm
    ua = sphere('UpperArm', (sx*0.70, -0.06, 0.66), (0.088, 0.088, 0.195))
    setmat(ua, M_ORANGE)

    elbow = sphere('Elbow', (sx*0.77, -0.14, 0.42), (0.082, 0.082, 0.080))
    setmat(elbow, M_ORANGE)

    # Long forearm
    fa = cyl('Forearm', (sx*0.81, -0.24, 0.22), (0.068, 0.068, 0.26), rot=(0.28, 0, 0))
    setmat(fa, M_ORANGE)

    # Wrist band
    wb = cyl('Wrist', (sx*0.83, -0.36, 0.02), (0.076, 0.076, 0.040), rot=(0.28, 0, 0))
    setmat(wb, M_ARMOR)

    # HUGE hand (disproportionately large per reference)
    hand = sphere('Hand', (sx*0.84, -0.46, -0.10), (0.165, 0.145, 0.125))
    setmat(hand, M_SKIN)
    organic(hand, strength=0.014, freq=6.2, cuts=1)

    # Three thick fingers
    for fi, (fx, fz) in enumerate([(-0.065, -0.04), (0.0, -0.055), (0.065, -0.04)]):
        fing = cyl(f'Finger_{sx}_{fi}',
                   (sx*(0.84 + fx*sx), -0.56, -0.10 + fz),
                   (0.026, 0.026, 0.10), rot=(0.12, 0, 0))
        setmat(fing, M_SKIN)

# ── Legs — thin upper, large foot ─────────────────────────────────────────────
for sx in [-1, 1]:
    thigh = cyl('Thigh', (sx*0.23, 0.04, -0.06), (0.130, 0.130, 0.205))
    setmat(thigh, M_ORANGE)

    knee = sphere('Knee', (sx*0.23, -0.02, -0.27), (0.088, 0.088, 0.070))
    setmat(knee, M_ARMOR)

    shin = cyl('Shin', (sx*0.23, 0.06, -0.42), (0.112, 0.112, 0.185))
    setmat(shin, M_ORANGE)

    shin_pl = cube('ShinPlate', (sx*0.23, -0.02, -0.42), (0.098, 0.046, 0.125))
    setmat(shin_pl, M_ARMOR)

    # Huge foot
    foot = sphere('Foot', (sx*0.23, 0.20, -0.62), (0.215, 0.300, 0.095))
    setmat(foot, M_ARMOR)

    leg_trim = cyl('LegTrim', (sx*0.23, -0.01, -0.21), (0.148, 0.148, 0.038))
    setmat(leg_trim, M_ARMOR)

    # Toe claws
    for fi, (fx, fy) in enumerate([(-0.09, 0.14), (0.0, 0.16), (0.09, 0.14)]):
        claw = cone(f'Claw_{sx}_{fi}',
                    (sx*(0.23 + fx*sx), 0.20+fy, -0.64),
                    (0.024, 0.024, 0.068), rot=(math.pi/2, 0, 0))
        setmat(claw, M_DARK_ARM)

# ── Plasma pistol ─────────────────────────────────────────────────────────────
gun      = cube('PlasmaBody',   (-1.06, -0.46, 0.00), (0.185, 0.056, 0.105))
setmat(gun, M_ARMOR)
gun_top  = cube('PlasmaTop',    (-1.02, -0.46, 0.115), (0.135, 0.050, 0.038))
setmat(gun_top, M_DARK_ARM)
gun_grip = cube('PlasmaGrip',   (-0.96, -0.46, -0.05), (0.058, 0.050, 0.082))
setmat(gun_grip, M_DARK_ARM)
barrel   = cyl('PlasmaBarrel',  (-1.28, -0.47, 0.01), (0.034, 0.034, 0.20),
               rot=(0, math.pi/2, 0))
setmat(barrel, M_ARMOR)
glow     = sphere('PlasmaGlow', (-1.46, -0.47, 0.01), (0.046, 0.046, 0.046))
setmat(glow, M_PLASMA)

# ── Ground ────────────────────────────────────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, -0.70))
ground = bpy.context.active_object
ground.name = 'Ground'
setmat(ground, M_GROUND)

# ── Lighting ──────────────────────────────────────────────────────────────────
# Warm key light
bpy.ops.object.light_add(type='AREA', location=(3.0, -3.2, 4.6))
kl = bpy.context.active_object
kl.data.energy = 1100; kl.data.size = 3.2; kl.data.color = (1.0, 0.90, 0.76)
kl.rotation_euler = (math.radians(48), 0, math.radians(40))

# Cool fill
bpy.ops.object.light_add(type='AREA', location=(-3.2, -1.8, 3.0))
fl = bpy.context.active_object
fl.data.energy = 420; fl.data.size = 5.0; fl.data.color = (0.65, 0.76, 1.0)
fl.rotation_euler = (math.radians(42), 0, math.radians(-52))

# Blue-purple rim (Halo atmosphere)
bpy.ops.object.light_add(type='SPOT', location=(0.4, 4.4, 4.0))
rl = bpy.context.active_object
rl.data.energy = 750; rl.data.spot_size = math.radians(40)
rl.data.spot_blend = 0.25; rl.data.color = (0.40, 0.50, 1.0)
rl.rotation_euler = (math.radians(-54), 0, math.radians(6))

# Plasma pistol green under-glow
bpy.ops.object.light_add(type='POINT', location=(-1.4, -0.5, 0.02))
pg = bpy.context.active_object
pg.data.energy = 170; pg.data.color = (0.06, 1.0, 0.26)

# Visor blue bounce
bpy.ops.object.light_add(type='POINT', location=(0, -0.75, 1.22))
vl = bpy.context.active_object
vl.data.energy = 90; vl.data.color = (0.08, 0.38, 1.0)

# ── Camera ────────────────────────────────────────────────────────────────────
bpy.ops.object.camera_add(location=(2.5, -3.6, 1.5))
cam = bpy.context.active_object
cam.rotation_euler = (math.radians(75), 0, math.radians(37))
bpy.context.scene.camera = cam
cam.data.lens = 52

# ── World ─────────────────────────────────────────────────────────────────────
world = bpy.data.worlds['World']
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value    = (0.010, 0.014, 0.052, 1.0)
bg.inputs['Strength'].default_value = 0.32

# ── Render ────────────────────────────────────────────────────────────────────
scene = bpy.context.scene
scene.render.engine         = 'CYCLES'
scene.cycles.samples        = 256
scene.cycles.use_denoising  = True
scene.render.resolution_x   = 900
scene.render.resolution_y   = 1100
scene.render.filepath       = '/home/user/rhino-mods/grunt_render.png'
scene.render.image_settings.file_format = 'PNG'
scene.cycles.device = 'CPU'
bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'NONE'

print("Starting render...")
bpy.ops.render.render(write_still=True)
print("Done → grunt_render.png")
