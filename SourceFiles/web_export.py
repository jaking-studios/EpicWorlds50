"""
Export the currently open EpicWorlds50 world for the browser viewer.

Writes to <root>/web/worlds/<ID>/:
  world.glb        Draco-compressed scene (procedural materials flattened to PBR colours,
                   terrain paint exported as vertex colours, vegetation SOURCE meshes only)
  instances.bin    Float32 4x4 matrices (three.js Y-up, column-major) for every
                   Geometry Nodes vegetation instance at viewport-LOD density
  meta.json        title/lore/landmark, sky + fog + sun, camera tour paths, cloud layers,
                   particle colours, and every animation driver expression

Run inside Blender with the world open:  exec(open(".../web_export.py").read())
The .blend is NOT saved afterwards; the script reverts the file when done.
"""
import bpy, os, json, struct, re, random
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(bpy.data.filepath))
WID = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
OUT = os.path.join(ROOT, "web", "worlds", WID)
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
C = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))   # Blender Z-up -> three Y-up
Ci = C.inverted()
MAX_PER_PART = 12000


def to_three(m):
    t = C @ m @ Ci
    return [t[r][c] for c in range(4) for r in range(4)]  # column-major


def yup(v):
    return [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]


def lin_to_hex(c):
    s = [max(0.0, min(1.0, x)) for x in c[:3]]
    s = [(x * 12.92) if x <= 0.0031308 else (1.055 * x ** (1 / 2.4) - 0.055) for x in s]
    return "#%02x%02x%02x" % tuple(int(x * 255 + 0.5) for x in s)


# ---------------------------------------------------------------- 1. vegetation instances
sc.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
inst = {}
for oi in dg.object_instances:
    if not oi.is_instance or not oi.parent or not oi.parent.name.startswith("VEG_"):
        continue
    if oi.object.type != 'MESH':
        continue
    inst.setdefault(oi.object.original.name, []).append(oi.matrix_world.copy())
