"""Versioned block lookup, property normalization, aliases, and palette selection."""
import difflib, json, re
from functools import lru_cache
from pathlib import Path
from . import config

AIR = "minecraft:air"
_STATE_RE = re.compile(r"^\s*([a-z0-9_.:\-/]+)\s*(?:\[(.*)\])?\s*$")

# 历史改名 + 大模型常见的“想当然”写法。只有当旧名不在目标版本、新名在时才生效。
ALIASES = {
    "grass": "short_grass", "grass_path": "dirt_path", "chain": "iron_chain",
    "log": "oak_log", "planks": "oak_planks", "wood_planks": "oak_planks", "wooden_planks": "oak_planks",
    "wool": "white_wool", "leaves": "oak_leaves", "brick": "bricks", "brick_block": "bricks",
    "stone_brick": "stone_bricks", "wooden_door": "oak_door", "door": "oak_door", "fence": "oak_fence",
    "bed": "red_bed", "stained_glass": "white_stained_glass", "concrete": "white_concrete",
    "sign": "oak_sign", "snow_layer": "snow", "wooden_slab": "oak_slab", "wooden_stairs": "oak_stairs",
    "trapdoor": "oak_trapdoor", "carpet": "white_carpet", "banner": "white_banner", "lantern_block": "lantern",
    "stone_brick_wall": "stone_brick_wall", "cobble": "cobblestone", "glowstone_block": "glowstone",
    "quartz": "quartz_block", "smooth_quartz_block": "smooth_quartz", "red_brick": "bricks",
}


def parse_state(s):
    """'minecraft:oak_stairs[facing=east]' -> ('oak_stairs', {'facing': 'east'})"""
    m = _STATE_RE.match(str(s).lower())
    if not m:
        raise ValueError(f"无法解析方块: {s!r}")
    bid = m.group(1)
    if ":" in bid: bid = bid.split(":", 1)[1]
    props = {}
    if m.group(2):
        for kv in m.group(2).split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                props[k.strip()] = v.strip()
    return bid, props


def format_state(bid, props=None):
    s = "minecraft:" + bid
    if props:
        s += "[" + ",".join(f"{k}={props[k]}" for k in sorted(props)) + "]"
    return s


def list_versions():
    out = []
    for d in config.VERSIONS.iterdir() if config.VERSIONS.exists() else []:
        f = d / "version.json"
        if f.exists():
            v = json.loads(f.read_text())
            out.append({"id": v["id"], "data_version": v["data_version"], "type": v.get("type", "release")})
    return sorted(out, key=lambda v: -v["data_version"])


def latest_version():
    vs = list_versions()
    if not vs:
        raise RuntimeError("没有任何版本档案，请先运行: python tools/update_version.py latest")
    rel = [v for v in vs if v["type"] == "release"] or vs
    return rel[0]["id"]


