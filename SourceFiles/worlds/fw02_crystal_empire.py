"""FW02 - Crystal Empire (Fantasy). Mega Landmark: the Prism Spire, 640 m."""
import math, random, bpy
import ew_core as ew

ID, TITLE = "FW02_CrystalEmpire", "Crystal Empire - City of the Prism Spire"
LORE = ("The Crystal Empire grew from a single seed-shard that fell during the Night of Falling "
        "Light. Its people sing the crystals into shape: hexagonal towers ring the Prism Spire, "
        "whose heartbeat pulse powers the whole city. Shards torn loose by old storms still hover "
        "over the valley, and the Echo Caves beneath the northern ridge answer anyone who sings.")


def height(x, y):
    r = math.hypot(x, y)
    basin = -20 * max(0.0, 1 - r / 900)
    ridges = 260 * max(0.0, ew.ridge(x, y, 0.0009, 3) - 0.55) * min(1.0, max(0.0, (r - 1100) / 700))
    return basin + ridges + 14 * ew.fbm(x, y, 0.002, 4, 8)


def paint(x, y, z, slope):
    n = ew.fbm(x, y, 0.015, 3, 2)
    if slope > 0.35 or z > 120:
        return (0.20, 0.22, 0.32), {"m_crystal": 1.0 if n > 0.2 else 0.0, "m_shrub": 0.0}
    return (0.12 + 0.04 * n, 0.18 + 0.05 * n, 0.30), {"m_crystal": 1.0 if n > 0.35 else 0.0, "m_shrub": 1.0 if n < 0.0 else 0.0}


def crystal_mat(name, c1, c2, glow, s=4.0):
    return ew.pbr(name, c1, c2, scale=s, rough=0.04, bump=0.05, emit=glow, emit_str=2.0, transmission=0.6)


