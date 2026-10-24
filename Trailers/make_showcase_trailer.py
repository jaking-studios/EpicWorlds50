"""
EpicWorlds50 showcase trailer: renders a shot from every world and cuts them together with
title cards in Blender's Video Sequencer, then encodes Trailers/EpicWorlds50_Trailer.mp4.

Run headless (it can take ~1 hour on a mid-range GPU):
    blender -b -P Trailers/make_showcase_trailer.py
Re-running skips frames that already exist, so it can resume after an interruption.
"""
import bpy, os, sys, time, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, "Trailers")
FR = os.path.join(TR, "frames")
LOG = os.path.join(TR, "trailer_progress.json")
FPS = 24
RES = (1920, 1080)
WORLDS = [
    ("RealWorldLandmarks", "RW01_GizaPlateau", "GIZA PLATEAU", "Great Pyramid of Khufu · 138 m"),
    ("RealWorldLandmarks", "RW02_MontSaintMichel", "MONT-SAINT-MICHEL", "Abbey spire · 177 m"),
    ("FantasyWorlds", "FW01_ChocolateLand", "CHOCOLATE LAND", "Cocoa Volcano · 420 m"),
    ("FantasyWorlds", "FW02_CrystalEmpire", "CRYSTAL EMPIRE", "Prism Spire · 640 m"),
    ("FantasyWorlds", "FW03_SkyKingdom", "SKY KINGDOM", "Storm Temple · 707 m"),
]
# Adventure cut per world: a 3 s drone dive that skims the ground toward the Mega Landmark,
# then a 5 s flythrough played at 3x speed (every 3rd frame of the orbit path).
DIVE_FRAMES = 72
FLY = (300, 660, 3)
INTRO, OUTRO = 3 * FPS, 5 * FPS


def log(**kw):
    state = {}
    if os.path.exists(LOG):
        try:
            state = json.load(open(LOG))
        except Exception:
            pass
    state.update(kw, updated=time.strftime("%H:%M:%S"))
    json.dump(state, open(LOG, "w"), indent=1)


def render_world(sub, wid):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, sub, wid + ".blend"))
    sc = bpy.context.scene
    ee = sc.eevee
    for a, v in (("taa_render_samples", 16), ("volumetric_samples", 24), ("volumetric_tile_size", '16'),
                 ("use_raytracing", False)):
        try:
            setattr(ee, a, v)
        except Exception:
            pass
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.timeline_markers.clear()
    out = os.path.join(FR, wid)
    os.makedirs(out, exist_ok=True)
    dive = make_dive_camera(sc)
    plan = [(dive, f) for f in range(1, DIVE_FRAMES + 1)]
    plan += [(bpy.data.objects["CAM_Flythrough"], f) for f in range(FLY[0], FLY[1], FLY[2])]
    total = len(plan)
    for n, (cam, f) in enumerate(plan, 1):
        path = os.path.join(out, f"{n:04d}.png")
        if os.path.exists(path):
            continue
        sc.camera = cam
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        if n % 12 == 0:
            log(world=wid, frame=n, of=total)
    return total


SKIP = ("AtmosphereFog", "CloudLayer", "Dust", "SandDust", "SeaSpray", "SugarSparkles", "MagicMotes", "SkyPollen", "Bird")


def ground(sc, x, y, top=3000.0):
    """Height of the first solid surface under (x, y), ignoring fog boxes, cloud sheets and particles."""
    from mathutils import Vector
    dg = bpy.context.evaluated_depsgraph_get()
    z = top
    for _ in range(12):
        hit, loc, _n, _i, obj, _m = sc.ray_cast(dg, Vector((x, y, z)), Vector((0, 0, -1)))
        if not hit:
            return None
        if obj and obj.name.startswith(SKIP):
            z = loc.z - 0.5
            continue
        return loc.z
    return None


def make_dive_camera(sc):
    """Fast, low drone dive toward the landmark: starts high and far, drops to skim the ground, ends close looking up."""
    import math
    from mathutils import Vector
    focus = bpy.data.objects["LandmarkFocus"].location.copy()
    beacon = bpy.data.objects.get("LandmarkBeacon")
    top = beacon.location.copy() if beacon else focus * Vector((1, 1, 1.8))
    hero = bpy.data.objects["CAM_HeroReveal"].location.copy()
    d = Vector((hero.x - focus.x, hero.y - focus.y, 0))
    d = d.normalized() if d.length > 1 else Vector((0.7, -0.7, 0))
    span = max(top.z - focus.z, 60.0) * 2.0
    keys = []
    for frac, dist_mul, alt in ((0.0, 9.0, 1.4), (0.45, 4.0, 0.0), (1.0, 1.2, 0.0)):
        x, y = focus.x + d.x * span * dist_mul, focus.y + d.y * span * dist_mul
        g = ground(sc, x, y)
        base = (g if g is not None else focus.z * 0.2)
        z = base + (span * alt if alt else max(14.0, span * 0.06))
        keys.append((1 + frac * (DIVE_FRAMES - 1), Vector((x, y, z))))
    cd = bpy.data.cameras.new("CAM_AdventureDive")
    cd.lens = 18
    cd.clip_end = 20000
    cam = bpy.data.objects.new("CAM_AdventureDive", cd)
    sc.collection.objects.link(cam)
    tgt = bpy.data.objects.new("DiveTarget", None)
    sc.collection.objects.link(tgt)
    for f, loc in keys:
        cam.location = loc
        cam.keyframe_insert("location", frame=f)
    tgt.location = focus
    tgt.keyframe_insert("location", frame=1)
    tgt.location = top
    tgt.keyframe_insert("location", frame=DIVE_FRAMES)
    cd.lens = 18
    cd.keyframe_insert("lens", frame=1)
    cd.lens = 24
    cd.keyframe_insert("lens", frame=DIVE_FRAMES)
    tr = cam.constraints.new('TRACK_TO')
    tr.target, tr.track_axis, tr.up_axis = tgt, 'TRACK_NEGATIVE_Z', 'UP_Y'
    # a touch of banking roll as the drone swoops in
    cam.rotation_mode = 'XYZ'
    return cam