class Registry:
    def __init__(self, version_id):
        d = config.VERSIONS / version_id
        if not (d / "blocks.json").exists():
            raise FileNotFoundError(f"缺少版本档案 {version_id}，请运行: python tools/update_version.py {version_id}")
        self.dir = d
        self.version = json.loads((d / "version.json").read_text())
        self.id = self.version["id"]
        self.data_version = self.version["data_version"]
        self.blocks = json.loads((d / "blocks.json").read_text())      # id -> [props, defaults]
        self.colors = json.loads((d / "colors.json").read_text())
        self._names = list(self.blocks)
        self._cache = {}

    def __contains__(self, bid): return bid in self.blocks

    def resolve_id(self, bid):
        """返回 (有效 id 或 None, 提示)。"""
        if bid in self.blocks: return bid, None
        a = ALIASES.get(bid)
        if a and a in self.blocks: return a, f"{bid} -> {a} (别名/改名)"
        for cand in (bid + "s", bid[:-1] if bid.endswith("s") else None, bid + "_block", bid.replace("_block", "")):
            if cand and cand in self.blocks: return cand, f"{bid} -> {cand} (拼写修正)"
        close = difflib.get_close_matches(bid, self._names, n=1, cutoff=0.82)
        if close: return close[0], f"{bid} -> {close[0]} (近似匹配)"
        return None, None

    def normalize(self, s):
        """任意写法 -> (规范状态字符串 或 None, [警告])。结果带缓存。"""
        if s in self._cache: return self._cache[s]
        warns = []
        try:
            bid, props = parse_state(s)
        except ValueError as e:
            r = (None, [str(e)]); self._cache[s] = r; return r
        rid, note = self.resolve_id(bid)
        if rid is None:
            sug = difflib.get_close_matches(bid, self._names, n=3, cutoff=0.5)
            r = (None, [f"未知方块 '{bid}' ({self.id} 中不存在)" + (f"，相近: {', '.join(sug)}" if sug else "")])
            self._cache[s] = r; return r
        if note: warns.append(note)
        allowed = self.blocks[rid][0] if self.blocks[rid] else {}
        clean = {}
        for k, v in props.items():
            if k not in allowed:
                warns.append(f"{rid} 没有属性 {k}，已忽略")
            elif v not in allowed[k]:
                warns.append(f"{rid} 的 {k}={v} 无效 (可选 {'/'.join(allowed[k])})，已用默认值")
            else:
                clean[k] = v
        r = (format_state(rid, clean), warns)
        self._cache[s] = r
        return r

    def full_props(self, canon):
        """补全默认属性，导出文件时用，避免游戏端按“缺省”猜。"""
        bid, props = parse_state(canon)
        e = self.blocks.get(bid)
        if not e or len(e) < 2: return bid, props
        full = dict(e[1]); full.update(props)
        return bid, full

    def info(self, bid): return self.colors.get(bid, {})

    def search(self, query, limit=40):
        q = [t for t in re.split(r"[\s,]+", query.lower()) if t]
        hits = [b for b in self._names if all(t in b for t in q)]
        return hits[:limit]

    def building_palette(self, group="all"):
        """可用于体素配色的方块: 完整、不透明、无重力、无方块实体、生存里拿得到。"""
        bad = re.compile(r"(powder|sand$|gravel|command|structure|jigsaw|barrier|spawner|infested|bedrock|"
                         r"portal|ore$|_ore|tnt|furnace|dispenser|dropper|observer|piston|shulker|"
                         r"glazed|budding|suspicious|test_|vault|crafter|loom|table|barrel|jukebox|note_block|"
                         r"bookshelf|beehive|bee_nest|target|lamp|pumpkin|melon|hay|dried_kelp|sponge|ice|"
                         r"farmland|mycelium|podzol|grass_block|dirt_path|nylium|mushroom|coral|froglight|magma|"
                         r"creaking|reinforced|respawn|lodestone|trial|copper_bulb|slime|honey|leaves|"
                         r"stripped|_log|_stem|_wood$|hyphae|cactus|bamboo_block|smoker|composter|cauldron|waxed|pillar|grate|"
                         r"chiseled|bone_block|purpur|redstone|bulb|ancient_debris|crying|lodestone|carved|dripstone|heavy_core|resin_clump)")
        groups = {
            "concrete": r"_concrete$", "wool": r"_wool$", "terracotta": r"terracotta$",
            "color": r"(_concrete$|_wool$|terracotta$)",
            "stone": r"(stone|brick|deepslate|andesite|diorite|granite|tuff|basalt|blackstone|quartz|prismarine|calcite|sandstone|mud)",
            "wood": r"_planks$",
        }
        pat = re.compile(groups[group]) if group in groups else None
        out = []
        for bid, c in self.colors.items():
            if not c.get("opaque") or bad.search(bid): continue
            if pat and not pat.search(bid): continue
            out.append((bid, c["rgb"]))
        return out


@lru_cache(maxsize=8)
def get_registry(version_id=None):
    return Registry(version_id or config.load_config().get("default_version") or latest_version())
