"""RW01 - Giza Plateau (Real-World Wonder). Mega Landmark: Great Pyramid of Khufu, 139 m."""
import math, random, bpy, bmesh
from mathutils import Vector
import ew_core as ew

ID, TITLE = "RW01_GizaPlateau", "Giza Plateau - The Great Pyramids"
LORE = ("Late afternoon on the Giza plateau: the three great pyramids rise over a sea of dunes, "
        "the Sphinx guards the causeway, and the Nile valley glows green on the eastern horizon.")


def height(x, y):
    dunes = 10 * ew.fbm(x, y, 0.0012, 5, 1) + 5 * abs(ew.fbm(x, y, 0.004, 3, 2))
    r = math.hypot(x + 250, y + 250)
    plateau = max(0.0, min(1.0, (r - 900) / 600))          # flatten the building plateau
    z = dunes * plateau
    nile = math.exp(-((x - 2200 - 120 * math.sin(y * 0.0015)) / 260) ** 2)  # Nile valley
    return z * (1 - nile) - 7 * nile


def paint(x, y, z, slope):
    n = ew.fbm(x, y, 0.01, 3, 4)
    sand = (0.78 + 0.08 * n, 0.62 + 0.06 * n, 0.40 + 0.04 * n)
    nile = math.exp(-((x - 2200 - 120 * math.sin(y * 0.0015)) / 420) ** 2)
    if slope > 0.35:
        return (0.55, 0.45, 0.33), {"m_rock": 1.0, "m_palm": 0.0, "m_grass": 0.0}
    if nile > 0.35 and z > -5.5:
        return (0.22 + 0.05 * n, 0.36 + 0.06 * n, 0.12), {"m_palm": 1.0 if n > -0.05 else 0.0, "m_grass": 1.0, "m_rock": 0.0}
    return sand, {"m_palm": 0.0, "m_grass": 0.0, "m_rock": 1.0 if n > 0.42 else 0.0}


def stone_blocks(name, c1, c2, brick=(3.0, 1.2)):
    m = bpy.data.materials.get("EW_" + name)
    if m:
        return m
    m = ew.pbr(name, c1, c2, scale=0.4, rough=0.85, bump=0.3)
    nt = m.node_tree; N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]
    br = N.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = brick[0]; br.inputs["Row Height"].default_value = brick[1]
    br.inputs["Mortar Size"].default_value = 0.04
    tc = [n for n in N if n.bl_idname == "ShaderNodeTexCoord"][0]
    L.new(tc.outputs["Object"], br.inputs["Vector"])
    bp = [n for n in N if n.bl_idname == "ShaderNodeBump"][0]
    mx = N.new("ShaderNodeMath"); mx.operation = 'MULTIPLY'
    L.new(br.outputs["Fac"], mx.inputs[0]); mx.inputs[1].default_value = 1.0
    L.new(mx.outputs[0], bp.inputs["Height"])
    bp.inputs["Strength"].default_value = 0.6
    return m


def pyramid(w, name, base, h, loc, mat, cap_mat=None, cap_frac=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=base / math.sqrt(2), radius2=0, depth=h)
    for v in bm.verts:
        v.co.z += h / 2
    o = ew._obj(name, bm, loc, mat, (0, 0, math.radians(45)))
    w.link(o, "MegaLandmark" if name == "GreatPyramid_Khufu" else "Architecture")
    if cap_mat and cap_frac:   # Khafre keeps a patch of original white casing at the top
        bm = bmesh.new()
        hh = h * cap_frac
        bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=base / math.sqrt(2) * cap_frac * 1.004, radius2=0, depth=hh)
        for v in bm.verts:
            v.co.z += hh / 2
        c = ew._obj(name + "_Casing", bm, (loc[0], loc[1], loc[2] + h - hh + 0.2), cap_mat, (0, 0, math.radians(45)))
        w.link(c, "Architecture")
    return o


