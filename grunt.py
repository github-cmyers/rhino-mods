import bpy
import math

# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for mat in bpy.data.materials:
    bpy.data.materials.remove(mat)

# ── Helpers ──────────────────────────────────────────────────────────────────

def sphere(name, loc, scale, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=loc, rotation=rot, segments=24, ring_count=16)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    return o

def cyl(name, loc, scale, rot=(0, 0, 0), verts=16):
    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, location=loc, rotation=rot, vertices=verts)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    return o

def cube(name, loc, scale, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    return o

def ico(name, loc, scale):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1, location=loc, subdivisions=2)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    return o

def mat(name, color, metallic=0.0, rough=0.5, emit=None, emit_strength=3.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree.nodes
    l = m.node_tree.links
    n.clear()
    out  = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value   = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value     = metallic
    bsdf.inputs['Roughness'].default_value    = rough
    if emit:
        bsdf.inputs['Emission Color'].default_value    = (*emit, 1.0)
        bsdf.inputs['Emission Strength'].default_value = emit_strength
    return m

def setmat(obj, m):
    if obj.data.materials:
        obj.data.materials[0] = m
    else:
        obj.data.materials.append(m)

# ── Materials ─────────────────────────────────────────────────────────────────

M_ORANGE  = mat('Orange',    (0.85, 0.32, 0.04), rough=0.75)
M_SKIN    = mat('Skin',      (0.38, 0.18, 0.42), rough=0.85)
M_ARMOR   = mat('Armor',     (0.12, 0.13, 0.18), metallic=0.85, rough=0.25)
M_METAL   = mat('Metal',     (0.50, 0.52, 0.55), metallic=0.95, rough=0.15)
M_VISOR   = mat('Visor',     (0.05, 0.30, 0.95), rough=0.02,
                emit=(0.05, 0.35, 1.0), emit_strength=4.0)
M_PLASMA  = mat('Plasma',    (0.05, 0.80, 0.25), rough=0.02,
                emit=(0.05, 0.90, 0.30), emit_strength=6.0)
M_TUBE    = mat('Tube',      (0.08, 0.08, 0.08), rough=0.95)
M_GROUND  = mat('Ground',    (0.10, 0.09, 0.08), rough=0.92)
M_DARK_ARMOR = mat('DarkArmor', (0.08, 0.09, 0.14), metallic=0.7, rough=0.3)

# ── GRUNT BODY ────────────────────────────────────────────────────────────────

# Torso – squat hunched egg
torso = sphere('Torso', (0, 0.05, 0.55), (0.52, 0.46, 0.48))
setmat(torso, M_ORANGE)

# Lower belly / hips – wider, drooping
hips = sphere('Hips', (0, 0.08, 0.18), (0.50, 0.44, 0.32))
setmat(hips, M_ORANGE)

# Chest armour plate
chest_plate = cube('ChestPlate', (0, -0.38, 0.60), (0.36, 0.07, 0.26))
setmat(chest_plate, M_ARMOR)

# Chest ridge detail strip
chest_ridge = cube('ChestRidge', (0, -0.42, 0.60), (0.10, 0.04, 0.22))
setmat(chest_ridge, M_DARK_ARMOR)

# ── HEAD ──────────────────────────────────────────────────────────────────────

head = sphere('Head', (0, -0.18, 1.22), (0.40, 0.38, 0.36))
setmat(head, M_SKIN)

# Cranial dome bumps (Unggoy crest)
for x_off, y_off, z_off, sc in [
    ( 0.00,  0.00, 0.34, (0.14, 0.12, 0.14)),
    ( 0.13, -0.05, 0.28, (0.08, 0.07, 0.09)),
    (-0.13, -0.05, 0.28, (0.08, 0.07, 0.09)),
]:
    b = sphere('CrestBump', (x_off, -0.18 + y_off, 1.22 + z_off), sc)
    setmat(b, M_SKIN)

# ── FACE / MASK ───────────────────────────────────────────────────────────────

# Breathing mask body
mask = cube('Mask', (0, -0.54, 1.12), (0.28, 0.10, 0.18))
setmat(mask, M_ARMOR)

# Visor lens
visor = sphere('Visor', (0, -0.61, 1.20), (0.20, 0.055, 0.10))
setmat(visor, M_VISOR)

# Eye lights behind visor
for sx in [-0.09, 0.09]:
    e = sphere('Eye', (sx, -0.60, 1.24), (0.045, 0.04, 0.045))
    setmat(e, M_VISOR)

# Mandible bumps (lower jaw protrusions)
for sx in [-0.14, 0.14]:
    mand = sphere('Mandible', (sx, -0.57, 1.02), (0.065, 0.065, 0.10))
    setmat(mand, M_SKIN)

# Chin strap
chin = cube('ChinStrap', (0, -0.56, 0.99), (0.22, 0.06, 0.04))
setmat(chin, M_ARMOR)

# ── METHANE TANK (back) ───────────────────────────────────────────────────────

tank = cyl('MethaneTank', (0, 0.46, 0.72), (0.20, 0.20, 0.42),
           rot=(0.28, 0, 0))
setmat(tank, M_METAL)

tank_top = sphere('TankCapTop', (0, 0.31, 1.14), (0.20, 0.20, 0.09))
setmat(tank_top, M_METAL)

tank_bot = sphere('TankCapBot', (0, 0.57, 0.32), (0.20, 0.20, 0.09))
setmat(tank_bot, M_METAL)

# Harness straps over torso
for sx in [-0.22, 0.22]:
    strap = cube('Strap', (sx, 0.08, 0.62), (0.04, 0.30, 0.28))
    setmat(strap, M_DARK_ARMOR)

# Tank band detail
band = cyl('TankBand', (0, 0.44, 0.72), (0.215, 0.215, 0.04), rot=(0.28, 0, 0))
setmat(band, M_DARK_ARMOR)

# Methane gauge (glowing green indicator)
gauge = sphere('Gauge', (0.17, 0.28, 0.88), (0.045, 0.04, 0.045))
setmat(gauge, M_PLASMA)

# Breathing tubes: tank → mask
for tx, ang in [(-0.16, 0.85), (0.16, 0.85)]:
    tube = cyl('BreathTube', (tx, -0.04, 1.02), (0.030, 0.030, 0.32),
               rot=(ang, 0, 0))
    setmat(tube, M_TUBE)

# ── SHOULDERS ─────────────────────────────────────────────────────────────────

for sx in [-1, 1]:
    pad = sphere('ShoulderPad', (sx * 0.62, -0.02, 0.86), (0.19, 0.14, 0.15))
    setmat(pad, M_ARMOR)
    pad_stud = sphere('ShoulderStud', (sx * 0.68, -0.04, 0.90), (0.05, 0.04, 0.05))
    setmat(pad_stud, M_METAL)

# ── ARMS ──────────────────────────────────────────────────────────────────────

for sx in [-1, 1]:
    upper = sphere('UpperArm', (sx * 0.70, -0.04, 0.66), (0.12, 0.12, 0.19))
    setmat(upper, M_ORANGE)

    fore = cyl('Forearm', (sx * 0.73, -0.12, 0.40), (0.075, 0.075, 0.19),
               rot=(0.18, 0, 0))
    setmat(fore, M_ORANGE)

    hand = sphere('Hand', (sx * 0.75, -0.20, 0.22), (0.095, 0.085, 0.075))
    setmat(hand, M_SKIN)

    # Wrist band
    wb = cyl('WristBand', (sx * 0.74, -0.17, 0.28), (0.082, 0.082, 0.045),
             rot=(0.18, 0, 0))
    setmat(wb, M_ARMOR)

# ── LEGS ──────────────────────────────────────────────────────────────────────

for sx in [-1, 1]:
    thigh = cyl('Thigh', (sx * 0.22, 0.04, -0.08), (0.155, 0.155, 0.22))
    setmat(thigh, M_ORANGE)

    shin = cyl('Shin', (sx * 0.22, 0.07, -0.40), (0.115, 0.115, 0.20))
    setmat(shin, M_ORANGE)

    foot = sphere('Foot', (sx * 0.22, 0.14, -0.60), (0.16, 0.22, 0.09))
    setmat(foot, M_ARMOR)

    # Knee cap
    knee = sphere('Knee', (sx * 0.22, -0.02, -0.24), (0.09, 0.09, 0.07))
    setmat(knee, M_ARMOR)

    # Shin armour
    shin_plate = cube('ShinPlate', (sx * 0.22, -0.01, -0.40), (0.10, 0.05, 0.14))
    setmat(shin_plate, M_ARMOR)

# ── PLASMA PISTOL (left hand) ─────────────────────────────────────────────────

gun_body = cube('PlasmaBody', (-1.0, -0.24, 0.24), (0.17, 0.055, 0.095))
setmat(gun_body, M_ARMOR)

gun_top = cube('PlasmaTop', (-0.98, -0.24, 0.32), (0.12, 0.05, 0.04))
setmat(gun_top, M_DARK_ARMOR)

gun_barrel = cyl('PlasmaBarrel', (-1.22, -0.26, 0.25), (0.038, 0.038, 0.17),
                 rot=(0, math.pi / 2, 0))
setmat(gun_barrel, M_ARMOR)

gun_glow = sphere('PlasmaGlow', (-1.39, -0.26, 0.25), (0.050, 0.050, 0.050))
setmat(gun_glow, M_PLASMA)

# ── GROUND ────────────────────────────────────────────────────────────────────

bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, -0.67))
ground = bpy.context.active_object
ground.name = 'Ground'
setmat(ground, M_GROUND)

