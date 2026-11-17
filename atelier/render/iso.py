"""Flat-color isometric previews and four-angle contact sheets."""
import numpy as np
from PIL import Image, ImageDraw
from ..blocks import parse_state

_SHADE = {"top": 1.18, "left": 0.96, "right": 0.74}


def render_iso(grid, reg, view=0, size=768, bg=(24, 26, 32, 255), pad=24):
    """view: 0..3，相机依次绕建筑转 90°。返回 PIL.Image。"""
    pal, arr, _ = grid.to_dense()
    arr = np.rot90(arr, k=view % 4, axes=(0, 2)).copy()       # 只转体素，不转朝向属性: 预览足够
    X, Y, Z = arr.shape
    info = [None] + [reg.info(parse_state(s)[0]) for s in pal[1:]]
    opaque = np.array([False] + [bool(i.get("opaque")) for i in info[1:]])
    occ = np.pad(opaque[arr], 1)
    s = max(1.0, min((size - 2 * pad) / max(1, X + Z), (size - 2 * pad) * 2 / max(1, X + Z + 2 * Y)))
    W = int((X + Z) * s + 2 * pad); H = int((X + Z) * s / 2 + Y * s + 2 * pad)
    img = Image.new("RGBA", (W, H), bg)
    drw = ImageDraw.Draw(img, "RGBA")
    ox, oy = pad + Z * s, pad + Y * s
    P = lambda x, y, z: (ox + (x - z) * s, oy + (x + z) * s / 2 - y * s)
    xs, ys, zs = np.nonzero(arr)
    order = np.argsort(xs + ys + zs, kind="stable")
    for i in order.tolist():
        x, y, z = int(xs[i]), int(ys[i]), int(zs[i])
        inf = info[arr[x, y, z]]
        if not inf or inf.get("shape") == "none": continue
        st, sx, sz = occ[x + 1, y + 2, z + 1], occ[x + 2, y + 1, z + 1], occ[x + 1, y + 1, z + 2]
        if st and sx and sz: continue
        shape = inf.get("shape", "full")
        h = 0.5 if shape == "slab" else (0.875 if shape == "fluid" else 1.0)
        m = 0.0
        if shape == "thin": m, h = 0.3, 0.8
        elif shape == "entity": m, h = 0.08, 0.85
        a = 150 if inf.get("translucent") or "glass" in pal[arr[x, y, z]] else 255
        top, side = inf.get("top") or inf["rgb"], inf.get("side") or inf["rgb"]
        x0, x1, z0, z1, y1 = x + m, x + 1 - m, z + m, z + 1 - m, y + h
        if not st or h < 1 or m:
            c = tuple(min(255, int(v * _SHADE["top"])) for v in top) + (a,)
            drw.polygon([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], fill=c)
        if not sz or m:
            c = tuple(min(255, int(v * _SHADE["left"])) for v in side) + (a,)
            drw.polygon([P(x0, y1, z1), P(x1, y1, z1), P(x1, y, z1), P(x0, y, z1)], fill=c)
        if not sx or m:
            c = tuple(min(255, int(v * _SHADE["right"])) for v in side) + (a,)
            drw.polygon([P(x1, y1, z0), P(x1, y1, z1), P(x1, y, z1), P(x1, y, z0)], fill=c)
    if max(W, H) > size * 1.5:
        img.thumbnail((int(size * 1.5),) * 2, Image.LANCZOS)
    return img


def render_views(grid, reg, out_dir, size=768, views=(0, 1, 2, 3)):
    paths = []
    for v in views:
        p = f"{out_dir}/iso_{v}.png"
        render_iso(grid, reg, v, size).save(p)
        paths.append(p)
    return paths


def contact_sheet(paths, out, cell=512):
    ims = [Image.open(p).convert("RGBA") for p in paths]
    cols = 2 if len(ims) > 1 else 1; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (24, 26, 32, 255))
    for i, im in enumerate(ims):
        im.thumbnail((cell, cell), Image.LANCZOS)
        sheet.paste(im, ((i % cols) * cell + (cell - im.width) // 2, (i // cols) * cell + (cell - im.height) // 2))
    sheet.save(out)
    return out
