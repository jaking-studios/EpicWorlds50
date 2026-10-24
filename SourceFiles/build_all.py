"""
Rebuild every EpicWorlds50 world from source.

    blender -b -P SourceFiles/build_all.py                 # all worlds
    blender -b -P SourceFiles/build_all.py -- fw01 rw02    # only matching worlds
    blender -b -P SourceFiles/build_all.py -- --renders    # also render preview stills

Each world script exposes build(root) and returns a World; finish() saves the
.blend into RealWorldLandmarks/ or FantasyWorlds/ and writes
Documentation/worlds/<id>.json (stats, landmark, build time).
"""
import bpy, os, sys, glob, importlib, json, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(HERE, "pipeline"), os.path.join(HERE, "worlds")]
import ew_core

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
filters = [a for a in args if not a.startswith("--")]
mods = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(HERE, "worlds", "*.py")))
mods = [m for m in mods if not filters or any(m.startswith(f) for f in filters)]

summary = []
for name in mods:
    try:
        mod = importlib.import_module(name)
        w = mod.build(ROOT)
        meta = w.finish(ROOT)
        if "--renders" in args:
            for cam, fr in (("CAM_HeroReveal", 1), ("CAM_Aerial", 1300)):
                ew_core.preview_render(w, ROOT, cam, (1280, 720), fr)
            bpy.ops.wm.save_mainfile()
        summary.append((name, "OK", meta["objects"], meta["mega_landmark"]["height_m"]))
    except Exception:
        traceback.print_exc()
        summary.append((name, "FAILED", 0, 0))

print("\n=== EpicWorlds50 build summary ===")
for row in summary:
    print("{:<28} {:<7} objects={:<5} landmark={} m".format(*row))
