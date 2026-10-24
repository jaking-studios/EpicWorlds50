"""
EpicWorlds50 - Jaking Company World Pipeline (ew_core)
=====================================================
Shared procedural systems used by every world in the EpicWorlds50 project.

Systems:
  * Scene/world bootstrap (collections, render settings, metadata)
  * Procedural terrain (fractal noise heightfields + per-world shaping)
  * Terrain texture painting (slope/height-driven vertex-colour paint layers)
  * Sculpt-style detailing (stacked displacement layers on rocks & cliffs)
  * PBR procedural material library
  * Geometry Nodes vegetation scatter with viewport LOD + procedural wind
  * Water (ocean modifier), flowing rivers/waterfalls, drifting clouds
  * Ambient life: bird flocks, waving flags, floating particles, pulsing lights
  * Atmosphere: sky gradient, volumetric fog, god rays, day/night driver
  * Mega Landmark rule (>= 100 m, beacon, recorded in metadata)
  * Cinematic camera rig (hero / flythrough / aerial, 60 s, camera-bound markers)

Everything animated is driven by drivers or Geometry Nodes Scene Time, so it
loops forever and needs no baking. Written for Blender 5.x (works on 4.2+).
"""
import bpy, bmesh, math, random, os, json, time
from mathutils import Vector, noise