rnd = random.Random(1)
index, blob = {}, bytearray()
for name, mats in inst.items():
    if len(mats) > MAX_PER_PART:
        mats = rnd.sample(mats, MAX_PER_PART)
    index[name] = [len(blob) // 4, len(mats)]
    for m in mats:
        blob += struct.pack("<16f", *to_three(m))
with open(os.path.join(OUT, "instances.bin"), "wb") as f:
    f.write(blob)

# ---------------------------------------------------------------- 2. meta: atmosphere, cameras, drivers
meta = {"id": WID, "title": sc.get("jaking_company", ""), "instances": index}
docs = os.path.join(ROOT, "Documentation", "worlds", WID + ".json")
if os.path.exists(docs):
    d = json.load(open(docs))
    meta.update({k: d.get(k) for k in ("title", "lore", "category", "mega_landmark")})
w = sc.world
ramp = next((n for n in w.node_tree.nodes if n.bl_idname == "ShaderNodeValToRGB"), None) if w and w.node_tree else None
if ramp:
    meta["sky"] = {"horizon": lin_to_hex(ramp.color_ramp.elements[0].color), "zenith": lin_to_hex(ramp.color_ramp.elements[1].color)}
fog = bpy.data.objects.get("AtmosphereFog")
if fog and fog.data.materials:
    vs = next((n for n in fog.data.materials[0].node_tree.nodes if n.bl_idname == "ShaderNodeVolumePrincipled"), None)
    if vs:
        meta["fog"] = {"color": lin_to_hex(vs.inputs["Color"].default_value), "density": vs.inputs["Density"].default_value}
sun = bpy.data.objects.get("Sun")
if sun:
    d = sun.matrix_world.to_quaternion() @ Vector((0, 0, 1))
    meta["sun"] = {"dir": yup(d), "color": lin_to_hex(sun.data.color), "power": sun.data.energy}
clouds = []
for o in bpy.data.objects:
    if o.name.startswith("CloudLayer") and o.data.materials:
        b = o.data.materials[0].node_tree.nodes.get("Principled BSDF")
        rp = next((n for n in o.data.materials[0].node_tree.nodes if n.bl_idname == "ShaderNodeValToRGB"), None)
        clouds.append({"y": round(o.location.z, 1), "color": lin_to_hex(b.inputs["Base Color"].default_value) if b else "#ffffff",
                       "coverage": round(1 - rp.color_ramp.elements[0].position, 2) if rp else 0.4, "size": round(o.dimensions.x, 1)})
meta["clouds"] = clouds
parts = []
for o in bpy.data.objects:
    if o.type == 'MESH' and o.particle_systems:
        s = o.particle_systems[0].settings
        src = s.instance_object
        col = "#ffffff"
        if src and src.data.materials:
            b = src.data.materials[0].node_tree.nodes.get("Principled BSDF")
            if b:
                col = lin_to_hex(b.inputs["Base Color"].default_value)
        parts.append({"center": yup(o.location), "size": round(o.dimensions.x, 1), "count": min(4000, s.count), "color": col})
meta["particles"] = parts
focus = bpy.data.objects.get("LandmarkFocus")
meta["focus"] = yup(focus.location) if focus else [0, 0, 0]
tour = []
for mk in sorted(sc.timeline_markers, key=lambda m: m.frame):
    tour.append({"camera": mk.camera.name if mk.camera else "", "frame": mk.frame})
paths = {}
for cam in ("CAM_HeroReveal", "CAM_Flythrough", "CAM_Aerial"):
    co = bpy.data.objects.get(cam)
    if not co:
        continue
    pts = []
    for f in range(1, sc.frame_end + 1, 24):
        sc.frame_set(f)
        pts.append(yup(co.matrix_world.translation))
    paths[cam] = {"points": pts, "lens": co.data.lens}
sc.frame_set(1)
meta["tour"] = tour
meta["paths"] = paths
drivers = []
for o in bpy.data.objects:
    ad = o.animation_data
    if not ad:
        continue
    for fc in ad.drivers:
        ex = fc.driver.expression
        if "spd" in ex or fc.data_path not in ("location", "rotation_euler", "scale"):
            continue
        drivers.append({"name": o.name, "path": fc.data_path, "index": fc.array_index, "expr": ex})
meta["drivers"] = drivers
glow = []
for o in bpy.data.objects:
    if o.type == 'LIGHT' and o.data.type == 'POINT' and o.data.energy > 2000:
        glow.append({"pos": yup(o.matrix_world.translation), "color": lin_to_hex(o.data.color), "name": o.name})
meta["glows"] = glow

# ---------------------------------------------------------------- 3. flatten materials for glTF
for m in bpy.data.materials:
    if not m.node_tree:
        continue
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    if not b:
        continue
    bc = b.inputs["Base Color"]
    if bc.is_linked:
        src = bc.links[0].from_node
        if src.bl_idname == "ShaderNodeValToRGB":
            els = src.color_ramp.elements
            avg = [sum(e.color[i] for e in els) / len(els) for i in range(4)]
            bc.default_value = avg
        else:   # terrain paint (vertex colours) -> white base so vertex colours show
            bc.default_value = (1, 1, 1, 1)
        nt.links.remove(bc.links[0])
    for nm in ("Normal", "Emission Strength", "Roughness"):
        if nm in b.inputs and b.inputs[nm].is_linked:
            nt.links.remove(b.inputs[nm].links[0])
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = 0.0
    if b.inputs["Emission Strength"].default_value > 0:
        b.inputs["Emission Strength"].default_value = min(b.inputs["Emission Strength"].default_value, 6.0)

# ---------------------------------------------------------------- 4. select what goes into the GLB
vl = sc.view_layers[0]
asc = vl.layer_collection.children.get("ASSETS_Source")
if asc:
    asc.exclude = False
skip = re.compile(r"^(AtmosphereFog|CloudLayer\d|FlyPath|LandmarkFocus|VEG_.*|.*_Emitter|.*_Mote)$")
for o in bpy.data.objects:
    try:
        o.select_set(False)
    except RuntimeError:
        pass
for o in sc.objects:
    if o.type in ('MESH', 'EMPTY') and not skip.match(o.name):
        if o.name == "Ocean":   # replace the heavy ocean sim with a flat water plane for the web
            for md in list(o.modifiers):
                o.modifiers.remove(md)
            import bmesh
            bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=4000)
            bm.to_mesh(o.data); bm.free()
            o.location.x = o.location.y = 0
        try:
            o.select_set(True)
        except RuntimeError:
            pass
kw = dict(filepath=os.path.join(OUT, "world.glb"), export_format='GLB', use_selection=True, export_apply=True,
          export_cameras=False, export_lights=False, export_animations=False, export_extras=False,
          export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
          export_yup=True)
_win = bpy.context.window_manager.windows[0]
_area = next((a for a in _win.screen.areas if a.type == 'VIEW_3D'), _win.screen.areas[0])
_ovr = dict(window=_win, area=_area, scene=sc, view_layer=vl,
            active_object=next((o for o in sc.objects if o.select_get()), None))
for extra in ({"export_vertex_color": 'ACTIVE'}, {"export_colors": True}, {}):
    try:
        with bpy.context.temp_override(**_ovr):
            bpy.ops.export_scene.gltf(**kw, **extra)
        break
    except TypeError:
        continue
with open(os.path.join(OUT, "meta.json"), "w") as f:
    json.dump(meta, f)
_sizes = {fn: round(os.path.getsize(os.path.join(OUT, fn)) / 1e6, 2) for fn in os.listdir(OUT)}
bpy.ops.wm.revert_mainfile()
result = {"world": WID, "files_mb": _sizes, "instance_parts": len(index),
          "instances": sum(v[1] for v in index.values()), "drivers": len(drivers)}
