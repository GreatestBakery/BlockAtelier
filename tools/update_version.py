#!/usr/bin/env python3
"""拉取某个 Minecraft 版本的官方数据，生成本软件需要的“版本档案”。

数据源: misode/mcmeta (由 Mojang 官方 jar 自动导出，每个快照/正式版都有 tag)。
用法:
    python tools/update_version.py latest          # 最新正式版
    python tools/update_version.py 26.3
    python tools/update_version.py 26.4-snapshot-8 # 快照也可以
    python tools/update_version.py 26.3 --from-dir /path/to/mcmeta 镜像目录(离线)

生成 data/versions/<id>/ :
    version.json      版本号 / DataVersion / 资源包格式
    blocks.json       方块 id -> [属性取值表, 默认属性]
    blockstates.json  方块状态 -> 模型 (变体 / multipart)
    models.json       方块模型 (只保留 block/ 下的, 去掉 display)
    atlas.png/.json   方块贴图图集 (16px 网格, 已做群系染色)
    colors.json       每个方块的平均颜色、是否完整不透明方块等 (供体素化配色与预览)
"""
import argparse, io, json, math, os, sys, urllib.request
from pathlib import Path
from PIL import Image
import numpy as np

BASE = "https://raw.githubusercontent.com/misode/mcmeta"
ROOT = Path(__file__).resolve().parent.parent
CELL = 16

GRASS, FOLIAGE, WATER = (145, 189, 89), (119, 171, 47), (63, 118, 228)
SPECIAL_TINT = {"birch_leaves": (128, 167, 85), "spruce_leaves": (97, 153, 97),
                "lily_pad": (32, 128, 48), "water": WATER}


def fetch(ref, path, src_dir=None, binary=False):
    if src_dir:
        data = (Path(src_dir) / ref / path).read_bytes()
    else:
        url = f"{BASE}/{ref}/{path}"
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
    return data if binary else json.loads(data)


def strip_ns(s):
    return s.split(":", 1)[1] if ":" in s else s


def resolve_model(models, name, _depth=0):
    """沿 parent 链合并 textures / elements。"""
    name = strip_ns(name)
    m = models.get(name)
    if m is None or _depth > 12:
        return {"textures": {}, "elements": None}
    out = resolve_model(models, m["parent"], _depth + 1) if "parent" in m else {"textures": {}, "elements": None}
    tex = dict(out["textures"]); tex.update(m.get("textures", {}))
    return {"textures": tex, "elements": m.get("elements", out["elements"])}


def tex_ref(textures, ref):
    for _ in range(10):
        if isinstance(ref, dict):
            ref = ref.get("sprite", "")
        if not ref.startswith("#"):
            return strip_ns(ref)
        ref = textures.get(ref[1:], "")
        if not ref:
            return None
    return None