FPS = 24
TRAILER_FRAMES = 60 * FPS  # 60 s showcase

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def hexc(h, a=1.0):
    """'#RRGGBB' -> linear RGBA."""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple([(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [a])


def drive(owner, path, expr, index=-1):
    fc = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = expr
    return fc


def setattr_safe(obj, attr, val):
    try:
        setattr(obj, attr, val)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Scene bootstrap
# --------------------------------------------------------------------------
class World:
    def __init__(self, wid, title, category, lore, palette):
        self.t0 = time.time()
        self.id, self.title, self.category, self.lore, self.palette = wid, title, category, lore, palette
        sc = bpy.data.scenes.new(wid)
        for w in bpy.context.window_manager.windows:
            w.scene = sc
        for s in list(bpy.data.scenes):
            if s != sc:
                bpy.data.scenes.remove(s)
        bpy.data.orphans_purge(do_recursive=True)
        self.scene = sc
        self.cols = {}
        for n in ("Terrain", "MegaLandmark", "Architecture", "Vegetation", "Water",
                  "AmbientFX", "Lighting", "Cameras", "ASSETS_Source"):
            self.col(n)
        # source assets are instanced by Geometry Nodes, never rendered directly
        sc.view_layers[0].layer_collection.children["ASSETS_Source"].exclude = True
        self.landmark = None
        self.notes = []
        self._render_setup()

    def col(self, name):
        if name not in self.cols:
            c = bpy.data.collections.new(f"{self.id}_{name}" if name != "ASSETS_Source" else "ASSETS_Source")
            self.scene.collection.children.link(c)
            self.cols[name] = c
        return self.cols[name]

    def link(self, obj, colname):
        self.col(colname).objects.link(obj)
        return obj

    def _render_setup(self):
        sc = self.scene
        sc.render.engine = 'BLENDER_EEVEE'
        sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
        sc.render.fps = FPS
        sc.frame_start, sc.frame_end = 1, TRAILER_FRAMES
        sc.view_settings.view_transform = 'AgX'
        setattr_safe(sc.view_settings, 'look', 'AgX - Medium High Contrast')
        ee = sc.eevee
        for a, v in (("taa_render_samples", 64), ("use_volumetric_shadows", True),
                     ("volumetric_end", 4000.0), ("volumetric_tile_size", '8'),
                     ("use_shadows", True), ("use_raytracing", True),
                     ("volumetric_samples", 64), ("use_gtao", True)):
            setattr_safe(ee, a, v)
        sc.unit_settings.system = 'METRIC'
        sc["jaking_company"] = "EpicWorlds50 - a Jaking Company production"
        sc["day_night_speed"] = 0.0  # set > 0 (e.g. 0.004) for an animated day/night cycle

    # ---------------------------------------------------------------- finish
    def finish(self, root):
        sc = self.scene
        verts = sum(len(o.data.vertices) for o in sc.objects if o.type == 'MESH')
        meta = {
            "id": self.id, "title": self.title, "category": self.category, "lore": self.lore,
            "mega_landmark": self.landmark, "objects": len(sc.objects),
            "base_mesh_vertices": verts, "build_seconds": round(time.time() - self.t0, 2),
            "blender": bpy.app.version_string, "notes": self.notes,
            "frames": TRAILER_FRAMES, "fps": FPS,
        }
        # mark reusable sources & materials as assets for the Asset Browser
        for o in self.col("ASSETS_Source").objects:
            try:
                o.asset_mark(); o.asset_data.tags.new(self.id); o.asset_data.author = "Jaking Company"
            except Exception:
                pass
        for m in bpy.data.materials:
            if m.name.startswith("EW_"):
                try:
                    m.asset_mark(); m.asset_data.author = "Jaking Company"
                except Exception:
                    pass
        sub = "RealWorldLandmarks" if self.category == "real" else "FantasyWorlds"
        path = os.path.join(root, sub, f"{self.id}.blend")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True, relative_remap=True)
        meta["blend_file"] = f"{sub}/{self.id}.blend"
        meta["blend_mb"] = round(os.path.getsize(path) / 1e6, 2)
        os.makedirs(os.path.join(root, "Documentation", "worlds"), exist_ok=True)
        with open(os.path.join(root, "Documentation", "worlds", f"{self.id}.json"), "w") as f:
            json.dump(meta, f, indent=2)
        return meta


# --------------------------------------------------------------------------
# Materials (procedural PBR library)
# --------------------------------------------------------------------------
def _nt(m):
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if not bsdf:
        nt.nodes.clear()
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return nt, bsdf


def pbr(name, c1, c2, scale=2.0, rough=0.7, bump=0.25, metal=0.0, emit=None, emit_str=0.0,
        transmission=0.0):
    name = "EW_" + name
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt, b = _nt(m)
    N, L = nt.nodes, nt.links
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 8.0
    vr = N.new("ShaderNodeTexVoronoi"); vr.inputs["Scale"].default_value = scale * 3
    rp = N.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = hexc(c1) if isinstance(c1, str) else c1
    rp.color_ramp.elements[1].color = hexc(c2) if isinstance(c2, str) else c2
    L.new(tc.outputs["Object"], nz.inputs["Vector"]); L.new(tc.outputs["Object"], vr.inputs["Vector"])
    L.new(nz.outputs["Fac"], rp.inputs["Fac"])
    L.new(rp.outputs["Color"], b.inputs["Base Color"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump
    mx = N.new("ShaderNodeMath"); mx.operation = 'ADD'
    L.new(nz.outputs["Fac"], mx.inputs[0]); L.new(vr.outputs["Distance"], mx.inputs[1])
    L.new(mx.outputs[0], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if transmission:
        setattr_safe(b.inputs["Transmission Weight"], "default_value", transmission)
    if emit:
        b.inputs["Emission Color"].default_value = hexc(emit)
        b.inputs["Emission Strength"].default_value = emit_str
    return m


def pulse(mat, base, amp, speed=0.08, phase=0.0):
    """Animated emission (crystals, portals, beacons)."""
    b = mat.node_tree.nodes.get("Principled BSDF")
    drive(b.inputs["Emission Strength"], "default_value",
          f"{base}+{amp}*sin(frame*{speed}+{phase})")


def flowing(name, c1, c2, speed=0.03, emit=None, emit_str=0.0, rough=0.08):
    """Liquid material whose noise pattern scrolls with time (rivers, waterfalls, chocolate)."""
    name = "EW_" + name
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt, b = _nt(m)
    N, L = nt.nodes, nt.links
    tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.6
    nz.inputs["Detail"].default_value = 6
    rp = N.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = hexc(c1); rp.color_ramp.elements[1].color = hexc(c2)
    L.new(tc.outputs["Object"], mp.inputs["Vector"]); L.new(mp.outputs[0], nz.inputs["Vector"])
    L.new(nz.outputs["Fac"], rp.inputs["Fac"]); L.new(rp.outputs["Color"], b.inputs["Base Color"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.4
    L.new(nz.outputs["Fac"], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    drive(mp.inputs["Location"], "default_value", f"frame*{speed}", 1)
    if emit:
        b.inputs["Emission Color"].default_value = hexc(emit)
        b.inputs["Emission Strength"].default_value = emit_str
    return m


def terrain_material():
    """Terrain shader reads the painted 'TerrainPaint' colour layer + micro detail."""
    m = bpy.data.materials.get("EW_TerrainPainted")
    if m:
        return m
    m = bpy.data.materials.new("EW_TerrainPainted")
    nt, b = _nt(m)
    N, L = nt.nodes, nt.links
    ca = N.new("ShaderNodeVertexColor"); ca.layer_name = "TerrainPaint"
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.08; nz.inputs["Detail"].default_value = 10
    mix = N.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.blend_type = 'OVERLAY'
    mix.inputs["Factor"].default_value = 0.35
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    L.new(ca.outputs["Color"], mix.inputs[6]); L.new(nz.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35
    L.new(nz.outputs["Fac"], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.92
    return m


def water_material(deep="#0b3d5c", shallow="#2f8fa3"):
    m = flowing("Water", deep, shallow, speed=0.01, rough=0.03)
    b = m.node_tree.nodes["Principled BSDF"]
    setattr_safe(b.inputs["Coat Weight"], "default_value", 0.6)
    return m


# --------------------------------------------------------------------------
# Mesh primitives (bmesh based: no operator context needed)
# --------------------------------------------------------------------------
def _obj(name, bm, loc, mat, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = loc; o.rotation_euler = rot
    if mat:
        me.materials.append(mat)
    return o


def box(name, sx, sy, sz, loc=(0, 0, 0), mat=None, rz=0.0, bevel=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, (v.co.z + 0.5) * sz))
    o = _obj(name, bm, loc, mat, (0, 0, rz))
    if bevel:
        bv = o.modifiers.new("Bevel", 'BEVEL'); bv.width = bevel; bv.segments = 2
        setattr_safe(bv, "harden_normals", True)
    return o


def cyl(name, r1, r2, h, segs=24, loc=(0, 0, 0), mat=None, rz=0.0, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=h)
    for v in bm.verts:
        v.co.z += h / 2
    if smooth:
        for f in bm.faces:
            f.smooth = len(f.verts) == 4
    return _obj(name, bm, loc, mat, (0, 0, rz))


def sphere(name, r, loc=(0, 0, 0), mat=None, subdiv=3, squash=1.0):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    for v in bm.verts:
        v.co.z *= squash
    for f in bm.faces:
        f.smooth = True
    return _obj(name, bm, loc, mat)


def sculpt_layers(o, strength=1.0, seed=0, layers=((1.6, 0.35, 'CLOUDS'), (0.5, 0.12, 'VORONOI'))):
    """Sculpt-style detailing: subdivide then stack displacement layers (big forms -> fine cracks)."""
    sd = o.modifiers.new("Sculpt_Subdiv", 'SUBSURF'); sd.levels = 2; sd.render_levels = 3
    for i, (size, amt, kind) in enumerate(layers):
        t = bpy.data.textures.new(f"{o.name}_SculptTex{i}", kind)
        setattr_safe(t, "noise_scale", size)
        if kind == 'VORONOI':
            setattr_safe(t, "distance_metric", 'DISTANCE')
        d = o.modifiers.new(f"Sculpt_Layer{i}", 'DISPLACE')
        d.texture = t; d.strength = amt * strength; d.texture_coords = 'OBJECT'
        d.mid_level = 0.5 + 0.01 * seed
    return o


# --------------------------------------------------------------------------
# Terrain
# --------------------------------------------------------------------------
def fbm(x, y, scale=0.002, octaves=6, seed=0):
    return noise.fractal(Vector((x * scale + seed * 13.1, y * scale - seed * 7.7, seed * 0.37)),
                         1.0, 2.0, octaves, noise_basis='PERLIN_ORIGINAL')


def ridge(x, y, scale=0.002, seed=0):
    return noise.ridged_multi_fractal(Vector((x * scale + seed, y * scale, seed)), 1.0, 2.0, 6, 1.0, 2.0,
                                      noise_basis='PERLIN_ORIGINAL')


def terrain(w, size, res, height_fn, paint_fn, name="Terrain"):
    """height_fn(x,y)->z ; paint_fn(x,y,z,slope)->((r,g,b), {mask_name: 0..1}).
    Paint is written to a colour attribute (texture painting layer) and float masks
    that drive Geometry Nodes scattering."""
    n = res + 1
    verts, faces = [], []
    for j in range(n):
        for i in range(n):
            x = (i / res - 0.5) * size; y = (j / res - 0.5) * size
            verts.append((x, y, height_fn(x, y)))
    for j in range(res):
        for i in range(res):
            a = j * n + i
            faces.append((a, a + 1, a + n + 1, a + n))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update()
    try:
        me.shade_smooth()
    except Exception:
        for p in me.polygons:
            p.use_smooth = True
    col = me.color_attributes.new("TerrainPaint", 'FLOAT_COLOR', 'POINT')
    masks = {}
    for v in me.vertices:
        slope = 1.0 - max(0.0, v.normal.z)
        rgb, mk = paint_fn(v.co.x, v.co.y, v.co.z, slope)
        col.data[v.index].color = (*[c ** 2.2 for c in rgb], 1.0)  # paint in sRGB -> linear
        for k, val in mk.items():
            if k not in masks:
                masks[k] = me.attributes.new(k, 'FLOAT', 'POINT')
            masks[k].data[v.index].value = val
    o = bpy.data.objects.new(name, me)
    me.materials.append(terrain_material())
    w.link(o, "Terrain")
    w.terrain = o
    w.height_fn = height_fn
    return o


# --------------------------------------------------------------------------
# Vegetation assets + Geometry Nodes scatter (LOD + wind)
# --------------------------------------------------------------------------
def tree_assets(w, kind="broadleaf", leaf="#3f6b2a", bark="#4a3426", n=3):
    """Builds n variants of a tree type into ASSETS_Source and returns a collection of them."""
    c = bpy.data.collections.new(f"VEG_{kind}")
    w.col("ASSETS_Source").children.link(c)
    lm = pbr(f"Leaf_{kind}", leaf, "#1d3a14" if kind != "candy" else leaf, scale=6, rough=0.6, bump=0.4)
    bm_ = pbr(f"Bark_{kind}", bark, "#22160f", scale=8, rough=0.85, bump=0.6)
    rnd = random.Random(hash(kind) & 0xffff)
    for i in range(n):
        h = rnd.uniform(6, 11)
        if kind == "conifer":
            parts = [cyl(f"{kind}{i}_trunk", 0.35, 0.2, h * 0.4, 8, mat=bm_)]
            for k in range(3):
                parts.append(cyl(f"{kind}{i}_tier{k}", 2.6 - k * 0.7, 0.1, h * 0.45, 9,
                                 loc=(0, 0, h * (0.25 + k * 0.22)), mat=lm))
        elif kind == "palm":
            parts = [cyl(f"{kind}{i}_trunk", 0.3, 0.18, h, 8, mat=bm_)]
            for k in range(7):
                a = k / 7 * 6.283
                fr = box(f"{kind}{i}_frond{k}", 4.2, 0.8, 0.08, loc=(math.cos(a) * 1.9, math.sin(a) * 1.9, h - 0.6), mat=lm, rz=a)
                fr.rotation_euler.x = 0.0; fr.rotation_euler.y = 0.35
                parts.append(fr)
        elif kind == "candy":
            parts = [cyl(f"{kind}{i}_stick", 0.2, 0.2, h * 0.7, 8, mat=bm_),
                     sphere(f"{kind}{i}_pop", rnd.uniform(1.6, 2.6), loc=(0, 0, h * 0.75), mat=lm, subdiv=3, squash=0.45)]
            parts[-1].rotation_euler.x = 1.45
        elif kind == "crystal":
            parts = []
            for k in range(rnd.randint(3, 6)):
                s = cyl(f"{kind}{i}_shard{k}", rnd.uniform(0.4, 1.0), 0.0, rnd.uniform(3, 9), 6, mat=lm, smooth=False)
                s.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 6))
                parts.append(s)
        elif kind == "grass":
            parts = []
            for k in range(7):
                s = cyl(f"{kind}{i}_blade{k}", 0.05, 0.0, rnd.uniform(0.5, 1.1), 3, mat=lm, smooth=False)
                s.location = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0)
                s.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0)
                parts.append(s)
        elif kind == "shrub":
            parts = [sculpt_layers(sphere(f"{kind}{i}_bush", rnd.uniform(0.8, 1.5), loc=(0, 0, 0.6), mat=lm, subdiv=2, squash=0.7),
                                   0.6, i, ((0.8, 0.5, 'CLOUDS'),))]
        else:  # broadleaf
            parts = [cyl(f"{kind}{i}_trunk", 0.4, 0.25, h * 0.55, 8, mat=bm_)]
            for k in range(3):
                cs = sphere(f"{kind}{i}_canopy{k}", rnd.uniform(2.0, 3.0),
                            loc=(rnd.uniform(-1.2, 1.2), rnd.uniform(-1.2, 1.2), h * 0.6 + k * 0.9), mat=lm, subdiv=2, squash=0.8)
                sculpt_layers(cs, 0.8, k, ((0.9, 0.6, 'CLOUDS'),))
                parts.append(cs)
        # one sub-collection per variant -> one pickable instance per variant
        vc = bpy.data.collections.new(f"{kind}_{i}")
        c.children.link(vc)
        for p in parts:
            vc.objects.link(p)
    return c


def rock_assets(w, color="#7d7468", n=3, name="rock"):
    c = bpy.data.collections.new(f"VEG_{name}")
    w.col("ASSETS_Source").children.link(c)
    m = pbr(f"Rock_{name}", color, "#3b3631", scale=1.5, rough=0.9, bump=0.8)
    for i in range(n):
        r = sphere(f"{name}_{i}", 1.0 + i * 0.4, mat=m, subdiv=2, squash=0.6)
        sculpt_layers(r, 1.0, i)
        c.objects.link(r)
    return c


def scatter(w, name, collection, mask, density, seed=0, scale=(0.8, 1.4), wind=0.035,
            viewport_lod=0.2, align=False):
    """GN scatter on the terrain, driven by a painted mask attribute.
    LOD: viewport shows only `viewport_lod` of the instances; full density at render.
    Wind: per-instance procedural sway from Scene Time + world position."""
    ng = bpy.data.node_groups.new(f"GN_Scatter_{name}", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi = N.new("NodeGroupInput"); go = N.new("NodeGroupOutput")
    oi = N.new("GeometryNodeObjectInfo"); oi.transform_space = 'RELATIVE'
    oi.inputs["Object"].default_value = w.terrain
    na = N.new("GeometryNodeInputNamedAttribute"); na.data_type = 'FLOAT'; na.inputs["Name"].default_value = mask
    cmp = N.new("FunctionNodeCompare"); cmp.data_type = 'FLOAT'; cmp.operation = 'GREATER_THAN'
    cmp.inputs[1].default_value = 0.5
    L.new(na.outputs[0], cmp.inputs[0])
    # LOD density switch
    isv = N.new("GeometryNodeIsViewport")
    sw = N.new("GeometryNodeSwitch"); sw.input_type = 'FLOAT'
    sw.inputs[1].default_value = density; sw.inputs[2].default_value = density * viewport_lod
    L.new(isv.outputs[0], sw.inputs[0])
    dist = N.new("GeometryNodeDistributePointsOnFaces"); dist.distribute_method = 'RANDOM'
    dist.inputs["Seed"].default_value = seed
    L.new(oi.outputs["Geometry"], dist.inputs["Mesh"]); L.new(cmp.outputs[0], dist.inputs["Selection"])
    L.new(sw.outputs[0], dist.inputs["Density"])
    ci = N.new("GeometryNodeCollectionInfo"); ci.inputs["Collection"].default_value = collection
    ci.inputs["Separate Children"].default_value = True; ci.inputs["Reset Children"].default_value = True
    ci.transform_space = 'ORIGINAL'
    # random yaw + scale from white noise of position
    pos = N.new("GeometryNodeInputPosition")
    wn = N.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = '3D'
    L.new(pos.outputs[0], wn.inputs["Vector"])
    yaw = N.new("ShaderNodeMath"); yaw.operation = 'MULTIPLY'; yaw.inputs[1].default_value = 6.283
    L.new(wn.outputs["Value"], yaw.inputs[0])
    rot = N.new("ShaderNodeCombineXYZ"); L.new(yaw.outputs[0], rot.inputs["Z"])
    fr = N.new("ShaderNodeMath"); fr.operation = 'FRACT'
    m7 = N.new("ShaderNodeMath"); m7.operation = 'MULTIPLY'; m7.inputs[1].default_value = 7.13
    L.new(wn.outputs["Value"], m7.inputs[0]); L.new(m7.outputs[0], fr.inputs[0])
    sc = N.new("ShaderNodeMapRange"); sc.inputs["To Min"].default_value = scale[0]; sc.inputs["To Max"].default_value = scale[1]
    L.new(fr.outputs[0], sc.inputs["Value"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    L.new(dist.outputs["Points"], inst.inputs["Points"]); L.new(ci.outputs[0], inst.inputs["Instance"])
    inst.inputs["Pick Instance"].default_value = True
    L.new(rot.outputs[0], inst.inputs["Rotation"]); L.new(sc.outputs[0], inst.inputs["Scale"])
    last = inst
    if wind > 0:
        st = N.new("GeometryNodeInputSceneTime")
        sep = N.new("ShaderNodeSeparateXYZ"); L.new(pos.outputs[0], sep.inputs[0])
        def wave(axis_out, tspeed, phase):
            a = N.new("ShaderNodeMath"); a.operation = 'MULTIPLY_ADD'
            a.inputs[1].default_value = 0.045
            L.new(sep.outputs[axis_out], a.inputs[0])
            t = N.new("ShaderNodeMath"); t.operation = 'MULTIPLY_ADD'; t.inputs[1].default_value = tspeed
            t.inputs[2].default_value = phase
            L.new(st.outputs["Seconds"], t.inputs[0]); L.new(t.outputs[0], a.inputs[2])
            s = N.new("ShaderNodeMath"); s.operation = 'SINE'; L.new(a.outputs[0], s.inputs[0])
            k = N.new("ShaderNodeMath"); k.operation = 'MULTIPLY'; k.inputs[1].default_value = wind
            L.new(s.outputs[0], k.inputs[0])
            return k
        wx, wy = wave(0, 1.7, 0.0), wave(1, 1.3, 1.9)
        wr = N.new("ShaderNodeCombineXYZ"); L.new(wx.outputs[0], wr.inputs["X"]); L.new(wy.outputs[0], wr.inputs["Y"])
        ri = N.new("GeometryNodeRotateInstances")
        L.new(inst.outputs[0], ri.inputs["Instances"]); L.new(wr.outputs[0], ri.inputs["Rotation"])
        ri.inputs["Local Space"].default_value = True
        last = ri
    L.new(last.outputs[0], go.inputs[0])
    me = bpy.data.meshes.new(f"VEG_{name}_host")
    o = bpy.data.objects.new(f"VEG_{name}", me)
    w.link(o, "Vegetation")
    mod = o.modifiers.new("Scatter", 'NODES'); mod.node_group = ng
    return o


# --------------------------------------------------------------------------
# Water, clouds, ambient life
# --------------------------------------------------------------------------
def ocean(w, z, size=4000, deep="#0b3d5c", shallow="#2f8fa3", wave_scale=1.2):
    me = bpy.data.meshes.new("Ocean"); o = bpy.data.objects.new("Ocean", me)
    o.location = (0, 0, z); w.link(o, "Water")
    om = o.modifiers.new("Ocean", 'OCEAN')
    om.geometry_mode = 'GENERATE'; om.resolution = 7; om.size = 1.0
    om.spatial_size = 400; om.repeat_x = om.repeat_y = max(1, int(size / 400))
    om.wave_scale = wave_scale; om.choppiness = 1.0
    o.location = (-size / 2 + 100, -size / 2 + 100, z)
    drive(om, "time", f"frame/{FPS}")
    me.materials.append(water_material(deep, shallow))
    return o


def ribbon(w, name, pts, width, mat, z_off=0.3, col="Water", fall=False):
    """Mesh strip along a polyline (rivers, waterfalls, roads). If fall, pts are 3D."""
    bm = bmesh.new()
    prev = None
    for i, p in enumerate(pts):
        if fall:
            x, y, z = p
        else:
            x, y = p; z = w.height_fn(x, y) + z_off
        q = pts[min(i + 1, len(pts) - 1)] if i < len(pts) - 1 else pts[i]
        r = pts[max(i - 1, 0)]
        d = Vector((q[0] - r[0], q[1] - r[1], 0))
        d = d.normalized() if d.length > 1e-6 else Vector((0, 1, 0))  # vertical falls
        nrm = Vector((-d.y, d.x, 0)) * (width / 2)
        a = bm.verts.new((x - nrm.x, y - nrm.y, z)); b = bm.verts.new((x + nrm.x, y + nrm.y, z))
        if prev:
            bm.faces.new((prev[0], prev[1], b, a))
        prev = (a, b)
    o = _obj(name, bm, (0, 0, 0), mat)
    w.link(o, col)
    return o


def clouds(w, z=700, size=5000, color="#ffffff", speed=0.6, density=0.55):
    m = bpy.data.materials.get("EW_Clouds_" + w.id)
    if not m:
        m = bpy.data.materials.new("EW_Clouds_" + w.id)
        nt, b = _nt(m)
        N, L = nt.nodes, nt.links
        out = N.get("Material Output")
        tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping")
        nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.0025; nz.inputs["Detail"].default_value = 8
        rp = N.new("ShaderNodeValToRGB"); rp.color_ramp.elements[0].position = density
        rp.color_ramp.elements[0].color = (0, 0, 0, 1); rp.color_ramp.elements[1].position = min(0.95, density + 0.2)
        tr = N.new("ShaderNodeBsdfTransparent"); mix = N.new("ShaderNodeMixShader")
        b.inputs["Base Color"].default_value = hexc(color); b.inputs["Roughness"].default_value = 1.0
        b.inputs["Emission Color"].default_value = hexc(color); b.inputs["Emission Strength"].default_value = 0.25
        L.new(tc.outputs["Object"], mp.inputs[0]); L.new(mp.outputs[0], nz.inputs["Vector"])
        L.new(nz.outputs["Fac"], rp.inputs["Fac"]); L.new(rp.outputs["Color"], mix.inputs[0])
        L.new(tr.outputs[0], mix.inputs[1]); L.new(b.outputs[0], mix.inputs[2])
        L.new(mix.outputs[0], out.inputs["Surface"])
        drive(mp.inputs["Location"], "default_value", f"frame*{speed}", 0)
        setattr_safe(m, "surface_render_method", 'BLENDED')
        setattr_safe(m, "use_backface_culling", False)
    for i, zz in enumerate((z, z + 120)):
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
        o = _obj(f"CloudLayer{i}", bm, (i * 300, i * 200, zz), m)
        w.link(o, "AmbientFX")


def birds(w, center, count=14, radius=150, height=120, color="#1b1b1b", speed=0.006):
    m = pbr("Bird", color, color, rough=0.8, bump=0.0)
    rnd = random.Random(7)
    for i in range(count):
        piv = bpy.data.objects.new(f"BirdPivot{i}", None)
        piv.location = (center[0], center[1], center[2] + height + rnd.uniform(-25, 25))
        w.link(piv, "AmbientFX")
        drive(piv, "rotation_euler", f"frame*{speed * rnd.uniform(0.8, 1.3):.5f}+{rnd.uniform(0, 6.28):.3f}", 2)
        bm = bmesh.new()
        v = [bm.verts.new(p) for p in ((0, 0.6, 0), (-1.4, -0.2, 0.3), (0, -0.3, 0), (1.4, -0.2, 0.3))]
        bm.faces.new((v[0], v[1], v[2])); bm.faces.new((v[0], v[2], v[3]))
        b = _obj(f"Bird{i}", bm, (radius * rnd.uniform(0.7, 1.2), 0, 0), m, (0, 0, 0))
        b.parent = piv; w.link(b, "AmbientFX")
        drive(b, "scale", f"1+0.6*sin(frame*0.9+{i})", 2)  # wing flap


def flag(w, loc, color="#b01e23", size=(6, 4), pole_h=14):
    pm = pbr("FlagPole", "#9a9a9a", "#5d5d5d", metal=0.9, rough=0.3)
    pole = cyl("FlagPole", 0.12, 0.1, pole_h, 8, loc=loc, mat=pm); w.link(pole, "AmbientFX")
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=24, y_segments=12, size=0.5)
    for v in bm.verts:
        v.co = Vector(((v.co.x + 0.5) * size[0], 0, (v.co.y + 0.5) * size[1]))
    fm = pbr("Flag_" + color.strip('#'), color, color, rough=0.8, bump=0.0)
    f = _obj("Flag", bm, (loc[0] + 0.1, loc[1], loc[2] + pole_h - size[1]), fm)
    wv = f.modifiers.new("Wind", 'WAVE')
    wv.use_normal = False; wv.use_y = False; wv.height = 0.35; wv.width = 1.6; wv.speed = 0.12
    wv.start_position_x = -1; wv.use_cyclic = True
    vg = f.vertex_groups.new(name="free")
    for v in f.data.vertices:
        vg.add([v.index], min(1.0, v.co.x / size[0] * 1.5), 'REPLACE')
    wv.vertex_group = "free"
    w.link(f, "AmbientFX")


def floating_particles(w, center, size=600, z=40, count=1500, color="#fff2c4", strength=4.0, name="Dust"):
    pm = pbr("Particle_" + name, color, color, emit=color, emit_str=strength, bump=0)
    src = sphere(f"{name}_Mote", 0.15, mat=pm, subdiv=1)
    w.link(src, "ASSETS_Source")
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    em = _obj(f"{name}_Emitter", bm, (center[0], center[1], z), None)
    w.link(em, "AmbientFX")
    ps = em.modifiers.new(name, 'PARTICLE_SYSTEM').particle_system
    s = ps.settings
    s.count = count; s.frame_start = -400; s.frame_end = TRAILER_FRAMES; s.lifetime = 900
    s.normal_factor = 0.4; s.brownian_factor = 0.4; s.effector_weights.gravity = 0.0
    s.render_type = 'OBJECT'; s.instance_object = src; s.particle_size = 1.0; s.size_random = 0.6
    em.show_instancer_for_render = False
    return em


def floating(o, amp=4.0, speed=0.02, phase=0.0, spin=0.0):
    """Hovering motion for islands, rocks, lanterns, castles."""
    base = o.location.z
    drive(o, "location", f"{base}+{amp}*sin(frame*{speed}+{phase})", 2)
    if spin:
        drive(o, "rotation_euler", f"frame*{spin}", 2)


# --------------------------------------------------------------------------
# Atmosphere & lighting
# --------------------------------------------------------------------------
def atmosphere(w, horizon="#c9dcef", zenith="#3b6fb5", fog="#d8e4f0", fog_density=0.00035,
               sun_rot=(math.radians(55), 0, math.radians(35)), sun_color="#fff1db", sun_power=4.5,
               anisotropy=0.6):
    wd = bpy.data.worlds.new(f"WORLD_{w.id}")
    w.scene.world = wd
    try:
        wd.use_nodes = True
    except Exception:
        pass
    nt = wd.node_tree; N, L = nt.nodes, nt.links
    N.clear()
    out = N.new("ShaderNodeOutputWorld")
    tc = N.new("ShaderNodeTexCoord"); sep = N.new("ShaderNodeSeparateXYZ")
    rp = N.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = hexc(horizon); rp.color_ramp.elements[1].color = hexc(zenith)
    rp.color_ramp.elements[1].position = 0.6
    bg = N.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 1.0
    L.new(tc.outputs["Generated"], sep.inputs[0]); L.new(sep.outputs["Z"], rp.inputs["Fac"])
    L.new(rp.outputs["Color"], bg.inputs["Color"]); L.new(bg.outputs[0], out.inputs["Surface"])
    fog_volume(w, fog, fog_density, anisotropy)
    sd = bpy.data.lights.new("Sun", 'SUN'); sd.energy = sun_power; sd.color = hexc(sun_color)[:3]
    sd.angle = math.radians(1.2)
    setattr_safe(sd, "volume_factor", 1.0)
    sun = bpy.data.objects.new("Sun", sd); sun.rotation_euler = sun_rot
    w.link(sun, "Lighting")
    # Day/night: rotation advances with scene['day_night_speed'] (0 = static)
    fc = sun.driver_add("rotation_euler", 0)
    var = fc.driver.variables.new(); var.name = "spd"; var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'SCENE'; var.targets[0].id = w.scene; var.targets[0].data_path = '["day_night_speed"]'
    fc.driver.expression = f"{sun_rot[0]:.4f}+spd*frame"
    w.sun = sun
    return sun


def god_light(w, loc, color="#ffd9a0", power=2e6, radius=6):
    ld = bpy.data.lights.new("Glow", 'POINT'); ld.energy = power; ld.color = hexc(color)[:3]
    ld.shadow_soft_size = radius
    o = bpy.data.objects.new("Glow", ld); o.location = loc
    w.link(o, "Lighting")
    return o


# --------------------------------------------------------------------------
# Mega Landmark rule + cameras
# --------------------------------------------------------------------------
def mega_landmark(w, name, height, top, beacon_color="#ffd27a"):
    """Every world must have one landmark >= 100 m visible from most of the map."""
    assert height >= 100, f"Mega Landmark {name} is {height} m (< 100 m rule)"
    w.landmark = {"name": name, "height_m": round(height, 1), "top": [round(c, 1) for c in top]}
    ld = bpy.data.lights.new("LandmarkBeacon", 'POINT'); ld.energy = 3e5; ld.color = hexc(beacon_color)[:3]
    b = bpy.data.objects.new("LandmarkBeacon", ld); b.location = Vector(top) + Vector((0, 0, 4))
    w.link(b, "MegaLandmark")
    drive(ld, "energy", "300000+150000*sin(frame*0.05)")
    focus = bpy.data.objects.new("LandmarkFocus", None)
    focus.location = (top[0], top[1], top[2] * 0.55)
    w.link(focus, "Cameras")
    w.focus = focus
    return b


def camera_rig(w, radius=600, height=220, hero=None, aerial=None, lens=28):
    sc = w.scene
    f = w.focus
    def cam(name, loc, lens_):
        cd = bpy.data.cameras.new(name); cd.lens = lens_; cd.clip_end = 20000
        cd.dof.use_dof = True; cd.dof.focus_object = f; cd.dof.aperture_fstop = 11
        c = bpy.data.objects.new(name, cd); c.location = loc
        t = c.constraints.new('TRACK_TO'); t.target = f; t.track_axis = 'TRACK_NEGATIVE_Z'; t.up_axis = 'UP_Y'
        w.link(c, "Cameras")
        return c
    # flythrough: orbit path, drone-style
    cu = bpy.data.curves.new("FlyPath", 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('NURBS'); pts = 12
    sp.points.add(pts - 1)
    for i in range(pts):
        a = i / pts * 6.283
        r = radius * (1.0 + 0.25 * math.sin(a * 2))
        sp.points[i].co = (f.location.x + math.cos(a) * r, f.location.y + math.sin(a) * r,
                           height * (0.7 + 0.5 * math.sin(a * 3) ** 2), 1)
    sp.use_cyclic_u = True; sp.order_u = 4
    path = bpy.data.objects.new("FlyPath", cu); w.link(path, "Cameras")
    fly = cam("CAM_Flythrough", (0, 0, 0), lens)
    fp = fly.constraints.new('FOLLOW_PATH'); fp.target = path; fp.use_fixed_location = True
    fly.constraints.move(1, 0)
    drive(fp, "offset_factor", f"frame/{TRAILER_FRAMES * 1.05}")
    hero = hero or (f.location.x + radius * 0.35, f.location.y - radius * 0.45, 4)
    aerial = aerial or (f.location.x - radius * 1.1, f.location.y + radius * 0.9, height * 2.4)
    h = cam("CAM_HeroReveal", hero, 20)
    drive(h, "location", f"{hero[2]}+frame*0.06", 2)  # slow crane-up reveal
    a = cam("CAM_Aerial", aerial, 35)
    sc.camera = h
    for fr, c in ((1, h), (int(TRAILER_FRAMES * 0.2), fly), (int(TRAILER_FRAMES * 0.85), a)):
        mk = sc.timeline_markers.new(c.name, frame=fr); mk.camera = c
    return {"hero": h, "fly": fly, "aerial": a}


def preview_render(w, root, cam_name, res=(1280, 720), frame=None):
    sc = w.scene
    sc.camera = bpy.data.objects[cam_name]
    rx, ry = sc.render.resolution_x, sc.render.resolution_y
    sc.render.resolution_x, sc.render.resolution_y = res
    if frame:
        sc.frame_set(frame)
    out = os.path.join(root, "Renders", f"{w.id}_{cam_name.replace('CAM_', '').lower()}.png")
    sc.render.filepath = out
    sc.render.image_settings.file_format = 'PNG'
    t = time.time()
    bpy.ops.render.render(write_still=True)
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.frame_set(1)
    return out, round(time.time() - t, 2)


def fog_volume(w, color, density, anisotropy=0.6, size=9000, top=1400):
    """Bounded atmospheric fog (EEVEE treats World volumes as infinite, which hides the sky)."""
    m = bpy.data.materials.new("EW_Fog_" + w.id)
    nt, b = _nt(m)
    N, L = nt.nodes, nt.links
    out = N.get("Material Output")
    N.remove(b)
    vs = N.new("ShaderNodeVolumePrincipled")
    vs.inputs["Color"].default_value = hexc(color); vs.inputs["Density"].default_value = density
    vs.inputs["Anisotropy"].default_value = anisotropy
    # thicker near the ground, thinning with altitude
    tc = N.new("ShaderNodeTexCoord"); sep = N.new("ShaderNodeSeparateXYZ")
    mr = N.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 1.0; mr.inputs["To Min"].default_value = density * 1.2
    mr.inputs["To Max"].default_value = density * 0.05
    L.new(tc.outputs["Generated"], sep.inputs[0]); L.new(sep.outputs["Z"], mr.inputs["Value"])
    L.new(mr.outputs[0], vs.inputs["Density"])
    L.new(vs.outputs[0], out.inputs["Volume"])
    o = box("AtmosphereFog", size, size, top + 200, (0, 0, -200), m)
    o.display_type = 'BOUNDS'
    w.link(o, "AmbientFX")
    return o
