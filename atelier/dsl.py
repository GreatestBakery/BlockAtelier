"""Deterministic JSON operations for Minecraft geometry and transformed components."""
import math
from .voxel import VoxelGrid
from .blocks import parse_state, format_state

MAX_COORD = 512
MAX_BLOCKS = 3_000_000

GUIDE = r"""
BUILD PROGRAM FORMAT (JSON)
{
  "name": "short title",
  "palette": {"wall": "stone_bricks", "roof": "dark_oak_stairs", ...},   // optional aliases, use as "$wall"
  "ops": [ ...operations executed in order, later ops overwrite earlier ones... ]
}
Coordinates are integers: x = east, y = up, z = south. Ground level is y=0. Keep everything at x,y,z >= 0.
Block strings: "oak_planks", "oak_stairs[facing=east,half=bottom]", "oak_log[axis=x]", or a palette alias "$wall".
Use "air" to carve/remove. Only use block ids that exist in the target Minecraft version.

OPERATIONS
{"op":"box","from":[x,y,z],"to":[x,y,z],"block":B,"mode":"solid|hollow|walls|frame"}
      solid = filled; hollow = 6-sided shell; walls = 4 vertical sides only; frame = 12 edges only.
{"op":"sphere","center":[x,y,z],"radius":r | [rx,ry,rz],"block":B,"hollow":false,"half":"top|bottom|none"}
{"op":"cylinder","base":[x,y,z],"radius":r | [ra,rb],"height":h,"axis":"y","block":B,"hollow":false}
{"op":"cone","base":[x,y,z],"radius":r,"height":h,"block":B,"hollow":false}
{"op":"pyramid","from":[x,y,z],"to":[x,y,z],"block":B,"hollow":false}        // footprint from..to at y, shrinks by 1 per layer
{"op":"roof","from":[x,y,z],"to":[x,y,z],"style":"gable|hip","ridge":"x|z","block":B_full,
      "stairs":B_stairs(optional, auto-oriented),"overhang":0,"gable":B(optional, fills the triangular end walls)}
      footprint is the x/z range, roof starts at y of "from" and rises.
{"op":"line","from":[x,y,z],"to":[x,y,z],"block":B}
{"op":"set","at":[[x,y,z],...],"block":B}
{"op":"pattern","origin":[x,y,z],"plane":"xz|xy|zy","rows":["##..##", ...],"legend":{"#":B,"g":B2},"depth":1}
      xz: floor plan, rows go south (+z), columns go east (+x), depth extrudes up.
      xy: facade, FIRST ROW IS THE TOP, columns go east (+x), depth extrudes south (+z).
      zy: facade, first row is the top, columns go south (+z), depth extrudes east (+x).
      '.' or ' ' = leave untouched, '_' = air.
{"op":"replace","from":[x,y,z],"to":[x,y,z],"find":B | [B,...],"block":B}
{"op":"door","at":[x,y,z],"block":"oak_door","facing":"north|south|east|west","hinge":"left|right"}   // places both halves
{"op":"group","ops":[...],"translate":[dx,dy,dz],"rotate_y":0|90|180|270,"pivot":[x,z],
      "mirror":{"axis":"x|z","at":c},"repeat":{"count":n,"step":[dx,dy,dz]}}
      Sub-ops are built in isolation, then rotated (about pivot), mirrored (a mirrored COPY is added, the original is kept),
      translated, and stamped `count` times. Directional block states (facing/axis) are rotated/mirrored for you.

TIPS
- Build big masses first (box/cylinder), then carve interiors/openings with "air", then add detail (windows, trim, roof, props).
- Use "group" + "repeat" for windows, columns, battlements; use "mirror" for symmetric facades.
- Fences, walls, glass panes and iron bars auto-connect to neighbours; you don't need to set north/east/... properties.
- Give depth: frames, pilasters, overhangs, mixed textures (e.g. stone_bricks + cracked/mossy variants), not flat walls.
"""

_FACING_CW = ["north", "east", "south", "west"]


