"""Bake Minecraft block models and textures into GLB and OBJ meshes."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .blocks import parse_state

DIRS = {"down": (0, -1, 0), "up": (0, 1, 0), "north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0), "east": (1, 0, 0)}
_Y_CW = {"north": "east", "east": "south", "south": "west", "west": "north", "up": "up", "down": "down"}
_X_ROT = {"up": "north", "north": "down", "down": "south", "south": "up", "east": "east", "west": "west"}


def _face_quad(name, f, t):
    """返回 4 个角 (左上, 左下, 右下, 右上)，从外侧看为逆时针。"""
    x1, y1, z1 = f; x2, y2, z2 = t
    return {
        "up":    [(x1, y2, z1), (x1, y2, z2), (x2, y2, z2), (x2, y2, z1)],
        "down":  [(x1, y1, z2), (x1, y1, z1), (x2, y1, z1), (x2, y1, z2)],
        "north": [(x2, y2, z1), (x2, y1, z1), (x1, y1, z1), (x1, y2, z1)],
        "south": [(x1, y2, z2), (x1, y1, z2), (x2, y1, z2), (x2, y2, z2)],
        "west":  [(x1, y2, z1), (x1, y1, z1), (x1, y1, z2), (x1, y2, z2)],
        "east":  [(x2, y2, z2), (x2, y1, z2), (x2, y1, z1), (x2, y2, z1)],
    }[name]


def _default_uv(name, f, t):
    x1, y1, z1 = f; x2, y2, z2 = t
    return {"up": [x1, z1, x2, z2], "down": [x1, 16 - z2, x2, 16 - z1],
            "north": [16 - x2, 16 - y2, 16 - x1, 16 - y1], "south": [x1, 16 - y2, x2, 16 - y1],
            "west": [z1, 16 - y2, z2, 16 - y1], "east": [16 - z2, 16 - y2, 16 - z1, 16 - y1]}[name]


class ModelBaker:
    def __init__(self, reg):
        d = reg.dir
        self.reg = reg
        self.states = json.loads((d / "blockstates.json").read_text())
        self.models = json.loads((d / "models.json").read_text())
        self.atlas = json.loads((d / "atlas.json").read_text())
        self.atlas_path = d / "atlas.png"
        self.translucent = set(self.atlas["translucent"])
        self._cache = {}

    # ---- 模型解析 ----
    def _resolve(self, name, depth=0):
        name = name.split(":", 1)[-1]
        m = self.models.get(name)
        if m is None or depth > 12: return {}, None
        tex, els = self._resolve(m["parent"], depth + 1) if "parent" in m else ({}, None)
        tex = dict(tex); tex.update(m.get("textures", {}))
        return tex, m.get("elements", els)

    @staticmethod
    def _tex(textures, ref):
        for _ in range(10):
            if isinstance(ref, dict): ref = ref.get("sprite", "")
            if not ref.startswith("#"): return ref.split(":", 1)[-1]
            ref = textures.get(ref[1:], "")
            if not ref: return None
        return None

    @staticmethod
    def _when(cond, props):
        if "OR" in cond: return any(ModelBaker._when(c, props) for c in cond["OR"])
        if "AND" in cond: return all(ModelBaker._when(c, props) for c in cond["AND"])
        return all(str(props.get(k)) in str(v).split("|") for k, v in cond.items())

    def _applies(self, bid, props):
        bs = self.states.get(bid)
        if not bs: return []
        out = []
        if "variants" in bs:
            for key, v in bs["variants"].items():
                cond = dict(kv.split("=", 1) for kv in key.split(",") if kv)
                if all(props.get(k) == val for k, val in cond.items()):
                    out.append(v[0] if isinstance(v, list) else v); break
        for part in bs.get("multipart", []):
            if "when" not in part or self._when(part["when"], props):
                a = part["apply"]; out.append(a[0] if isinstance(a, list) else a)
        return out

    def quads(self, state):
        """-> [(verts(4x3, 0..1 方块内坐标), uv(4x2, 贴图内 0..1), 贴图名, 剔除方向 或 None)]"""
        if state in self._cache: return self._cache[state]
        bid, props = self.reg.full_props(state)
        out = []
        applies = self._applies(bid, props)
        for ap in applies:
            tex, els = self._resolve(ap["model"])
            xr, yr = int(ap.get("x", 0)) // 90 % 4, int(ap.get("y", 0)) // 90 % 4
            for el in els or []:
                f, t = el["from"], el["to"]
                rot = el.get("rotation")
                for fname, face in el.get("faces", {}).items():
                    tname = self._tex(tex, face.get("texture", ""))
                    if tname not in self.atlas["tex"]: continue
                    corners = np.array(_face_quad(fname, f, t), np.float64)
                    if rot:
                        corners = self._el_rot(corners, rot)
                    u1, v1, u2, v2 = face.get("uv") or _default_uv(fname, f, t)
                    uv = [(u1, v1), (u1, v2), (u2, v2), (u2, v1)]
                    k = int(face.get("rotation", 0)) // 90 % 4
                    uv = uv[k:] + uv[:k]
                    cull = face.get("cullface")
                    c = corners - 8.0
                    for _ in range(xr):                       # 绕 X: 上 -> 北
                        c = np.stack([c[:, 0], c[:, 2], -c[:, 1]], 1)
                        cull = _X_ROT.get(cull, cull)
                    for _ in range(yr):                       # 绕 Y: 北 -> 东 (俯视顺时针)
                        c = np.stack([-c[:, 2], c[:, 1], c[:, 0]], 1)
                        cull = _Y_CW.get(cull, cull)
                    out.append(((c + 8.0) / 16.0, np.array(uv, np.float64) / 16.0, tname, cull))
        if not out:
            out = self._fallback(bid)
        self._cache[state] = out
        return out

    @staticmethod
    def _el_rot(c, rot):
        ang = np.deg2rad(rot.get("angle", 0)); o = np.array(rot.get("origin", [8, 8, 8]), np.float64)
        ax = "xyz".index(rot.get("axis", "y")); a, b = [i for i in range(3) if i != ax]
        p = c - o; q = p.copy()
        # 右手系旋转
        ca, sa = np.cos(ang), np.sin(ang)
        if ax == 1: q[:, 2] = p[:, 2] * ca - p[:, 0] * sa; q[:, 0] = p[:, 0] * ca + p[:, 2] * sa
        elif ax == 0: q[:, 1] = p[:, 1] * ca - p[:, 2] * sa; q[:, 2] = p[:, 2] * ca + p[:, 1] * sa
        else: q[:, 0] = p[:, 0] * ca - p[:, 1] * sa; q[:, 1] = p[:, 1] * ca + p[:, 0] * sa
        if rot.get("rescale"):
            s = 1.0 / max(abs(ca), 1e-6); q[:, a] *= s; q[:, b] *= s
        return q + o

    def _fallback(self, bid):
        """没有可烘焙模型的方块 (方块实体、流体): 用粒子贴图/平均色做一个替身方块。"""
        bs = self.states.get(bid); tname = None
        if bs:
            ap = (self._applies(bid, self.reg.full_props("minecraft:" + bid)[1]) or [None])[0]
            if ap:
                tex, _ = self._resolve(ap["model"]); tname = self._tex(tex, "#particle")
        if bid == "water": tname = "block/water_still"
        if bid == "lava": tname = "block/lava_still"
        if tname not in self.atlas["tex"]: return []
        f, t = ([0, 0, 0], [16, 14, 16]) if bid in ("water", "lava") else ([1, 0, 1], [15, 14, 15])
        out = []
        for fname in DIRS:
            c = np.array(_face_quad(fname, f, t), np.float64) / 16.0
            u1, v1, u2, v2 = _default_uv(fname, f, t)
            cull = fname if bid in ("water", "lava") and fname != "up" else None
            out.append((c, np.array([(u1, v1), (u1, v2), (u2, v2), (u2, v1)]) / 16.0, tname, cull))
        return out

    # ---- 整体网格 ----
    def build(self, grid):
        """-> dict(verts Nx3, uv Nx2(贴图内), tex [每个 quad 的贴图名], quads M)"""
        pal, arr, _ = grid.to_dense()
        opaque = np.array([False] + [self.reg.info(parse_state(s)[0]).get("opaque", False) for s in pal[1:]])
        occ_opaque = np.pad(opaque[arr], 1)
        same_cull = {i for i, s in enumerate(pal) if i and (self.reg.info(parse_state(s)[0]).get("translucent") or
                                                             parse_state(s)[0] in ("glass", "water", "lava") or "glass" in s and "pane" not in s)}
        padded = np.pad(arr, 1)
        V, UV, T = [], [], []
        qcache = [None] + [self.quads(s) for s in pal[1:]]
        xs, ys, zs = np.nonzero(arr)
        for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist()):
            pi = int(arr[x, y, z])
            for verts, uv, tname, cull in qcache[pi]:
                if cull:
                    dx, dy, dz = DIRS[cull]
                    if occ_opaque[x + 1 + dx, y + 1 + dy, z + 1 + dz]: continue
                    if pi in same_cull and padded[x + 1 + dx, y + 1 + dy, z + 1 + dz] == pi: continue
                V.append(verts + (x, y, z)); UV.append(uv); T.append(tname)
        if not V:
            return {"verts": np.zeros((0, 3)), "uv": np.zeros((0, 2)), "tex": [], "quads": 0}
        return {"verts": np.concatenate(V), "uv": np.concatenate(UV), "tex": T, "quads": len(T)}

    # ---- 导出 ----
    def export_glb(self, grid, path):
        import trimesh
        from trimesh.visual.material import PBRMaterial
        from trimesh.visual import TextureVisuals
        m = self.build(grid)
        atlas_img = Image.open(self.atlas_path).convert("RGBA")
        AW, AH = atlas_img.size; cell = self.atlas["cell"]; eps = 0.02
        n = m["quads"]
        if n == 0: raise ValueError("没有可渲染的面")
        org = np.array([self.atlas["tex"][t] for t in m["tex"]], np.float64)          # 每 quad 的图集原点
        uv = m["uv"].reshape(n, 4, 2).copy()
        ctr = uv.mean(1, keepdims=True)
        uv = ctr + (uv - ctr) * (1 - eps)                                               # 略内缩，防止图集渗色
        px = org[:, None, :] + uv * cell
        guv = np.stack([px[..., 0] / AW, 1.0 - px[..., 1] / AH], -1).reshape(-1, 2)
        trans = np.array([t in self.translucent for t in m["tex"]])
        scene = trimesh.Scene()
        lo, hi = m["verts"].min(0), m["verts"].max(0)
        offset = np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])           # 落地居中
        for label, mask, mode in (("opaque", ~trans, "MASK"), ("translucent", trans, "BLEND")):
            idx = np.nonzero(mask)[0]
            if not len(idx): continue
            vi = (idx[:, None] * 4 + np.arange(4)).reshape(-1)
            base = np.arange(len(idx)) * 4
            faces = np.concatenate([np.stack([base, base + 1, base + 2], 1), np.stack([base, base + 2, base + 3], 1)])
            mat = PBRMaterial(name="mc_" + label, baseColorTexture=atlas_img, metallicFactor=0.0, roughnessFactor=1.0,
                              alphaMode=mode, alphaCutoff=0.5 if mode == "MASK" else None, doubleSided=True)
            mesh = trimesh.Trimesh(vertices=m["verts"][vi] - offset, faces=faces, process=False,
                                   visual=TextureVisuals(uv=guv[vi], material=mat))
            scene.add_geometry(mesh, geom_name=label, node_name=label)
        scene.export(str(path))
        return {"quads": int(n), "triangles": int(n * 2)}

    def export_obj(self, grid, out_dir, name="build"):
        """OBJ + MTL + textures/*.png，每张贴图一个材质 (材质名=贴图名，如 oak_planks)。"""
        out_dir = Path(out_dir); (out_dir / "textures").mkdir(parents=True, exist_ok=True)
        m = self.build(grid)
        atlas_img = Image.open(self.atlas_path).convert("RGBA"); cell = self.atlas["cell"]
        used = sorted(set(m["tex"]))
        with open(out_dir / f"{name}.mtl", "w") as f:
            for t in used:
                short = t.split("/", 1)[1]
                x, y = self.atlas["tex"][t]
                atlas_img.crop((x, y, x + cell, y + cell)).save(out_dir / "textures" / f"{short}.png")
                f.write(f"newmtl {short}\nKd 1 1 1\nKs 0 0 0\nmap_Kd textures/{short}.png\nmap_d textures/{short}.png\n\n")
        order = sorted(range(m["quads"]), key=lambda i: m["tex"][i])
        with open(out_dir / f"{name}.obj", "w") as f:
            f.write(f"# BlockAtelier export\nmtllib {name}.mtl\no {name}\n")
            for v in m["verts"]: f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            for u in m["uv"]: f.write(f"vt {u[0]:.4f} {1 - u[1]:.4f}\n")
            cur = None
            for i in order:
                if m["tex"][i] != cur:
                    cur = m["tex"][i]; f.write(f"usemtl {cur.split('/', 1)[1]}\n")
                a = i * 4 + 1
                f.write(f"f {a}/{a} {a+1}/{a+1} {a+2}/{a+2} {a+3}/{a+3}\n")
        return str(out_dir / f"{name}.obj")
