"""Offline rule-based building examples for demonstrations and tests."""
import json, re


def _size(text, default=(21, 24, 21)):
    m = re.search(r"MAX_SIZE\s*=\s*\[(\d+),\s*(\d+),\s*(\d+)\]", text)
    return tuple(int(v) for v in m.groups()) if m else default


def _kind(text):
    t = text.lower()
    if re.search(r"塔|tower|灯塔|城堡|castle", t): return "tower"
    if re.search(r"亭|寺|pagoda|temple|pavilion|神社|shrine", t): return "pavilion"
    return "house"


def _house(sx, sy, sz):
    w, d = min(sx - 2, 15) | 1, min(sz - 2, 11) | 1
    h = max(4, min(6, sy - (d // 2) - 4))
    x0, z0 = 1, 1; x1, z1 = x0 + w - 1, z0 + d - 1; cx = (x0 + x1) // 2
    return {"name": "石砖小屋", "palette": {"wall": "stone_bricks", "trim": "spruce_log", "roof": "dark_oak_stairs", "floor": "spruce_planks"},
            "ops": [
                {"op": "box", "from": [0, 0, 0], "to": [x1 + 1, 0, z1 + 1], "block": "cobblestone"},
                {"op": "box", "from": [x0, 1, z0], "to": [x1, h, z1], "block": "$wall", "mode": "walls"},
                {"op": "box", "from": [x0, 0, z0], "to": [x1, 0, z1], "block": "$floor"},
                {"op": "group", "ops": [{"op": "box", "from": [x0, 1, z0], "to": [x0, h, z0], "block": "$trim"}],
                 "mirror": {"axis": "x", "at": cx}},
                {"op": "group", "ops": [{"op": "box", "from": [x0, 1, z1], "to": [x0, h, z1], "block": "$trim"}],
                 "mirror": {"axis": "x", "at": cx}},
                {"op": "box", "from": [x0, h + 1, z0], "to": [x1, h + 1, z1], "block": "spruce_log[axis=x]", "mode": "walls"},
                {"op": "roof", "from": [x0, h + 2, z0], "to": [x1, h + 2, z1], "style": "gable", "ridge": "x",
                 "block": "dark_oak_planks", "stairs": "$roof", "overhang": 1, "gable": "spruce_planks"},
                {"op": "group", "ops": [{"op": "box", "from": [x0 + 2, 2, z1], "to": [x0 + 3, 3, z1], "block": "glass_pane"}],
                 "mirror": {"axis": "x", "at": cx}},
                {"op": "box", "from": [x0, 2, z0 + 2], "to": [x0, 3, z1 - 2], "block": "glass_pane"},
                {"op": "box", "from": [x1, 2, z0 + 2], "to": [x1, 3, z1 - 2], "block": "glass_pane"},
                {"op": "set", "at": [cx, 1, z1], "block": "air"},
                {"op": "door", "at": [cx, 1, z1], "block": "spruce_door", "facing": "south"},
                {"op": "set", "at": [[cx - 1, 3, z1 + 1], [cx + 1, 3, z1 + 1]], "block": "wall_torch[facing=south]"},
                {"op": "set", "at": [cx, 1, z1 + 1], "block": "air"},
            ]}


def _tower(sx, sy, sz):
    r = max(3, min(6, (min(sx, sz) - 5) // 2)); c = r + 2; h = max(10, min(sy - r - 6, 26))
    return {"name": "圆形石塔", "palette": {"wall": "stone_bricks", "accent": "polished_andesite", "roof": "deepslate_tiles"},
            "ops": [
                {"op": "cylinder", "base": [c, 0, c], "radius": r + 1, "height": 1, "block": "cobblestone"},
                {"op": "cylinder", "base": [c, 1, c], "radius": r, "height": h, "block": "$wall", "hollow": True},
                {"op": "cylinder", "base": [c, 1, c], "radius": r - 1, "height": 1, "block": "spruce_planks"},
                {"op": "group", "ops": [{"op": "cylinder", "base": [c, 6, c], "radius": r, "height": 1, "block": "$accent", "hollow": True}],
                 "repeat": {"count": max(1, (h - 6) // 6 + 1), "step": [0, 6, 0]}},
                {"op": "cylinder", "base": [c, h + 1, c], "radius": r + 1, "height": 1, "block": "$accent"},
                {"op": "cylinder", "base": [c, h + 2, c], "radius": r + 1, "height": 1, "block": "stone_brick_wall", "hollow": True},
                {"op": "cone", "base": [c, h + 2, c], "radius": r - 0.5, "height": r + 3, "block": "$roof"},
                {"op": "group", "ops": [{"op": "box", "from": [c, 4, c - r], "to": [c, 5, c - r], "block": "glass_pane"}],
                 "repeat": {"count": max(1, (h - 5) // 6 + 1), "step": [0, 6, 0]}},
                {"op": "group", "ops": [{"op": "box", "from": [c - r, 4, c], "to": [c - r, 5, c], "block": "glass_pane"}],
                 "mirror": {"axis": "x", "at": c}, "repeat": {"count": max(1, (h - 5) // 6 + 1), "step": [0, 6, 0]}},
                {"op": "box", "from": [c, 1, c + r], "to": [c, 2, c + r], "block": "air"},
                {"op": "door", "at": [c, 1, c + r], "block": "oak_door", "facing": "south"},
            ]}


def _pavilion(sx, sy, sz):
    w = min(min(sx, sz) - 4, 13) | 1; a, b = 2, 2 + w - 1; c = (a + b) // 2
    return {"name": "朱红凉亭", "palette": {"pillar": "mangrove_log", "roof": "dark_prismarine_stairs", "base": "smooth_stone"},
            "ops": [
                {"op": "box", "from": [a - 1, 0, a - 1], "to": [b + 1, 0, b + 1], "block": "$base"},
                {"op": "box", "from": [a, 1, a], "to": [b, 1, b], "block": "polished_andesite"},
                {"op": "group", "ops": [{"op": "group", "ops": [{"op": "box", "from": [a, 2, a], "to": [a, 6, a], "block": "$pillar"}],
                                         "mirror": {"axis": "x", "at": c}}], "mirror": {"axis": "z", "at": c}},
                {"op": "box", "from": [a, 7, a], "to": [b, 7, b], "block": "mangrove_planks", "mode": "walls"},
                {"op": "box", "from": [a, 2, a], "to": [b, 2, b], "block": "mangrove_fence", "mode": "walls"},
                {"op": "box", "from": [c - 1, 2, b], "to": [c + 1, 2, b], "block": "air"},
                {"op": "group", "ops": [{"op": "box", "from": [a, 2, a], "to": [a, 6, a], "block": "$pillar"}], "mirror": {"axis": "x", "at": c}},
                {"op": "group", "ops": [{"op": "box", "from": [a, 2, b], "to": [a, 6, b], "block": "$pillar"}], "mirror": {"axis": "x", "at": c}},
                {"op": "roof", "from": [a, 6, a], "to": [b, 6, b], "style": "hip", "block": "dark_prismarine", "stairs": "$roof", "overhang": 2},
                {"op": "set", "at": [c, 7 + (w + 4) // 2, c], "block": "gold_block"},
                {"op": "set", "at": [c, 2, c], "block": "lantern"},
            ]}


class MockClient:
    def __init__(self, cfg): self.cfg = cfg

    def chat(self, system, messages, task=None):
        text = "\n".join(m["text"] for m in messages if m["role"] == "user")
        req = re.search(r"USER REQUEST:\s*(.*?)(?:\n[A-Z_ ]+:|\Z)", text, re.S)
        want = req.group(1) if req else text
        sx, sy, sz = _size(text); kind = _kind(want)
        if task == "brief":
            return json.dumps({"title": {"tower": "圆形石塔", "pavilion": "朱红凉亭", "house": "石砖小屋"}[kind],
                               "concept": f"[离线模拟] 按关键词选用原型: {kind}", "style": "vanilla medieval",
                               "size": [sx, sy, sz], "palette": {}, "components": [{"name": "main", "description": kind}],
                               "search_queries": [f"minecraft {kind} build"]}, ensure_ascii=False)
        if task in ("program", "repair"):
            return json.dumps({"tower": _tower, "pavilion": _pavilion, "house": _house}[kind](sx, sy, sz), ensure_ascii=False)
        if task == "critique":
            return json.dumps({"verdict": "ok", "notes": ["[离线模拟] 未做视觉评审"]}, ensure_ascii=False)
        if task == "remap":
            return json.dumps({"mapping": {}, "notes": "[离线模拟] 保持原配色"}, ensure_ascii=False)
        return "{}"