def build(root):
    w = ew.World(ID, TITLE, "fantasy", LORE, ["#5ee0ff", "#8a6bff", "#1b2340", "#e6f7ff"])
    ew.terrain(w, 6000, 200, height, paint)
    prism = crystal_mat("Prism", "#a8f0ff", "#8a6bff", "#6fe3ff", 2)
    ew.pulse(prism, 4, 3, 0.06)
    amethyst = crystal_mat("Amethyst", "#b796ff", "#5b3fc4", "#9d7bff")
    ew.pulse(amethyst, 2, 1.5, 0.05, 1.3)
    stone = ew.pbr("MoonMarble", "#d9def0", "#9aa3c4", scale=3, rough=0.3, bump=0.15)
    rnd = random.Random(21)

    # Mega Landmark: the Prism Spire
    w.link(ew.cyl("PrismSpire_Base", 70, 50, 60, 6, (0, 0, -10), stone, smooth=False), "MegaLandmark")
    w.link(ew.cyl("PrismSpire_Shaft", 40, 14, 480, 6, (0, 0, 50), prism, smooth=False), "MegaLandmark")
    w.link(ew.cyl("PrismSpire_Tip", 14, 0, 110, 6, (0, 0, 530), prism, smooth=False), "MegaLandmark")
    heart = ew.sphere("PrismSpire_Heart", 18, (0, 0, 300), ew.pbr("HeartCore", "#ffffff", "#bff4ff", emit="#9ff0ff", emit_str=30, rough=0.1), 3)
    ew.floating(heart, 6, 0.04, 0, 0.01)
    w.link(heart, "MegaLandmark")
    ew.mega_landmark(w, "Prism Spire", 640, (0, 0, 630), "#7fe9ff")
    # energy beams from the spire to four pylons
    beam = ew.pbr("EnergyBeam", "#aef6ff", "#ffffff", emit="#7fe9ff", emit_str=25, rough=0.2)
    ew.pulse(beam, 20, 12, 0.12)
    for k in range(4):
        a = k * 1.5708 + 0.785
        px, py = math.cos(a) * 700, math.sin(a) * 700
        w.link(ew.cyl(f"Pylon_{k}", 12, 4, 160, 6, (px, py, height(px, py)), amethyst, smooth=False), "Architecture")
        b = ew.cyl(f"EnergyBeam_{k}", 1.5, 1.5, 700, 8, (0, 0, 300), beam)
        b.rotation_euler = (math.radians(102), 0, a + 1.5708); w.link(b, "AmbientFX")
    # ring city of hex towers
    for ring, (rad, count, hmin, hmax) in enumerate(((220, 12, 80, 160), (380, 20, 50, 120), (560, 30, 25, 80))):
        for i in range(count):
            a = i / count * 6.283 + ring * 0.2
            x, y = math.cos(a) * rad, math.sin(a) * rad
            h = rnd.uniform(hmin, hmax)
            z = height(x, y) - 2
            w.link(ew.cyl(f"HexTower_{ring}_{i}", rnd.uniform(9, 16), rnd.uniform(5, 9), h, 6, (x, y, z), stone, rz=a, smooth=False), "Architecture")
            w.link(ew.cyl(f"HexTowerCap_{ring}_{i}", 6, 0, h * 0.3, 6, (x, y, z + h), prism if i % 3 else amethyst, smooth=False), "Architecture")
    # hovering shards
    for i in range(40):
        s = ew.cyl(f"FloatingShard_{i}", rnd.uniform(4, 12), 0, rnd.uniform(20, 70), 6,
                   (rnd.uniform(-1600, 1600), rnd.uniform(-1600, 1600), rnd.uniform(150, 520)), amethyst if i % 2 else prism, smooth=False)
        s.rotation_euler = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 0)
        ew.floating(s, rnd.uniform(5, 15), rnd.uniform(0.01, 0.03), i, rnd.uniform(0.002, 0.008))
        w.link(s, "AmbientFX")
    # Echo Caves (secret): crystal-lined chamber in the north ridge
    cx, cy = 0, 1500; cz = height(cx, cy) - 30
    w.link(ew.box("EchoCave_Chamber", 60, 60, 25, (cx, cy, cz), stone), "Architecture")
    for k in range(10):
        w.link(ew.cyl(f"EchoCrystal_{k}", 2.5, 0, rnd.uniform(6, 14), 6, (cx - 25 + k * 5.5, cy + rnd.uniform(-20, 20), cz), amethyst, smooth=False), "Architecture")
    ew.god_light(w, (cx, cy, cz + 12), "#9d7bff", 8000, 3).name = "EchoCave_Glow"
    # magic water
    ew.ribbon(w, "StarlightRiver", [(-2800 + i * 100, -900 + 300 * math.sin(i * 0.2)) for i in range(57)], 60,
              ew.flowing("StarWater", "#123a66", "#47c6ff", speed=0.04, emit="#3fb8ff", emit_str=1.5), 1.0)
    crystals = ew.tree_assets(w, "crystal", "#8fe8ff", "#6c52d9", 4)
    shrubs = ew.tree_assets(w, "shrub", "#3e5fa8", "#22315e", 3)
    ew.scatter(w, "CrystalGroves", crystals, "m_crystal", 0.002, 1, (0.6, 2.5), wind=0.0)
    ew.scatter(w, "GlowShrubs", shrubs, "m_shrub", 0.004, 2, (0.6, 1.4), wind=0.03)
    ew.atmosphere(w, "#2c2f6b", "#0b0f24", "#6a7cff", 0.00010, (math.radians(70), 0, math.radians(20)), "#bfd4ff", 2.0)
    ew.clouds(w, 1100, 9000, "#9aa8ff", 0.5, 0.6)
    ew.floating_particles(w, (0, 0, 0), 3000, 20, 4000, "#9ff0ff", 8.0, "MagicMotes")
    ew.birds(w, (0, 0, 0), 10, 500, 420, "#c6b8ff", 0.004)  # crystal moths
    ew.camera_rig(w, radius=1300, height=420, hero=(320, -900, height(320, -900) + 6), lens=22)
    w.notes += ["Secret: Echo Caves under the north ridge", "Prism Spire heart pulses and powers 4 energy beams"]
    return w
