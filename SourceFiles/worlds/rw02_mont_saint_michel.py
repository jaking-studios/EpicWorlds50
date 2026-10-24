"""RW02 - Mont-Saint-Michel (Real-World Wonder). Mega Landmark: abbey spire, ~170 m above the bay."""
import math, random, bpy
import ew_core as ew

ID, TITLE = "RW02_MontSaintMichel", "Mont-Saint-Michel - The Tidal Abbey"
LORE = ("A granite island crowned by a Gothic abbey rises out of the tidal flats of Normandy. "
        "Ramparts wrap a medieval village that spirals up to the church, and the spire's golden "
        "archangel can be seen from every corner of the bay.")


def height(x, y):
    r = math.hypot(x, y)
    island = 80 * max(0.0, 1 - (r / 170) ** 1.6)
    flats = 1.2 * ew.fbm(x, y, 0.002, 4, 3) - 0.6
    coast = max(0.0, (y - 1600) / 400) * 14 + 3 * ew.fbm(x, y, 0.004, 4, 5) * max(0.0, (y - 1500) / 400)
    return max(island, flats) + coast if r < 200 else flats + coast


def paint(x, y, z, slope):
    n = ew.fbm(x, y, 0.02, 3, 1)
    if slope > 0.3:
        return (0.42, 0.40, 0.38), {"m_tree": 0.0, "m_grass": 0.0, "m_rock": 1.0}
    if y > 1650:
        return (0.30 + 0.05 * n, 0.45 + 0.05 * n, 0.20), {"m_tree": 1.0 if n > 0.1 else 0.0, "m_grass": 1.0, "m_rock": 0.0}
    if z > 6:
        return (0.35, 0.44, 0.25), {"m_tree": 1.0 if n > 0.2 else 0.0, "m_grass": 1.0, "m_rock": 0.0}
    return (0.62 + 0.05 * n, 0.58 + 0.05 * n, 0.50), {"m_tree": 0.0, "m_grass": 0.0, "m_rock": 0.0}


