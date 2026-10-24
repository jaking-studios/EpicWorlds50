"""FW03 - Sky Kingdom (Fantasy). Mega Landmark: the Storm Temple, tip at 707 m."""
import math, random, bpy
import ew_core as ew

ID, TITLE = "FW03_SkyKingdom", "Sky Kingdom - The Floating Continents"
LORE = ("When the old world sank beneath the Cloud Sea, its mountain-tops broke free and rose. "
        "The Sky Kingdom now drifts on those islands, linked by rope bridges and sky-ships. At its "
        "centre the Storm Temple holds a captive thunderstorm, and a sunken bell tower can still be "
        "glimpsed through gaps in the clouds far below.")


def height(x, y):
    return -400 + 30 * ew.fbm(x, y, 0.001, 4, 3)   # hidden sea floor far below the clouds


def paint(x, y, z, slope):
    return (0.25, 0.30, 0.40), {"m_none": 0.0}


def island(w, name, x, y, z, r, mats, rnd, trees=True):
    top = ew.sphere(name + "_Top", r, (x, y, z), mats["grass"], 3, 0.18)
    ew.sculpt_layers(top, r * 0.04, rnd.randint(0, 9), ((0.5, 1.0, 'CLOUDS'),))
    rock = ew.cyl(name + "_Rock", r * 0.98, r * 0.12, r * 1.4, 18, (x, y, z - r * 1.4), mats["rock"])
    ew.sculpt_layers(rock, r * 0.08, rnd.randint(0, 9))
    w.link(top, "Architecture"); w.link(rock, "Architecture")
    parts = [top, rock]
    if trees:
        for i in range(int(r / 6)):
            a = rnd.uniform(0, 6.283); d = rnd.uniform(0, r * 0.8)
            t = ew.cyl(f"{name}_Pine{i}", rnd.uniform(2, 4), 0.2, rnd.uniform(10, 20), 8,
                       (x + math.cos(a) * d, y + math.sin(a) * d, z + r * 0.1), mats["leaf"])
            w.link(t, "Vegetation"); parts.append(t)
    piv = bpy.data.objects.new(name + "_Float", None); piv.location = (0, 0, 0); w.link(piv, "AmbientFX")
    for p in parts:
        p.parent = piv
    ew.floating(piv, rnd.uniform(4, 10), rnd.uniform(0.008, 0.02), rnd.uniform(0, 6))
    return piv