def _rot_props(props, k):
    """绕 y 轴顺时针转 k*90° (从上往下看)。"""
    if not props or k % 4 == 0: return props
    p = dict(props)
    if p.get("facing") in _FACING_CW:
        p["facing"] = _FACING_CW[(_FACING_CW.index(p["facing"]) + k) % 4]
    if p.get("axis") in ("x", "z") and k % 2:
        p["axis"] = "z" if p["axis"] == "x" else "x"
    if "rotation" in p and p["rotation"].isdigit():
        p["rotation"] = str((int(p["rotation"]) + 4 * k) % 16)
    side = {d: props[d] for d in _FACING_CW if d in props}
    for d, v in side.items():
        p[_FACING_CW[(_FACING_CW.index(d) + k) % 4]] = v
    return p


def _mirror_props(props, axis):
    if not props: return props
    p = dict(props)
    a, b = ("east", "west") if axis == "x" else ("south", "north")
    if p.get("facing") == a: p["facing"] = b
    elif p.get("facing") == b: p["facing"] = a
    if a in props or b in props:
        va, vb = props.get(a), props.get(b)
        if vb is not None: p[a] = vb
        if va is not None: p[b] = va
    if "shape" in p and ("left" in p["shape"] or "right" in p["shape"]):
        p["shape"] = p["shape"].replace("left", "\0").replace("right", "left").replace("\0", "right")
    if p.get("hinge") in ("left", "right"):
        p["hinge"] = "right" if p["hinge"] == "left" else "left"
    if "rotation" in p and p["rotation"].isdigit():
        r = int(p["rotation"]); p["rotation"] = str((-r) % 16 if axis == "x" else (8 - r) % 16)
    return p


def _xform_state(state, fn, arg):
    if "[" not in state: return state
    bid, props = parse_state(state)
    return format_state(bid, fn(props, arg))


class DSLError(Exception):
    pass