def first_model(blockstate, defaults):
    """默认状态对应的第一个模型名。"""
    if "variants" in blockstate:
        best = None
        for key, v in blockstate["variants"].items():
            cond = dict(kv.split("=") for kv in key.split(",") if kv)
            if all(defaults.get(k) == val for k, val in cond.items()):
                best = v; break
        if best is None:
            best = next(iter(blockstate["variants"].values()))
        if isinstance(best, list): best = best[0]
        return best["model"]
    if "multipart" in blockstate:
        a = blockstate["multipart"][0]["apply"]
        if isinstance(a, list): a = a[0]
        return a["model"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--from-dir", default=None, help="本地 mcmeta 镜像 (含 <ver>-summary 等子目录)")
    a = ap.parse_args()
    ver = a.version
    if ver == "latest":
        allv = fetch("summary", "versions/data.min.json", a.from_dir)
        ver = next(v["id"] for v in allv if v["type"] == "release")
        print("最新正式版:", ver)
    out = ROOT / "data" / "versions" / ver
    out.mkdir(parents=True, exist_ok=True)

    version = fetch(f"{ver}-summary", "version.json", a.from_dir)
    blocks = fetch(f"{ver}-summary", "blocks/data.min.json", a.from_dir)
    states = fetch(f"{ver}-summary", "assets/block_definition/data.min.json", a.from_dir)
    models_all = fetch(f"{ver}-summary", "assets/model/data.min.json", a.from_dir)
    atlas_idx = fetch(f"{ver}-atlas", "all/data.min.json", a.from_dir)
    atlas_src = Image.open(io.BytesIO(fetch(f"{ver}-atlas", "all/atlas.png", a.from_dir, binary=True))).convert("RGBA")

    models = {}
    for k, m in models_all.items():
        if k.startswith("block/"):
            m = {kk: vv for kk, vv in m.items() if kk in ("parent", "textures", "elements")}
            models[k] = m

    # 哪些贴图会被染色 (面带 tintindex)
    tinted = set()
    for k in models:
        r = resolve_model(models, k)
        for el in r["elements"] or []:
            for f in el.get("faces", {}).values():
                if "tintindex" in f:
                    t = tex_ref(r["textures"], f["texture"])
                    if t: tinted.add(t)

    # 重新打包只含方块贴图的图集
    names = sorted(k for k in atlas_idx if k.startswith("block/"))
    cols = 64                                              # 图集边长取 2 的幂，mipmap 时各格不串色
    rows = math.ceil(len(names) / cols)
    pot = 1 << max(0, (rows * CELL - 1).bit_length())
    atlas = Image.new("RGBA", (cols * CELL, pot), (0, 0, 0, 0))
    amap, tstats = {}, {}
    for i, n in enumerate(names):
        x, y, w, h = atlas_idx[n]
        im = atlas_src.crop((x, y, x + w, y + min(w, h)))   # 动画贴图取第一帧
        if im.size != (CELL, CELL):
            im = im.resize((CELL, CELL), Image.NEAREST)
        if n in tinted and "redstone" not in n and "stem" not in n:
            short = n.split("/", 1)[1]
            tint = next((c for key, c in SPECIAL_TINT.items() if short.startswith(key)), None)
            if tint is None:
                tint = FOLIAGE if ("leaves" in short or "vine" in short) else GRASS
            arr = np.asarray(im).astype(np.float32)
            arr[..., :3] *= np.array(tint, np.float32) / 255.0
            im = Image.fromarray(arr.astype(np.uint8), "RGBA")
        cx, cy = (i % cols) * CELL, (i // cols) * CELL
        atlas.paste(im, (cx, cy))
        amap[n] = [cx, cy]
        arr = np.asarray(im).astype(np.float32)
        al = arr[..., 3]
        wsum = al.sum()
        rgb = (arr[..., :3] * al[..., None]).sum((0, 1)) / wsum if wsum > 0 else np.zeros(3)
        tstats[n] = {"rgb": [int(round(v)) for v in rgb], "cover": float((al > 16).mean()),
                     "translucent": bool(((al > 16) & (al < 240)).mean() > 0.2)}
    atlas.save(out / "atlas.png")

    # 每个方块的颜色与形状分类
    colors = {}
    for bid, (props, defaults) in blocks.items():
        bs = states.get(bid)
        entry = {"rgb": [128, 128, 128], "top": None, "side": None, "full": False, "opaque": False,
                 "translucent": False, "shape": "none"}
        mname = first_model(bs, defaults) if bs else None
        if mname:
            r = resolve_model(models, mname)
            els = r["elements"] or []
            def col(face_names):
                for el in els:
                    for fn in face_names:
                        f = el.get("faces", {}).get(fn)
                        if f:
                            t = tex_ref(r["textures"], f["texture"])
                            if t in tstats: return t
                return None
            top_t, side_t = col(["up"]), col(["north", "south", "east", "west"])
            if not els:
                top_t = side_t = tex_ref(r["textures"], "#particle")
                if top_t not in tstats: top_t = side_t = None
                entry["shape"] = "entity"
            if top_t or side_t:
                top_t = top_t or side_t; side_t = side_t or top_t
                entry["top"], entry["side"] = tstats[top_t]["rgb"], tstats[side_t]["rgb"]
                entry["rgb"] = [int(round((a_ + 2 * b_) / 3)) for a_, b_ in zip(entry["top"], entry["side"])]
                entry["translucent"] = tstats[side_t]["translucent"]
                full = (len(els) >= 1 and els[0].get("from") == [0, 0, 0] and els[0].get("to") == [16, 16, 16]
                        and "rotation" not in els[0] and len(els[0].get("faces", {})) == 6)
                entry["full"] = bool(full)
                texs = {tex_ref(r["textures"], f["texture"]) for f in els[0]["faces"].values()} if full else set()
                entry["opaque"] = bool(full and all(t in tstats and tstats[t]["cover"] > 0.999 and not tstats[t]["translucent"] for t in texs))
                if els:
                    if full: entry["shape"] = "full"
                    elif "slab" in bid: entry["shape"] = "slab"
                    elif "stairs" in bid: entry["shape"] = "stairs"
                    else:
                        vol = sum(max(0, (e["to"][0]-e["from"][0]))*max(0, (e["to"][1]-e["from"][1]))*max(0, (e["to"][2]-e["from"][2])) for e in els) / 4096
                        entry["shape"] = "partial" if vol > 0.2 else "thin"
        if bid in ("water", "lava"):
            t = "block/water_still" if bid == "water" else "block/lava_still"
            c = tstats.get(t, {"rgb": [63, 118, 228]})["rgb"]
            entry.update(rgb=c, top=c, side=c, shape="fluid", translucent=(bid == "water"))
        colors[bid] = entry

    json.dump(version, open(out / "version.json", "w"), indent=1)
    json.dump(blocks, open(out / "blocks.json", "w"), separators=(",", ":"))
    json.dump({k: v for k, v in states.items() if k in blocks}, open(out / "blockstates.json", "w"), separators=(",", ":"))
    json.dump(models, open(out / "models.json", "w"), separators=(",", ":"))
    json.dump({"cell": CELL, "size": list(atlas.size), "tex": amap,
               "translucent": sorted(n for n, s in tstats.items() if s["translucent"])},
              open(out / "atlas.json", "w"), separators=(",", ":"))
    json.dump(colors, open(out / "colors.json", "w"), separators=(",", ":"))
    n_full = sum(1 for c in colors.values() if c["opaque"])
    print(f"完成 {ver}: DataVersion={version['data_version']} 方块={len(blocks)} 贴图={len(names)} 完整不透明方块={n_full} -> {out}")


if __name__ == "__main__":
    main()
