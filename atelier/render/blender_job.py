"""Import exported meshes and render framed Blender scenes."""
import math, sys

DEFAULTS = {"glb": "", "out": "render.png", "engine": "CYCLES", "samples": 64, "width": 1600, "height": 1200,
            "azimuth": 35.0, "elevation": 28.0, "ortho": False, "ground": True, "sun_elevation": 42.0,
            "sun_rotation": 140.0, "views": 1, "keep_scene": False, "transparent": False}


def render_build(opts):
    import bpy
    from mathutils import Vector
    o = dict(DEFAULTS); o.update(opts or {})
    if not o["keep_scene"]:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=o["glb"])
    objs = [ob for ob in bpy.data.objects if ob not in before and ob.type == "MESH"]
    if not objs:
        raise RuntimeError("GLB 里没有网格")
    # 像素风: 贴图用最近邻采样
    for ob in objs:
        for slot in ob.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes: continue
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE": node.interpolation = "Closest"
            for attr, val in (("blend_method", "BLEND" if "translucent" in mat.name else "CLIP"),
                              ("surface_render_method", "BLENDED" if "translucent" in mat.name else "DITHERED")):
                try: setattr(mat, attr, val)
                except Exception: pass
    # 包围盒
    pts = [ob.matrix_world @ Vector(c) for ob in objs for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (lo + hi) / 2; radius = max((hi - lo).length / 2, 1.0)
    # 地面
    if o["ground"]:
        bpy.ops.mesh.primitive_plane_add(size=radius * 40, location=(center.x, center.y, lo.z - 0.001))
        ground = bpy.context.active_object; ground.name = "atelier_ground"
        gm = bpy.data.materials.new("atelier_ground"); gm.use_nodes = True
        bsdf = gm.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.36, 0.42, 0.30, 1); bsdf.inputs["Roughness"].default_value = 1.0
        ground.data.materials.append(gm)
    # 天空 + 太阳
    world = bpy.data.worlds.new("atelier_world"); scene.world = world; world.use_nodes = True
    nt = world.node_tree; bg = nt.nodes.get("Background")
    sky = nt.nodes.new("ShaderNodeTexSky")
    for t in ("MULTIPLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):     # 不同 Blender 版本的天空模型名不同
        try: sky.sky_type = t; break
        except Exception: continue
    for attr, val in (("sun_elevation", math.radians(o["sun_elevation"])), ("sun_rotation", math.radians(o["sun_rotation"])),
                      ("sun_disc", False)):
        try: setattr(sky, attr, val)
        except Exception: pass
    nt.links.new(sky.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.35
    sun_data = bpy.data.lights.new("atelier_sun", "SUN"); sun_data.energy = 4.0; sun_data.angle = math.radians(2.0)
    sun = bpy.data.objects.new("atelier_sun", sun_data); scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(90 - o["sun_elevation"]), 0, math.radians(o["sun_rotation"]))
    # 相机
    cam_data = bpy.data.cameras.new("atelier_cam"); cam = bpy.data.objects.new("atelier_cam", cam_data)
    scene.collection.objects.link(cam); scene.camera = cam
    cam_data.clip_end = radius * 100
    # 渲染设置
    engine = o["engine"].upper()
    if engine == "EEVEE":
        for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try: scene.render.engine = e; break
            except Exception: continue
    else:
        scene.render.engine = "CYCLES"; scene.cycles.samples = int(o["samples"])
        try: scene.cycles.use_denoising = True
        except Exception: pass
    scene.render.resolution_x, scene.render.resolution_y = int(o["width"]), int(o["height"])
    scene.render.film_transparent = bool(o["transparent"])
    scene.render.image_settings.file_format = "PNG"
    try: scene.view_settings.view_transform = "Standard"       # 保持方块原色，不要 Filmic 的灰
    except Exception: pass
    outs = []
    n = max(1, int(o["views"]))
    for i in range(n):
        az = math.radians(o["azimuth"] + 360.0 * i / n); el = math.radians(o["elevation"])
        d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
        if o["ortho"]:
            cam_data.type = "ORTHO"; cam_data.ortho_scale = radius * 2.1; dist = radius * 4
        else:
            cam_data.type = "PERSP"; cam_data.lens = 50
            fov = 2 * math.atan(min(cam_data.sensor_width, cam_data.sensor_width * o["height"] / o["width"]) / 2 / cam_data.lens)
            dist = radius / math.sin(fov / 2) * 1.05
        cam.location = center + d * dist
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        path = o["out"] if n == 1 else o["out"].replace(".png", f"_{i}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        outs.append(path)
    return outs


def _cli():
    import argparse
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    for k, v in DEFAULTS.items():
        if isinstance(v, bool): ap.add_argument("--" + k, type=lambda s: s.lower() in ("1", "true", "yes"), default=v)
        else: ap.add_argument("--" + k, type=type(v), default=v)
    print("ATELIER_RENDERED", render_build(vars(ap.parse_args(argv))))


if __name__ == "__main__":
    _cli()