class Interpreter:
    def __init__(self, program):
        if not isinstance(program, dict) or not isinstance(program.get("ops"), list):
            raise DSLError("指令必须是含 ops 数组的 JSON 对象")
        self.palette = {str(k).lstrip("$"): v for k, v in (program.get("palette") or {}).items()}
        self.program = program
        self.errors = []      # [(op 路径, 信息)]

    # ---- helpers -------------------------------------------------
    def blk(self, b):
        if not isinstance(b, str) or not b: raise DSLError(f"block 必须是字符串: {b!r}")
        for _ in range(4):
            if b.startswith("$"):
                key = b[1:]
                if key not in self.palette: raise DSLError(f"palette 里没有 {b}")
                b = self.palette[key]
            else: break
        b = b.strip().lower()
        if b in ("air", "minecraft:air", "cave_air"): return "minecraft:air"
        bid, props = parse_state(b)
        return format_state(bid, props)

    @staticmethod
    def vec(v, n=3, name="坐标"):
        if not isinstance(v, (list, tuple)) or len(v) != n: raise DSLError(f"{name} 需要 {n} 个数: {v!r}")
        out = [int(round(float(c))) for c in v]
        if any(abs(c) > MAX_COORD for c in out): raise DSLError(f"{name} 超出范围 ±{MAX_COORD}: {v}")
        return out

    def rng(self, op):
        a, b = self.vec(op.get("from"), name="from"), self.vec(op.get("to"), name="to")
        return [min(p, q) for p, q in zip(a, b)], [max(p, q) for p, q in zip(a, b)]

    # ---- ops -----------------------------------------------------
    def op_box(self, g, op):
        lo, hi = self.rng(op); b = self.blk(op.get("block")); mode = op.get("mode", "solid")
        if mode not in ("solid", "hollow", "walls", "frame"): raise DSLError(f"box.mode 无效: {mode}")
        for x in range(lo[0], hi[0] + 1):
            ex = x in (lo[0], hi[0])
            for y in range(lo[1], hi[1] + 1):
                ey = y in (lo[1], hi[1])
                for z in range(lo[2], hi[2] + 1):
                    ez = z in (lo[2], hi[2])
                    if (mode == "solid" or (mode == "hollow" and (ex or ey or ez)) or
                            (mode == "walls" and (ex or ez)) or (mode == "frame" and (ex + ey + ez) >= 2)):
                        g.set(x, y, z, b)

    def op_sphere(self, g, op):
        c = self.vec(op.get("center"), name="center"); b = self.blk(op.get("block"))
        r = op.get("radius", 3)
        r = [float(v) for v in r] if isinstance(r, (list, tuple)) else [float(r)] * 3
        if len(r) != 3 or min(r) < 0 or max(r) > 128: raise DSLError(f"sphere.radius 无效: {op.get('radius')}")
        half = op.get("half", "none"); hollow = bool(op.get("hollow"))
        R = [v + 0.5 for v in r]
        inside = lambda dx, dy, dz, rr: (dx / rr[0]) ** 2 + (dy / rr[1]) ** 2 + (dz / rr[2]) ** 2 <= 1.0
        Ri = [max(v - 1, 0.01) for v in R]
        for dx in range(-math.ceil(r[0]), math.ceil(r[0]) + 1):
            for dy in range(-math.ceil(r[1]), math.ceil(r[1]) + 1):
                if (half == "top" and dy < 0) or (half == "bottom" and dy > 0): continue
                for dz in range(-math.ceil(r[2]), math.ceil(r[2]) + 1):
                    if inside(dx, dy, dz, R) and not (hollow and inside(dx, dy, dz, Ri)):
                        g.set(c[0] + dx, c[1] + dy, c[2] + dz, b)

    def _disc(self, ra, rb, hollow):
        Ra, Rb = ra + 0.5, rb + 0.5
        pts = []
        for da in range(-math.ceil(ra), math.ceil(ra) + 1):
            for db in range(-math.ceil(rb), math.ceil(rb) + 1):
                if (da / Ra) ** 2 + (db / Rb) ** 2 <= 1.0:
                    if hollow and ra >= 1 and rb >= 1 and (da / (Ra - 1)) ** 2 + (db / (Rb - 1)) ** 2 <= 1.0: continue
                    pts.append((da, db))
        return pts

    def op_cylinder(self, g, op):
        c = self.vec(op.get("base"), name="base"); b = self.blk(op.get("block"))
        r = op.get("radius", 3); r = [float(v) for v in r] if isinstance(r, (list, tuple)) else [float(r)] * 2
        h = int(op.get("height", 1)); axis = op.get("axis", "y")
        if h < 1 or h > MAX_COORD or max(r) > 128 or min(r) < 0: raise DSLError("cylinder 的 radius/height 无效")
        for da, db in self._disc(r[0], r[1], bool(op.get("hollow"))):
            for i in range(h):
                if axis == "y": g.set(c[0] + da, c[1] + i, c[2] + db, b)
                elif axis == "x": g.set(c[0] + i, c[1] + da, c[2] + db, b)
                elif axis == "z": g.set(c[0] + da, c[1] + db, c[2] + i, b)
                else: raise DSLError(f"axis 无效: {axis}")

    def op_cone(self, g, op):
        c = self.vec(op.get("base"), name="base"); b = self.blk(op.get("block"))
        r = float(op.get("radius", 3)); h = int(op.get("height", 3))
        if h < 1 or h > MAX_COORD or not 0 <= r <= 128: raise DSLError("cone 的 radius/height 无效")
        for i in range(h):
            ri = r * (1 - i / h)
            for da, db in self._disc(ri, ri, bool(op.get("hollow")) and i < h - 1):
                g.set(c[0] + da, c[1] + i, c[2] + db, b)

    def op_pyramid(self, g, op):
        lo, hi = self.rng(op); b = self.blk(op.get("block")); hollow = bool(op.get("hollow"))
        y, (x0, z0, x1, z1) = lo[1], (lo[0], lo[2], hi[0], hi[2])
        while x0 <= x1 and z0 <= z1:
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    if not hollow or x in (x0, x1) or z in (z0, z1): g.set(x, y, z, b)
            x0 += 1; z0 += 1; x1 -= 1; z1 -= 1; y += 1

    def op_roof(self, g, op):
        lo, hi = self.rng(op); b = self.blk(op.get("block"))
        st = self.blk(op["stairs"]) if op.get("stairs") else None
        gable = self.blk(op["gable"]) if op.get("gable") else None
        oh = int(op.get("overhang", 0)); style = op.get("style", "gable"); ridge = op.get("ridge", "x")
        if style not in ("gable", "hip") or ridge not in ("x", "z"): raise DSLError("roof.style / ridge 无效")
        x0, x1, z0, z1, y = lo[0] - oh, hi[0] + oh, lo[2] - oh, hi[2] + oh, lo[1]
        def stair(facing):
            if not st: return b
            bid, p = parse_state(st); p = dict(p); p["facing"] = facing; p.setdefault("half", "bottom")
            return format_state(bid, p)
        if style == "gable":
            a0, a1 = (z0, z1) if ridge == "x" else (x0, x1)       # 收拢方向
            l0, l1 = (x0, x1) if ridge == "x" else (z0, z1)       # 屋脊方向
            g0, g1 = (lo[0], hi[0]) if ridge == "x" else (lo[2], hi[2])
            put = (lambda l, a, yy, s: g.set(l, yy, a, s)) if ridge == "x" else (lambda l, a, yy, s: g.set(a, yy, l, s))
            f_lo, f_hi = ("south", "north") if ridge == "x" else ("east", "west")
            i = 0
            while a0 + i <= a1 - i:
                al, ar = a0 + i, a1 - i
                for l in range(l0, l1 + 1):
                    if al == ar: put(l, al, y + i, b)
                    else:
                        put(l, al, y + i, stair(f_lo)); put(l, ar, y + i, stair(f_hi))
                if gable:
                    for a in range(al + 1, ar):
                        put(g0, a, y + i, gable); put(g1, a, y + i, gable)
                i += 1
        else:
            i = 0
            while x0 + i <= x1 - i and z0 + i <= z1 - i:
                xa, xb, za, zb = x0 + i, x1 - i, z0 + i, z1 - i
                flat = xa == xb or za == zb
                for x in range(xa, xb + 1):
                    g.set(x, y + i, za, b if flat else stair("south")); g.set(x, y + i, zb, b if flat else stair("north"))
                for z in range(za + (0 if flat else 1), zb + (1 if flat else 0)):
                    g.set(xa, y + i, z, b if flat else stair("east")); g.set(xb, y + i, z, b if flat else stair("west"))
                i += 1

    def op_line(self, g, op):
        a, c = self.vec(op.get("from"), name="from"), self.vec(op.get("to"), name="to"); b = self.blk(op.get("block"))
        n = max(abs(c[i] - a[i]) for i in range(3))
        for i in range(n + 1):
            t = i / n if n else 0
            g.set(*[int(round(a[k] + (c[k] - a[k]) * t)) for k in range(3)], b)

    def op_set(self, g, op):
        b = self.blk(op.get("block")); at = op.get("at")
        if at and isinstance(at[0], (int, float)): at = [at]
        if not at or len(at) > 20000: raise DSLError("set.at 需要坐标数组")
        for p in at: g.set(*self.vec(p, name="at"), b)

    def op_pattern(self, g, op):
        o = self.vec(op.get("origin"), name="origin"); plane = op.get("plane", "xz")
        rows = op.get("rows"); depth = int(op.get("depth", 1))
        if not isinstance(rows, list) or not rows or len(rows) > 256 or not 1 <= depth <= 256: raise DSLError("pattern.rows/depth 无效")
        legend = {k: self.blk(v) for k, v in (op.get("legend") or {}).items()}
        H = len(rows)
        for r, row in enumerate(rows):
            for cidx, ch in enumerate(str(row)):
                if ch in " .": continue
                if ch == "_": b = "minecraft:air"
                elif ch in legend: b = legend[ch]
                else: raise DSLError(f"pattern 里的字符 '{ch}' 不在 legend 中")
                for d in range(depth):
                    if plane == "xz": g.set(o[0] + cidx, o[1] + d, o[2] + r, b)
                    elif plane == "xy": g.set(o[0] + cidx, o[1] + (H - 1 - r), o[2] + d, b)
                    elif plane == "zy": g.set(o[0] + d, o[1] + (H - 1 - r), o[2] + cidx, b)
                    else: raise DSLError(f"pattern.plane 无效: {plane}")

    def op_replace(self, g, op):
        lo, hi = self.rng(op); b = self.blk(op.get("block")); find = op.get("find")
        find = [find] if isinstance(find, str) else (find or [])
        ids = {parse_state(self.blk(f))[0] for f in find}
        for (x, y, z), s in list(g.cells.items()):
            if all(lo[i] <= (x, y, z)[i] <= hi[i] for i in range(3)) and parse_state(s)[0] in ids:
                g.set(x, y, z, b)

    def op_door(self, g, op):
        x, y, z = self.vec(op.get("at"), name="at"); bid, p = parse_state(self.blk(op.get("block", "oak_door")))
        p = dict(p); p["facing"] = op.get("facing", p.get("facing", "north")); p["hinge"] = op.get("hinge", p.get("hinge", "left"))
        g.set(x, y, z, format_state(bid, {**p, "half": "lower"})); g.set(x, y + 1, z, format_state(bid, {**p, "half": "upper"}))

    def op_group(self, g, op, path=""):
        sub = VoxelGrid()
        self.run_ops(sub, op.get("ops") or [], path + "/")
        k = int(op.get("rotate_y", 0)) // 90 % 4
        if k:
            px, pz = (op.get("pivot") or [0, 0])[:2]
            cells = {}
            for (x, y, z), s in sub.cells.items():
                dx, dz = x - px, z - pz
                for _ in range(k): dx, dz = -dz, dx
                cells[(int(px + dx), y, int(pz + dz))] = _xform_state(s, _rot_props, k)
            sub.cells = cells
        m = op.get("mirror")
        if m:
            ax, at = m.get("axis", "x"), float(m.get("at", 0))
            if ax not in ("x", "z"): raise DSLError("mirror.axis 只能是 x 或 z")
            for (x, y, z), s in list(sub.cells.items()):
                q = (int(round(2 * at - x)), y, z) if ax == "x" else (x, y, int(round(2 * at - z)))
                sub.cells.setdefault(q, _xform_state(s, _mirror_props, ax))
        t = self.vec(op.get("translate", [0, 0, 0]), name="translate")
        rep = op.get("repeat") or {}
        n = int(rep.get("count", 1)); step = self.vec(rep.get("step", [0, 0, 0]), name="repeat.step")
        if not 1 <= n <= 512: raise DSLError("repeat.count 需在 1..512")
        for i in range(n):
            for (x, y, z), s in sub.cells.items():
                g.cells[(x + t[0] + step[0] * i, y + t[1] + step[1] * i, z + t[2] + step[2] * i)] = s
        # group 内的 air 雕刻只作用于组内，这是有意的: 组是“预制件”。

    # ---- driver --------------------------------------------------
    def run_ops(self, g, ops, path=""):
        for i, op in enumerate(ops):
            where = f"{path}ops[{i}]"
            try:
                if not isinstance(op, dict): raise DSLError("每条指令必须是对象")
                name = op.get("op")
                fn = getattr(self, "op_" + str(name), None)
                if fn is None: raise DSLError(f"未知指令 op={name!r}")
                if name == "group": fn(g, op, where)
                else: fn(g, op)
                if len(g) > MAX_BLOCKS: raise DSLError(f"方块数超过上限 {MAX_BLOCKS}")
            except (DSLError, ValueError, TypeError, KeyError) as e:
                self.errors.append((where, f"{op.get('op') if isinstance(op, dict) else '?'}: {e}"))

    def run(self):
        g = VoxelGrid()
        self.run_ops(g, self.program["ops"])
        return g


def execute(program):
    """-> (VoxelGrid, [(位置, 错误)])"""
    it = Interpreter(program)
    return it.run(), it.errors