# ── LIGHTING ──────────────────────────────────────────────────────────────────

# Key light (warm, front-left-top)
bpy.ops.object.light_add(type='AREA', location=(2.8, -2.8, 4.2))
kl = bpy.context.active_object
kl.data.energy = 900
kl.data.size   = 3.0
kl.data.color  = (1.0, 0.92, 0.80)
kl.rotation_euler = (math.radians(50), 0, math.radians(40))

# Fill light (cool, right)
bpy.ops.object.light_add(type='AREA', location=(-3.0, -1.5, 2.5))
fl = bpy.context.active_object
fl.data.energy = 350
fl.data.size   = 4.5
fl.data.color  = (0.70, 0.80, 1.0)
fl.rotation_euler = (math.radians(40), 0, math.radians(-50))

# Rim light (back-top, blue-purple Halo vibe)
bpy.ops.object.light_add(type='SPOT', location=(0.3, 3.8, 3.5))
rl = bpy.context.active_object
rl.data.energy      = 600
rl.data.spot_size   = math.radians(45)
rl.data.spot_blend  = 0.3
rl.data.color       = (0.45, 0.55, 1.0)
rl.rotation_euler   = (math.radians(-50), 0, math.radians(5))

# Under-glow (plasma pistol atmosphere)
bpy.ops.object.light_add(type='POINT', location=(-1.1, -0.3, 0.3))
pg = bpy.context.active_object
pg.data.energy = 120
pg.data.color  = (0.1, 1.0, 0.3)

# ── CAMERA ────────────────────────────────────────────────────────────────────

bpy.ops.object.camera_add(location=(2.6, -3.2, 1.6))
cam = bpy.context.active_object
cam.rotation_euler = (math.radians(73), 0, math.radians(39))
bpy.context.scene.camera = cam
cam.data.lens = 50

# ── WORLD ─────────────────────────────────────────────────────────────────────

world = bpy.data.worlds['World']
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value    = (0.015, 0.020, 0.060, 1.0)
bg.inputs['Strength'].default_value = 0.4

# ── RENDER ────────────────────────────────────────────────────────────────────

scene = bpy.context.scene
scene.render.engine          = 'CYCLES'
scene.cycles.samples         = 200
scene.cycles.use_denoising   = True
scene.render.resolution_x    = 800
scene.render.resolution_y    = 1000
scene.render.filepath        = '/home/user/rhino-mods/grunt_render.png'
scene.render.image_settings.file_format = 'PNG'

# Force CPU rendering (no GPU in headless env)
scene.cycles.device = 'CPU'
bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'NONE'

print("Starting render...")
bpy.ops.render.render(write_still=True)
print("Render complete → grunt_render.png")
