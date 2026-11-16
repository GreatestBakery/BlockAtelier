"""读入已有的结构文件 (.litematic / .schem v2,v3 / 原版 .nbt)，用作参考或直接入库、转格式、渲染。"""
from pathlib import Path
import numpy as np
import nbtlib
from .voxel import VoxelGrid
from .blocks import format_state


def _read_varints(buf, n):
    out = np.zeros(n, np.int32); i = 0; k = 0
    b = bytes(np.asarray(buf, dtype=np.int8).tobytes())
    while k < n and i < len(b):
        v = 0; shift = 0
        while True:
            c = b[i]; i += 1
            v |= (c & 0x7F) << shift
            if not c & 0x80: break
            shift += 7
        out[k] = v; k += 1
    return out


def read_schem(path):
    f = nbtlib.load(str(path), gzipped=True)
    root = f["Schematic"] if "Schematic" in f else f
    W, H, L = int(root["Width"]), int(root["Height"]), int(root["Length"])
    if "Blocks" in root:
        palette, data = root["Blocks"]["Palette"], root["Blocks"]["Data"]
    else:
        palette, data = root["Palette"], root["BlockData"]
    names = {int(v): k for k, v in palette.items()}
    idx = _read_varints(data, W * H * L).reshape(H, L, W)
    g = VoxelGrid()
    ys, zs, xs = np.nonzero(np.vectorize(lambda i: not names.get(int(i), "minecraft:air").endswith(":air"))(idx)) if idx.size else ([], [], [])
    for y, z, x in zip(ys, zs, xs):
        g.cells[(int(x), int(y), int(z))] = names[int(idx[y, z, x])]
    return g, {"format": f"sponge v{int(root.get('Version', 2))}", "data_version": int(root.get("DataVersion", 0))}


def read_litematic(path):
    from litemapy import Schematic
    sch = Schematic.load(str(path))
    g = VoxelGrid()
    for reg in sch.regions.values():
        for x in reg.xrange():
            for y in reg.yrange():
                for z in reg.zrange():
                    b = reg[x, y, z]
                    if b.id == "minecraft:air": continue
                    props = {k: v for k, v in b.properties()} if callable(getattr(b, "properties", None)) else {}
                    g.cells[(reg.x + x, reg.y + y, reg.z + z)] = format_state(b.id.split(":", 1)[1], props)
    return g, {"format": f"litematic v{int(sch.lm_version)}", "data_version": int(sch.mc_version), "name": sch.name}


def read_structure_nbt(path):
    f = nbtlib.load(str(path), gzipped=True)
    pal = []
    for p in f["palette"]:
        props = {str(k): str(v) for k, v in p.get("Properties", {}).items()}
        pal.append(format_state(str(p["Name"]).split(":", 1)[1], props))
    g = VoxelGrid()
    for b in f["blocks"]:
        s = pal[int(b["state"])]
        if not s.endswith(":air"):
            x, y, z = (int(v) for v in b["pos"])
            g.cells[(x, y, z)] = s
    return g, {"format": "vanilla structure", "data_version": int(f.get("DataVersion", 0))}


def read_any(path):
    ext = Path(path).suffix.lower()
    if ext == ".litematic": return read_litematic(path)
    if ext in (".schem", ".schematic"): return read_schem(path)
    if ext == ".nbt": return read_structure_nbt(path)
    raise ValueError(f"不支持的结构文件: {ext}")


def summarize(grid, name="", top=14):
    """给大模型看的参考摘要: 尺寸、用料比例。刻意不给逐格数据 —— 参考是为了借鉴比例和配色，不是复制。"""
    size = grid.size(); total = max(1, len(grid))
    cnt = {}
    for s in grid.cells.values():
        b = s.split("[")[0].replace("minecraft:", "")
        cnt[b] = cnt.get(b, 0) + 1
    tops = sorted(cnt.items(), key=lambda kv: -kv[1])[:top]
    return {"name": name, "size_xyz": list(size), "blocks": len(grid),
            "materials": [{"block": b, "share": round(n / total, 3)} for b, n in tops]}
