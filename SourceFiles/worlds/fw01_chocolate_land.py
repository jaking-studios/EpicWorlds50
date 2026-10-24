"""FW01 - Chocolate Land (Fantasy). Mega Landmark: the Cocoa Volcano, 420 m."""
import math, random, bpy
import ew_core as ew

ID, TITLE = "FW01_ChocolateLand", "Chocolate Land - Realm of the Cocoa Volcano"
LORE = ("Long ago a falling star of pure cocoa struck the Sugar Plains. Its crater became the Cocoa "
        "Volcano, which still pours molten chocolate rivers through wafer forests and gingerbread "
        "villages. Candy-cane pillars mark the old Sugar Road; hidden inside the volcano's flank is "
        "the Truffle Vault, where the first recipe is said to be kept.")
VX, VY = 0, 600


def height(x, y):
    r = math.hypot(x - VX, y - VY)
    cone = 420 * max(0.0, 1 - r / 900) ** 1.3
    crater = -90 * max(0.0, 1 - r / 120)
    hills = 30 * ew.fbm(x, y, 0.0012, 5, 9) + 12 * abs(ew.fbm(x, y, 0.004, 3, 2))
    river = 10 * math.exp(-((x - 260 * math.sin(y * 0.0016) - 200) / 60) ** 2) * (1 if y < 200 else 0)
    return cone + crater + hills - river


def paint(x, y, z, slope):
    n = ew.fbm(x, y, 0.01, 3, 4)
    if z > 150:
        return (0.25, 0.13, 0.07), {"m_candy": 0.0, "m_cane": 0.0}
    if slope > 0.3:
        return (0.38 + 0.05 * n, 0.22, 0.12), {"m_candy": 0.0, "m_cane": 0.0}
    pink = n > 0.25
    col = (0.95, 0.70, 0.78) if pink else (0.86 + 0.05 * n, 0.70, 0.48)
    return col, {"m_candy": 1.0 if n > -0.1 else 0.0, "m_cane": 1.0 if n > 0.45 else 0.0}