def build(root):
    w = ew.World(ID, TITLE, "real", LORE, ["#d9b27a", "#9c7a4f", "#2f6b8a", "#f2dcb3"])
    ew.terrain(w, 6000, 220, height, paint)
    lime = stone_blocks("Limestone", "#cfb48a", "#9e835e")
    casing = ew.pbr("Casing", "#efe6d2", "#d8cbb0", scale=3, rough=0.5, bump=0.05)
    granite = ew.pbr("Granite", "#5a4f4c", "#2b2525", scale=6, rough=0.35, bump=0.1)
    sand_stone = ew.pbr("Sandstone", "#c9a777", "#8a6d48", scale=2, rough=0.9, bump=0.5)
    road = ew.pbr("Causeway", "#b89a6c", "#8d744f", scale=1.2, rough=0.95, bump=0.3)

    gz = lambda x, y: height(x, y) - 1.5
    # --- Mega Landmark + pyramids (real proportions) --------------------------------
    gp = pyramid(w, "GreatPyramid_Khufu", 230.3, 138.5, (0, 0, gz(0, 0)), lime)
    pyramid(w, "Pyramid_Khafre", 215.3, 136.4, (-330, -380, gz(-330, -380) + 10), lime, casing, 0.18)
    pyramid(w, "Pyramid_Menkaure", 104.6, 65.5, (-560, -760, gz(-560, -760)), sand_stone)
    for i, (x, y) in enumerate(((150, -60), (150, 0), (150, 60), (-470, -870), (-430, -870), (-390, -870))):
        pyramid(w, f"QueensPyramid_{i}", 45 if i < 3 else 30, 29 if i < 3 else 20, (x, y, gz(x, y)), lime)
    ew.mega_landmark(w, "Great Pyramid of Khufu", 138.5, (0, 0, gz(0, 0) + 138.5), "#ffcf7a")

    # --- Interior: Grand Gallery + King's Chamber (hollow room with its own camera) -
    kz = gz(0, 0) + 43
    shell = []
    for nm, sx, sy, sz, loc in (("KC_Floor", 10.5, 5.2, 0.4, (0, 0, kz)), ("KC_Ceiling", 10.5, 5.2, 0.6, (0, 0, kz + 5.8)),
                                ("KC_WallN", 10.5, 0.4, 5.8, (0, 2.6, kz)), ("KC_WallS", 10.5, 0.4, 5.8, (0, -2.6, kz)),
                                ("KC_WallE", 0.4, 5.2, 5.8, (5.25, 0, kz)), ("KC_WallW", 0.4, 5.2, 5.8, (-5.25, 0, kz))):
        shell.append(w.link(ew.box(nm, sx, sy, sz, loc, granite), "Architecture"))
    w.link(ew.box("KC_Sarcophagus", 2.3, 1.0, 1.05, (-3.5, 0, kz + 0.4), granite, bevel=0.03), "Architecture")
    gal = ew.box("GrandGallery", 2.1, 47, 8.6, (0, -28, kz - 22), lime)
    gal.rotation_euler.x = math.radians(26); w.link(gal, "Architecture")
    for i in range(4):
        lt = ew.god_light(w, (-4 + i * 2.6, 0, kz + 4.6), "#ff9e4a", 120, 0.4)
        lt.name = f"KC_Torch{i}"
        ew.drive(lt.data, "energy", f"110+30*sin(frame*0.6+{i*1.7})")   # flickering torches
    cd = bpy.data.cameras.new("CAM_Interior_KingsChamber"); cd.lens = 16
    ic = bpy.data.objects.new("CAM_Interior_KingsChamber", cd)
    ic.location = (4.6, -2.0, kz + 1.8); ic.rotation_euler = (math.radians(85), 0, math.radians(68))
    w.link(ic, "Cameras")

    # --- Great Sphinx ---------------------------------------------------------------
    sx0, sy0 = 260, -420; sz0 = gz(sx0, sy0)
    for nm, sx, sy, sz, lx, ly, lz in (("Sphinx_Body", 16, 57, 15, 0, 0, 0), ("Sphinx_Chest", 18, 12, 18, 0, 26, 0),
                                       ("Sphinx_PawL", 4.5, 15, 4, -5.5, 37, 0), ("Sphinx_PawR", 4.5, 15, 4, 5.5, 37, 0),
                                       ("Sphinx_Neck", 8, 7, 6, 0, 28, 17), ("Sphinx_Head", 8.5, 9, 8.5, 0, 29, 21.5),
                                       ("Sphinx_Nemes", 13, 5, 9, 0, 26.5, 15.5)):
        o = ew.box(nm, sx, sy, sz, (sx0 + lx, sy0 + ly, sz0 + lz), sand_stone, bevel=0.6)
        ew.sculpt_layers(o, 0.4, 1, ((3.0, 0.5, 'CLOUDS'), (0.8, 0.2, 'VORONOI')))
        w.link(o, "Architecture")

    # --- Mastaba cemetery (modular, procedural) ------------------------------------
    rnd = random.Random(3)
    for gx in range(8):
        for gy in range(6):
            x, y = -340 + gx * 28, -60 + gy * 25 + 130
            if rnd.random() < 0.85:
                o = ew.box(f"Mastaba_{gx}_{gy}", 20, 10, rnd.uniform(4, 7), (x, y, gz(x, y)), lime, bevel=0.3)
                w.link(o, "Architecture")
    for gx in range(6):
        for gy in range(4):
            x, y = 170 + gx * 26, 120 + gy * 24
            w.link(ew.box(f"MastabaE_{gx}_{gy}", 18, 9, rnd.uniform(3.5, 6), (x, y, gz(x, y)), sand_stone, bevel=0.3), "Architecture")

    # --- Temples + causeway (procedural road) --------------------------------------
    w.link(ew.box("ValleyTemple", 45, 45, 12, (300, -500, gz(300, -500)), granite, bevel=0.2), "Architecture")
    w.link(ew.box("MortuaryTemple_Khafre", 110, 50, 10, (-180, -380, gz(-180, -380)), lime, bevel=0.2), "Architecture")
    cw = [(-200 + t * 480, -380 - t * 120) for t in [i / 30 for i in range(31)]]
    ew.ribbon(w, "Causeway_Khafre", cw, 9, road, 0.6, col="Architecture")
    ew.ribbon(w, "DesertTrack", [(-1500 + i * 80, -900 + 120 * math.sin(i * 0.3)) for i in range(45)], 6, road, 0.2, col="Architecture")

    # --- Nile + vegetation ---------------------------------------------------------
    river = [(2200 + 120 * math.sin(y * 0.0015), y) for y in range(-3000, 3001, 60)]
    ew.ribbon(w, "Nile", [(x, y) for x, y in river], 320, ew.water_material("#1d4f5e", "#4b8c8c"), -6.5 + 7.6)
    palms = ew.tree_assets(w, "palm", "#4f7a2c", "#6b5236", 3)
    grass = ew.tree_assets(w, "grass", "#5c8a2e", "#3e5b22", 2)
    rocks = ew.rock_assets(w, "#a88d66", 3, "desert_rock")
    ew.scatter(w, "Palms", palms, "m_palm", 0.0012, 1, (0.8, 1.3), wind=0.05)
    ew.scatter(w, "Fields", grass, "m_grass", 0.02, 2, (0.8, 1.6), wind=0.12, viewport_lod=0.1)
    ew.scatter(w, "DesertRocks", rocks, "m_rock", 0.0004, 3, (0.6, 2.5), wind=0.0)

    # --- Ambient life --------------------------------------------------------------
    ew.atmosphere(w, "#f3d9b0", "#5a8dc4", "#f0d4a8", 0.00009,
                  (math.radians(68), 0, math.radians(-120)), "#ffd8a8", 5.0)
    ew.clouds(w, 900, 9000, "#fff4e6", 0.4, 0.62)
    ew.birds(w, (1900, 0, 0), 16, 220, 90)
    ew.birds(w, (0, 0, 0), 8, 120, 175, speed=0.004)
    ew.floating_particles(w, (0, -200, 0), 900, 6, 2500, "#f5deb3", 1.5, "SandDust")
    camp_z = gz(700, -900)
    tent = ew.pbr("TentCanvas", "#e9dfc9", "#b8ab8f", scale=4, rough=0.9, bump=0.1)
    for i in range(5):
        t = ew.cyl(f"ExpeditionTent{i}", 3.2, 0.2, 3.5, 4, (700 + i * 9, -900, camp_z), tent, rz=0.785, smooth=False)
        w.link(t, "Architecture")
    ew.flag(w, (690, -905, camp_z), "#c8342b")
    ew.flag(w, (740, -905, camp_z), "#2b4fa0")

    ew.camera_rig(w, radius=900, height=260, hero=(560, -260, gz(560, -260) + 6), lens=26)
    w.notes += ["Interior: King's Chamber + Grand Gallery (CAM_Interior_KingsChamber)",
                "Real dimensions: Khufu 230.3 m base / 138.5 m, Khafre 215.3/136.4, Menkaure 104.6/65.5"]
    return w