def build(root):
    w = ew.World(ID, TITLE, "fantasy", LORE, ["#7fb3ff", "#ffffff", "#4f7d3a", "#ffd36b"])
    ew.terrain(w, 6000, 60, height, paint, name="SunkenWorldFloor")
    rnd = random.Random(33)
    mats = {"grass": ew.pbr("SkyMeadow", "#6fa84a", "#3e6e2b", scale=3, rough=0.8, bump=0.3),
            "rock": ew.pbr("FloatRock", "#8d8a85", "#55524e", scale=1.2, rough=0.9, bump=0.7),
            "leaf": ew.pbr("SkyPine", "#2f5a2a", "#1d3a1a", scale=6, rough=0.7)}
    marble = ew.pbr("TempleMarble", "#f4f1ea", "#cfc8b8", scale=2, rough=0.35, bump=0.1)
    gold = ew.pbr("SkyGold", "#f2c14e", "#c48b1f", rough=0.2, metal=1.0, bump=0.05)
    wood = ew.pbr("ShipWood", "#7a5232", "#4a2f1a", scale=6, rough=0.8, bump=0.4)
    sail = ew.pbr("Sail", "#f7f3ea", "#e0d8c4", rough=0.9, bump=0.0)

    # central continent + Storm Temple (Mega Landmark)
    island(w, "Capital", 0, 0, 200, 260, mats, rnd)
    base = 200 + 260 * 0.18
    w.link(ew.box("StormTemple_Plinth", 120, 120, 30, (0, 0, base - 10), marble, bevel=1.0), "MegaLandmark")
    for i in range(16):
        a = i / 16 * 6.283
        w.link(ew.cyl(f"StormTemple_Column{i}", 3, 2.6, 120, 16, (math.cos(a) * 45, math.sin(a) * 45, base + 20), marble), "MegaLandmark")
    w.link(ew.cyl("StormTemple_Ring", 52, 52, 10, 32, (0, 0, base + 140), gold), "MegaLandmark")
    w.link(ew.cyl("StormTemple_Tower", 26, 8, 250, 16, (0, 0, base + 150), marble), "MegaLandmark")
    w.link(ew.cyl("StormTemple_Lightning_Rod", 2, 0.3, 60, 8, (0, 0, base + 400), gold), "MegaLandmark")
    storm = ew.sphere("CaptiveStorm", 40, (0, 0, base + 95), ew.pbr("StormOrb", "#9fc9ff", "#ffffff", emit="#bfe0ff", emit_str=12, rough=0.1), 4)
    ew.pulse(storm.data.materials[0], 12, 10, 0.3)
    ew.floating(storm, 3, 0.05, 0, 0.02)
    w.link(storm, "MegaLandmark")
    ew.mega_landmark(w, "Storm Temple", base + 460 - 200 + 200, (0, 0, base + 460), "#bfe0ff")
    flash = ew.god_light(w, (0, 0, base + 95), "#cfe6ff", 5e5, 20); flash.name = "StormLightning"
    ew.drive(flash.data, "energy", "500000*max(0,sin(frame*0.37))**12+50000")   # lightning strikes
    # satellite islands + rope bridges
    sats = []
    for i in range(9):
        a = i / 9 * 6.283 + rnd.uniform(-0.2, 0.2); d = rnd.uniform(650, 1300)
        x, y, z = math.cos(a) * d, math.sin(a) * d, rnd.uniform(80, 380)
        r = rnd.uniform(70, 150)
        island(w, f"Isle{i}", x, y, z, r, mats, rnd)
        sats.append((x, y, z + r * 0.18))
        hh = rnd.uniform(25, 60)
        w.link(ew.cyl(f"Isle{i}_Tower", 10, 8, hh, 12, (x, y, z + r * 0.15), marble), "Architecture")
        w.link(ew.cyl(f"Isle{i}_Roof", 12, 0.5, 15, 12, (x, y, z + r * 0.15 + hh), gold), "Architecture")
    bridge = ew.pbr("RopeBridge", "#9b7b52", "#6b5233", scale=8, rough=0.9)
    for i, (x, y, z) in enumerate(sats[:5]):
        pts = [(x * t, y * t, z * t + base * (1 - t) - 18 * math.sin(t * math.pi)) for t in [k / 40 for k in range(4, 37)]]
        ew.ribbon(w, f"RopeBridge_{i}", pts, 4, bridge, fall=True, col="Architecture")
    # waterfalls pouring off the capital into the void
    water = ew.flowing("SkyFall", "#bfe6ff", "#ffffff", speed=0.12, emit="#e6f6ff", emit_str=0.6, rough=0.05)
    for k in range(3):
        a = k * 2.1 + 0.4
        x, y = math.cos(a) * 250, math.sin(a) * 250
        ew.ribbon(w, f"SkyWaterfall_{k}", [(x, y, base - i * 25) for i in range(30)], 24, water, fall=True)
    # sky-ships circling the kingdom
    for i in range(4):
        piv = bpy.data.objects.new(f"SkyShipOrbit{i}", None); piv.location = (0, 0, 350 + i * 60); w.link(piv, "AmbientFX")
        ew.drive(piv, "rotation_euler", f"frame*{0.002 + i * 0.0007:.4f}+{i * 1.6}", 2)
        hull = ew.box(f"SkyShip{i}_Hull", 8, 30, 7, (900 + i * 150, 0, 0), wood, bevel=1.5); hull.parent = piv
        mast = ew.cyl(f"SkyShip{i}_Mast", 0.6, 0.4, 26, 8, (900 + i * 150, 0, 6), wood); mast.parent = piv
        sl = ew.box(f"SkyShip{i}_Sail", 0.3, 16, 16, (900 + i * 150, 0, 12), sail); sl.parent = piv
        bal = ew.sphere(f"SkyShip{i}_Balloon", 12, (900 + i * 150, 0, 40), ew.pbr("Balloon", "#d94a3a", "#ffb04a", rough=0.6), 3, 1.3); bal.parent = piv
        for o in (hull, mast, sl, bal):
            w.link(o, "AmbientFX")
    # floating lanterns
    lant = ew.pbr("Lantern", "#ffcf7a", "#ffb04a", emit="#ffb04a", emit_str=15)
    for i in range(60):
        l = ew.sphere(f"Lantern_{i}", 1.2, (rnd.uniform(-800, 800), rnd.uniform(-800, 800), rnd.uniform(260, 520)), lant, 1, 1.4)
        ew.floating(l, rnd.uniform(3, 8), rnd.uniform(0.02, 0.05), i)
        w.link(l, "AmbientFX")
    # sunken bell tower (secret) visible through gaps in the clouds
    w.link(ew.cyl("SunkenBellTower", 20, 16, 160, 12, (500, -700, -400), marble), "Architecture")
    # the cloud sea (several drifting layers) below the islands
    ew.clouds(w, -60, 9000, "#ffffff", 0.9, 0.35)
    ew.clouds(w, 900, 9000, "#ffffff", 0.4, 0.62)
    ew.atmosphere(w, "#ffffff", "#4f8fe8", "#e8f2ff", 0.00005, (math.radians(50), 0, math.radians(60)), "#fff3e0", 5.0)
    ew.birds(w, (0, 0, 200), 24, 500, 200, "#ffffff", 0.006)
    ew.floating_particles(w, (0, 0, 0), 2500, 150, 2000, "#ffffff", 2.0, "SkyPollen")
    ew.camera_rig(w, radius=1400, height=520, hero=(600, -700, 320), lens=24)
    w.notes += ["Islands float via drivers; bridges sag procedurally", "Captive storm with randomised lightning flashes",
                "Secret: sunken bell tower visible below the cloud sea"]
    return w
