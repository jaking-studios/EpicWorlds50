"""
Render the 60-second showcase trailer for a world.

Every world ships with its camera path already cut: Hero Reveal (0-12 s) ->
drone Flythrough (12-51 s) -> Aerial (51-60 s), bound to timeline markers.

Usage (from the EpicWorlds50 folder):
    blender -b RealWorldLandmarks/RW01_GizaPlateau.blend -P Trailers/render_trailer.py
    blender -b FantasyWorlds/FW01_ChocolateLand.blend -P Trailers/render_trailer.py -- --preview

Options after "--":
    --preview      960x540, 16 samples, every 2nd frame (fast draft)
    --night        animate a sunset-to-night pass via the day/night driver
Output: Trailers/<WorldID>.mp4
"""
import bpy, os, sys

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
sc = bpy.context.scene
root = os.path.dirname(os.path.dirname(bpy.data.filepath))
wid = os.path.splitext(os.path.basename(bpy.data.filepath))[0]

sc.render.engine = 'BLENDER_EEVEE'
if "--preview" in args:
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    sc.eevee.taa_render_samples = 16
    sc.frame_step = 2
if "--night" in args:
    sc["day_night_speed"] = 0.0012

sc.render.image_settings.file_format = 'FFMPEG'
sc.render.ffmpeg.format = 'MPEG4'
sc.render.ffmpeg.codec = 'H264'
sc.render.ffmpeg.constant_rate_factor = 'HIGH'
sc.render.ffmpeg.ffmpeg_preset = 'GOOD'
sc.render.filepath = os.path.join(root, "Trailers", f"{wid}.mp4")
print(f"[EpicWorlds50] Rendering trailer for {wid} -> {sc.render.filepath}")
bpy.ops.render.render(animation=True)