def build(root):
    w = ew.World(ID, TITLE, "fantasy", LORE, ["#5a2e1a", "#f4a6c0", "#fff1d6", "#ff7a3c"])
    ew.terrain(w, 6000, 220, height, paint)
    choc = ew.flowing("MoltenChocolate", "#3b1a0c", "#6b3518", speed=0.05, emit="#ff7a2e", emit_str=0.0, rough=0.15)
    caramel = ew.flowing("CaramelLava", "#c46a1b", "#ffb347", speed=0.08, emit="#ff8a2a", emit_str=6.0, rough=0.2)
    ew.pulse(caramel, 6, 3, 0.05)
    ginger = ew.pbr("Gingerbread", "#a0602e", "#6b3a17", scale=4, rough=0.9, bump=0.5)
    icing = ew.pbr("Icing", "#fff8f0", "#f3e6e6", scale=8, rough=0.4, bump=0.1)
    mint = ew.pbr("Mint", "#9ff2d0", "#57c9a0", scale=4, rough=0.3)
    cherry = ew.pbr("CandyRed", "#e8243c", "#ff6b81", scale=3, rough=0.15)
    marsh = ew.pbr("Marshmallow", "#fff6fb", "#ffd9ea", scale=2, rough=0.8, bump=0.15)
    rnd = random.Random(5)

    # Mega Landmark: Cocoa Volcano (terrain) + glowing crater caldera + eruption light
    top = height(VX, VY + 160)
    ew.mega_landmark(w, "Cocoa Volcano", 420, (VX, VY, 420), "#ff8a3a")
    pool = ew.cyl("Crater_CaramelPool", 115, 115, 1, 48, (VX, VY, height(VX, VY) + 6), caramel)
    w.link(pool, "MegaLandmark")
    ew.god_light(w, (VX, VY, 360), "#ff7a2a", 4e6, 40).name = "VolcanoGlow"
    ew.drive(bpy.data.objects["VolcanoGlow"].data, "energy", "4000000+2000000*sin(frame*0.04)")
    # chocolate rivers from the crater rim down the slopes
    for k, ang in enumerate((-1.9, -1.3, 2.4)):
        pts = []
        for i in range(60):
            t = i / 59
            r = 130 + t * 1900
            a = ang + 0.35 * math.sin(t * 6 + k)
            pts.append((VX + math.cos(a) * r, VY + math.sin(a) * r))
        ew.ribbon(w, f"ChocolateRiver_{k}", pts, 22 + k * 6, choc, 1.2)
    # chocolate waterfall off a wafer cliff
    fx, fy = -700, -300
    fz = height(fx, fy) + 80
    w.link(ew.box("WaferCliff", 120, 40, 80, (fx, fy - 20, height(fx, fy) - 5), ginger, bevel=1.0), "Architecture")
    ew.ribbon(w, "ChocolateFall", [(fx, fy + 2, fz - i * 4) for i in range(21)], 40, choc, fall=True)
    # Sugar Road with candy-cane pillars
    road = ew.pbr("SugarRoad", "#fff1f6", "#f7c6d9", scale=1, rough=0.6)
    rd = [(-2400 + i * 80, -900 + 200 * math.sin(i * 0.15)) for i in range(55)]
    ew.ribbon(w, "SugarRoad", rd, 12, road, 0.4, col="Architecture")
    for i, (x, y) in enumerate(rd[::5]):
        for side in (-10, 10):
            c = ew.cyl(f"CandyCane_{i}_{side}", 1.4, 1.4, 26, 16, (x, y + side, height(x, y + side)), cherry)
            w.link(c, "Architecture")
            w.link(ew.sphere(f"CandyCaneTop_{i}_{side}", 2.2, (x, y + side, height(x, y + side) + 26), icing, 2), "Architecture")
    # gingerbread village
    for i in range(40):
        a = rnd.uniform(0, 6.283); r = rnd.uniform(200, 650)
        x, y = 900 + math.cos(a) * r, -700 + math.sin(a) * r
        z = height(x, y)
        hh = rnd.uniform(8, 14)
        w.link(ew.box(f"GingerHouse_{i}", 10, 8, hh, (x, y, z), ginger, rz=a, bevel=0.6), "Architecture")
        w.link(ew.cyl(f"GingerRoof_{i}", 8, 0.3, 7, 4, (x, y, z + hh), icing, rz=a + 0.785, smooth=False), "Architecture")
        w.link(ew.sphere(f"GumdropDoor_{i}", 1.4, (x + math.cos(a) * 5, y + math.sin(a) * 5, z + 1), mint if i % 2 else cherry, 2), "Architecture")
    # hidden secret: Truffle Vault inside the volcano flank
    vz = height(VX + 480, VY - 200) - 10
    w.link(ew.box("TruffleVault_Chamber", 30, 30, 14, (VX + 480, VY - 200, vz), ginger), "Architecture")
    for k in range(6):
        w.link(ew.sphere(f"GoldenTruffle_{k}", 1.6, (VX + 470 + k * 3.5, VY - 200, vz + 2), ew.pbr("GoldFoil", "#f2c14e", "#c48b1f", rough=0.2, metal=1.0), 3), "Architecture")
    ew.god_light(w, (VX + 480, VY - 200, vz + 10), "#ffcf70", 3000, 2).name = "Vault_Glow"
    # floating marshmallow clouds (hovering)
    for i in range(14):
        s = ew.sphere(f"MarshmallowCloud_{i}", rnd.uniform(25, 60), (rnd.uniform(-2500, 2500), rnd.uniform(-2500, 2500), rnd.uniform(380, 650)), marsh, 3, 0.55)
        ew.sculpt_layers(s, 6, i, ((0.6, 1.0, 'CLOUDS'),))
        ew.floating(s, rnd.uniform(6, 14), rnd.uniform(0.01, 0.025), i)
        w.link(s, "AmbientFX")
    candy = ew.tree_assets(w, "candy", "#ff7eb6", "#fff3f8", 4)
    ew.scatter(w, "LollipopForest", candy, "m_candy", 0.0025, 1, (0.8, 2.0), wind=0.03)
    ew.atmosphere(w, "#ffd6e2", "#9b7fd1", "#ffd9e8", 0.00008, (math.radians(58), 0, math.radians(-40)), "#ffe9d6", 4.0)
    ew.clouds(w, 900, 9000, "#ffe6f2", 0.5, 0.55)
    ew.birds(w, (0, 0, 0), 12, 400, 250, "#ff9ccd", 0.005)
    ew.floating_particles(w, (0, 0, 0), 2500, 30, 3000, "#ffd1e8", 3.0, "SugarSparkles")
    ew.camera_rig(w, radius=1500, height=420, hero=(700, -1200, height(700, -1200) + 8), lens=24)
    w.notes += ["Secret: Truffle Vault hidden in the volcano's east flank", "3 chocolate rivers + chocolate waterfall + pulsing caramel crater"]
    return w