def strips_of(se):
    return se.strips if hasattr(se, "strips") else se.sequences


def add_text(se, name, text, ch, start, length, size, y, color=(1, 1, 1, 1), bold=True):
    col = strips_of(se)
    try:
        st = col.new_effect(name=name, type='TEXT', channel=ch, frame_start=start, length=length)
    except TypeError:
        st = col.new_effect(name=name, type='TEXT', channel=ch, frame_start=start, frame_end=start + length)
    st.text = text
    st.font_size = size
    for attr, val in (("location", (0.5, y)), ("align_x", 'CENTER'), ("anchor_x", 'CENTER'), ("anchor_y", 'CENTER'),
                      ("use_shadow", True), ("use_bold", bold), ("color", color), ("blend_type", 'ALPHA_OVER')):
        try:
            setattr(st, attr, val)
        except Exception:
            pass
    return st


def add_color(se, name, ch, start, length, rgb):
    col = strips_of(se)
    try:
        st = col.new_effect(name=name, type='COLOR', channel=ch, frame_start=start, length=length)
    except TypeError:
        st = col.new_effect(name=name, type='COLOR', channel=ch, frame_start=start, frame_end=start + length)
    st.color = rgb
    return st


def edit_and_encode(lengths):
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    se = sc.sequence_editor_create()
    col = strips_of(se)
    t = 1
    add_color(se, "IntroBG", 1, t, INTRO, (0.05, 0.06, 0.09))
    add_text(se, "IntroBrand", "JAKING COMPANY PRESENTS", 3, t, INTRO, 42, 0.64, (0.96, 0.77, 0.33, 1))
    add_text(se, "IntroTitle", "EpicWorlds50", 4, t, INTRO, 160, 0.47)
    add_text(se, "IntroSub", "5 WORLDS. 1 ADVENTURE.", 5, t, INTRO, 56, 0.31, (1, 1, 1, 1))
    t += INTRO
    for k, ((sub, wid, name, lm), n) in enumerate(zip(WORLDS, lengths), 1):
        first = os.path.join(FR, wid, "0001.png")
        img = col.new_image(name=wid, filepath=first, channel=1, frame_start=t)
        for i in range(2, n + 1):
            img.elements.append(f"{i:04d}.png")
        try:
            img.frame_final_duration = n
        except Exception:
            pass
        add_text(se, wid + "_num", f"WORLD {k:02d} / 05", 5, t + 6, 66, 30, 0.88, (0.96, 0.77, 0.33, 1))
        add_text(se, wid + "_name", name, 3, t + 10, n - 20, 84, 0.14)
        add_text(se, wid + "_lm", "MEGA LANDMARK: " + lm.upper(), 4, t + 16, n - 26, 32, 0.075, (0.96, 0.77, 0.33, 1))
        t += n
    add_color(se, "OutroBG", 1, t, OUTRO, (0.05, 0.06, 0.09))
    add_text(se, "OutroHook", "YOUR ADVENTURE STARTS NOW", 7, t, OUTRO, 84, 0.76)
    add_text(se, "OutroTitle", "Play all 5 worlds free in your browser", 3, t, OUTRO, 50, 0.6, (0.85, 0.87, 0.92, 1), False)
    add_text(se, "OutroURL", "jaking-studios.github.io/EpicWorlds50", 4, t, OUTRO, 52, 0.48, (0.96, 0.77, 0.33, 1))
    add_text(se, "OutroSupport", "Support new worlds: patreon.com/c/JaineilRana", 5, t, OUTRO, 38, 0.32, (0.85, 0.87, 0.92, 1), False)
    add_text(se, "OutroName", "Made by Jaineil Rana (JaKing) · JaKing Studios", 6, t, OUTRO, 30, 0.2, (0.7, 0.73, 0.8, 1), False)
    t += OUTRO
    sc.frame_start, sc.frame_end = 1, t - 1
    r = sc.render
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH'
    r.ffmpeg.ffmpeg_preset = 'GOOD'
    r.filepath = os.path.join(TR, "EpicWorlds50_Trailer.mp4")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(TR, "EpicWorlds50_Trailer_edit.blend"))
    log(stage="encoding", frames=t - 1)
    bpy.ops.render.render(animation=True)
    log(stage="done", video=r.filepath, seconds=round((t - 1) / FPS, 1))


if __name__ == "__main__":
    t0 = time.time()
    log(stage="rendering", started=time.strftime("%H:%M:%S"))
    lengths = []
    for sub, wid, *_ in WORLDS:
        lengths.append(render_world(sub, wid))
    edit_and_encode(lengths)
    log(stage="done", minutes=round((time.time() - t0) / 60, 1))
