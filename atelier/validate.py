"""Block-state normalization, neighbor connections, and structural validation."""
import numpy as np
from scipy import ndimage
from .blocks import parse_state, format_state
from .voxel import VoxelGrid

GRAVITY = ("sand", "red_sand", "gravel", "anvil", "dragon_egg", "scaffolding")


def _connect_kind(bid):
    if bid.endswith("_fence"): return "fence"
    if bid.endswith("_wall") and "sign" not in bid and "banner" not in bid and "head" not in bid and "skull" not in bid and "fan" not in bid and "torch" not in bid: return "wall"
    if bid.endswith("glass_pane") or bid in ("iron_bars",) or bid.endswith("_bars"): return "pane"
    return None


def normalize_blocks(grid, reg):
    """把所有方块规范到目标版本。未知方块会被删除并记为错误。"""
    out, errors, warns = VoxelGrid(), {}, {}
    for pos, s in grid.cells.items():
        canon, w = reg.normalize(s)
        if canon is None:
            errors[w[0]] = errors.get(w[0], 0) + 1
            continue
        for m in w: warns[m] = warns.get(m, 0) + 1
        if not canon.endswith(":air"): out.cells[pos] = canon
    return out, [f"{m} ×{n}" for m, n in errors.items()], [f"{m} ×{n}" for m, n in warns.items()]


def autoconnect(grid, reg):
    """栅栏/墙/玻璃板按邻居补全连接属性 (粘贴类工具不会触发方块更新，所以必须写进文件)。"""
    dirs = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
    changed = 0
    for (x, y, z), s in list(grid.cells.items()):
        bid, props = parse_state(s)
        kind = _connect_kind(bid)
        if not kind or bid not in reg: continue
        allowed = reg.blocks[bid][0]
        p = dict(props); n_conn = 0
        for d, (dx, dy, dz) in dirs.items():
            if d not in allowed: continue
            nb = grid.get(x + dx, y + dy, z + dz)
            conn = False
            if nb:
                nid = parse_state(nb)[0]
                conn = reg.info(nid).get("opaque", False) or _connect_kind(nid) == kind or \
                       (kind in ("pane", "wall") and _connect_kind(nid) in ("pane", "wall")) or \
                       (kind == "fence" and nid.endswith("fence_gate"))
            n_conn += conn
            if kind == "wall":
                p[d] = ("low" if conn else "none")
            else:
                p[d] = "true" if conn else "false"
        if kind == "wall" and "up" in allowed:
            straight = (p.get("north") != "none" and p.get("south") != "none" and p.get("east") == "none" and p.get("west") == "none") or \
                       (p.get("east") != "none" and p.get("west") != "none" and p.get("north") == "none" and p.get("south") == "none")
            above = grid.get(x, y + 1, z)
            p["up"] = "false" if (straight and not above) else "true"
        ns = format_state(bid, p)
        if ns != s:
            grid.cells[(x, y, z)] = ns; changed += 1
    return changed


def structure_checks(grid, reg, limits=None):
    """-> (errors, warnings, stats)"""
    errors, warns = [], []
    if len(grid) == 0:
        return ["结构为空: 没有放置任何方块"], [], {"blocks": 0, "size": [0, 0, 0]}
    size = grid.size()
    stats = {"blocks": len(grid), "size": list(size), "palette": len(grid.counts())}
    lim = limits or {}
    mx = lim.get("max_size")
    if mx and any(s > m for s, m in zip(size, mx)):
        errors.append(f"尺寸 {size[0]}x{size[1]}x{size[2]} (x,y,z) 超过要求的上限 {mx[0]}x{mx[1]}x{mx[2]}")
    pal, arr, lo = grid.to_dense()
    occ = arr > 0
    lab, n = ndimage.label(occ, structure=np.ones((3, 3, 3)))
    if n > 1:
        ground = set(np.unique(lab[:, 0, :])) - {0}
        floating = []
        for i, sl in enumerate(ndimage.find_objects(lab), start=1):
            if i in ground or sl is None: continue
            cnt = int((lab[sl] == i).sum())
            floating.append((cnt, [int(sl[k].start + lo[k]) for k in range(3)]))
        floating.sort(reverse=True)
        if floating:
            tot = sum(c for c, _ in floating)
            ex = "; ".join(f"{c} 块 @ {p}" for c, p in floating[:4])
            (errors if tot > 0.25 * len(grid) else warns).append(
                f"有 {len(floating)} 处悬空的独立部件 (共 {tot} 块，不接地也不与主体相连): {ex}")
        stats["components"] = n
    fall = 0; lone_doors = 0
    for (x, y, z), s in grid.cells.items():
        bid, props = parse_state(s)
        if (bid in GRAVITY or bid.endswith("concrete_powder")) and y > lo[1] and grid.get(x, y - 1, z) is None:
            fall += 1
        if bid.endswith("_door"):
            other = grid.get(x, y + 1, z) if props.get("half", "lower") == "lower" else grid.get(x, y - 1, z)
            if not other or parse_state(other)[0] != bid: lone_doors += 1
    if fall: warns.append(f"{fall} 个受重力方块下方悬空 (沙/沙砾/混凝土粉末会掉落)")
    if lone_doors: warns.append(f"{lone_doors} 个门只有半扇 (请用 door 指令)")
    filled = occ.sum() / occ.size
    stats["fill_ratio"] = round(float(filled), 3)
    if len(grid.counts()) == 1 and len(grid) > 200:
        warns.append("整座建筑只用了 1 种方块，缺少材质层次")
    return errors, warns, stats


def validate(grid, reg, limits=None):
    """完整流程。返回 (规整后的网格, 报告 dict)。"""
    g, e1, w1 = normalize_blocks(grid, reg)
    g = g.normalized()
    n_conn = autoconnect(g, reg)
    e2, w2, stats = structure_checks(g, reg, limits)
    stats["autoconnected"] = n_conn
    return g, {"errors": e1 + e2, "warnings": w1 + w2, "stats": stats}