def build(root):
    w = ew.World(ID, TITLE, "real", LORE, ["#7c8c99", "#c9bfa8", "#3d5a6c", "#d8b25a"])
    ew.terrain(w, 6000, 200, height, paint)
    gran = ew.pbr("Granite_MSM", "#8b8478", "#5d574e", scale=1.5, rough=0.85, bump=0.5)
    wall = ew.pbr("AbbeyStone", "#b3aa96", "#8a8170", scale=3, rough=0.8, bump=0.35)
    slate = ew.pbr("Slate", "#3c4249", "#262a2f", scale=10, rough=0.55, bump=0.2)
    gold = ew.pbr("Gold", "#e8b64c", "#b9862b", rough=0.25, metal=1.0, bump=0.05)
    road = ew.pbr("Causeway_MSM", "#7d7a73", "#5a5852", scale=2, rough=0.9)
    rnd = random.Random(11)

    # ramparts ring + towers
    for i in range(28):
        a = i / 28 * 6.283
        if 3.8 < a < 5.2:
            continue
        r = 175
        x, y = math.cos(a) * r, math.sin(a) * r
        w.link(ew.box(f"Rampart_{i}", 42, 4, 12, (x, y, 0), wall, rz=a + 1.5708, bevel=0.2), "Architecture")
        if i % 4 == 0:
            w.link(ew.cyl(f"RampartTower_{i}", 7, 7, 20, 16, (x, y, 0), wall), "Architecture")
            w.link(ew.cyl(f"RampartTowerRoof_{i}", 7.6, 0.5, 8, 16, (x, y, 20), slate), "Architecture")
    # spiral village (Grande Rue) - modular houses climbing the rock
    for i in range(110):
        t = i / 110
        a = 3.6 + t * 4.2
        r = 150 - t * 95 + rnd.uniform(-8, 8)
        x, y = math.cos(a) * r, math.sin(a) * r
        z = height(x, y) - 1
        hh = rnd.uniform(9, 15)
        w.link(ew.box(f"House_{i}", rnd.uniform(7, 11), rnd.uniform(6, 9), hh, (x, y, z), wall, rz=a, bevel=0.15), "Architecture")
        roof = ew.cyl(f"HouseRoof_{i}", 6.2, 0.2, 5, 4, (x, y, z + hh), slate, rz=a + 0.785, smooth=False)
        w.link(roof, "Architecture")
    # abbey on the summit
    top = height(0, 0)
    w.link(ew.box("Abbey_Merveille", 70, 28, 40, (-10, 20, top - 22), wall, bevel=0.3), "Architecture")
    w.link(ew.box("Abbey_Nave", 64, 18, 26, (0, -5, top), wall, bevel=0.2), "Architecture")
    w.link(ew.box("Abbey_NaveRoof", 64, 19, 1, (0, -5, top + 26), slate), "Architecture")
    w.link(ew.box("Abbey_Choir", 26, 26, 30, (36, -5, top), wall, bevel=0.2), "Architecture")
    for k in range(8):   # flying buttresses
        w.link(ew.box(f"Buttress_{k}", 2, 6, 22, (-26 + k * 7.5, -16, top), wall), "Architecture")
        w.link(ew.box(f"ButtressS_{k}", 2, 6, 22, (-26 + k * 7.5, 6, top), wall), "Architecture")
    tower = ew.box("Abbey_BellTower", 14, 14, 32, (12, -5, top + 20), wall, bevel=0.2)
    w.link(tower, "MegaLandmark")
    spire = ew.cyl("Abbey_Spire", 7.5, 0.4, 40, 8, (12, -5, top + 52), slate, smooth=False)
    w.link(spire, "MegaLandmark")
    angel = ew.cyl("Archangel_Gilded", 0.9, 0.3, 5, 8, (12, -5, top + 92), gold)
    w.link(angel, "MegaLandmark")
    ew.mega_landmark(w, "Abbey spire & golden archangel", top + 97, (12, -5, top + 97), "#ffd36b")
    # interior: abbey nave hall with columns + candle light
    for k in range(10):
        w.link(ew.cyl(f"NaveColumn_{k}", 0.9, 0.8, 18, 12, (-26 + (k // 2) * 12, -10 + (k % 2) * 10, top + 0.5), wall), "Architecture")
    for k in range(5):
        c = ew.god_light(w, (-24 + k * 12, -5, top + 6), "#ffb062", 400, 0.5); c.name = f"Nave_Candles{k}"
        ew.drive(c.data, "energy", f"380+60*sin(frame*0.7+{k})")
    cd = bpy.data.cameras.new("CAM_Interior_Nave"); cd.lens = 18
    ic = bpy.data.objects.new("CAM_Interior_Nave", cd); ic.location = (28, -5, top + 5)
    ic.rotation_euler = (math.radians(88), 0, math.radians(90)); w.link(ic, "Cameras")

    # causeway bridge to the mainland, tidal water, vegetation
    ew.ribbon(w, "Causeway_Bridge", [(0, 170 + i * 50) for i in range(32)], 10, road, 2.5, col="Architecture")
    for i in range(30):
        w.link(ew.cyl(f"BridgePier_{i}", 1.2, 1.2, 3, 8, (0, 190 + i * 50, -1)), "Architecture")
    ew.ocean(w, 0.35, 6000, "#3a5866", "#7a9a9c", 0.6)
    trees = ew.tree_assets(w, "broadleaf", "#3f6427", "#4a3426", 3)
    grass = ew.tree_assets(w, "grass", "#5b7f34", "#3f5a24", 2)
    ew.scatter(w, "Trees", trees, "m_tree", 0.004, 4, (0.8, 1.5), wind=0.04)
    ew.scatter(w, "Grass", grass, "m_grass", 0.03, 5, (0.8, 1.5), wind=0.14, viewport_lod=0.08)
    ew.scatter(w, "Rocks", ew.rock_assets(w, "#77726a", 3), "m_rock", 0.004, 6, (0.5, 2.0), wind=0)

    ew.atmosphere(w, "#d9dee3", "#6f8fae", "#dfe4e8", 0.00008, (math.radians(62), 0, math.radians(140)), "#fff0d8", 4.0)
    ew.clouds(w, 650, 9000, "#ffffff", 0.7, 0.5)
    ew.birds(w, (0, 0, 0), 20, 220, 130, "#f2f2f2", 0.007)   # seagulls
    ew.flag(w, (40, -5, top + 30), "#2a4ea3", (4, 2.6), 9)
    ew.floating_particles(w, (0, 0, 0), 1200, 2, 1800, "#ffffff", 0.6, "SeaSpray")
    ew.camera_rig(w, radius=650, height=180, hero=(260, 520, 3), lens=30)
    w.notes += ["Interior: abbey nave with columns and candles (CAM_Interior_Nave)",
                "Rampart gap faces the causeway; 110 procedural village houses spiral the rock"]
    return w
