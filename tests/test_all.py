"""自检套件:  python -m pytest tests -q
全部离线可跑 (大模型接口用本地假服务器验证请求/响应格式)。"""
import json, math, os, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import numpy as np
import pytest

os.environ["ATELIER_WORKSPACE"] = tempfile.mkdtemp(prefix="atelier_test_")
from atelier import config, pipeline, store
from atelier.blocks import get_registry, parse_state, format_state, list_versions
from atelier.dsl import execute
from atelier.validate import validate
from atelier.exporters import write_litematic, write_schem
from atelier.exporters.litematic import litematic_format_version
from atelier.importers import read_any
from atelier.llm import make_client, extract_json, LLMError

ROOT = Path(__file__).resolve().parent.parent
REG = get_registry()
HOUSE = {"palette": {"wall": "stone_bricks"}, "ops": [
    {"op": "box", "from": [0, 0, 0], "to": [8, 5, 6], "block": "$wall", "mode": "hollow"},
    {"op": "roof", "from": [0, 6, 0], "to": [8, 6, 6], "style": "gable", "ridge": "x", "block": "oak_planks", "stairs": "oak_stairs", "overhang": 1},
    {"op": "door", "at": [4, 1, 0], "block": "oak_door", "facing": "north"},
    {"op": "line", "from": [10, 0, 0], "to": [10, 0, 6], "block": "oak_fence"},
    {"op": "set", "at": [2, 2, 0], "block": "glass_pane"}]}


def build(prog=HOUSE, reg=REG):
    g, errs = execute(prog)
    g, rep = validate(g, reg)
    return g, errs, rep


# ---------- 版本档案 ----------
def test_version_profiles():
    vs = {v["id"]: v for v in list_versions()}
    assert "26.3" in vs and vs["26.3"]["data_version"] == 5023
    assert "poplar_planks" in REG and "stone" in REG          # 26.3 新方块在表里
    assert "poplar_planks" not in get_registry("1.21.11")      # 老版本里没有
    assert litematic_format_version(5023) == 7 and litematic_format_version(3700) == 6


def test_normalize():
    assert REG.normalize("Stone_Brick")[0] == "minecraft:stone_bricks"
    assert REG.normalize("minecraft:grass")[0] == "minecraft:short_grass"
    assert REG.normalize("oak_stairs[facing=up,foo=1]")[0] == "minecraft:oak_stairs"
    assert REG.normalize("unobtainium")[0] is None
    assert get_registry("1.21.11").normalize("poplar_planks")[0] is None


# ---------- 指令解释器 ----------
def test_dsl_shapes():
    g, e = execute({"ops": [{"op": "box", "from": [0, 0, 0], "to": [4, 4, 4], "block": "stone", "mode": "hollow"}]})
    assert not e and len(g) == 125 - 27
    g, e = execute({"ops": [{"op": "sphere", "center": [8, 8, 8], "radius": 6, "block": "stone"}]})
    assert abs(len(g) - 4 / 3 * math.pi * 6.5 ** 3) / len(g) < 0.08
    g, e = execute({"ops": [{"op": "cylinder", "base": [5, 0, 5], "radius": 4, "height": 3, "block": "stone", "hollow": True}]})
    assert g.get(5, 0, 5) is None and g.get(9, 0, 5)
    g, e = execute({"ops": [{"op": "pattern", "origin": [0, 0, 0], "plane": "xy", "rows": ["#g#", "###"], "legend": {"#": "stone", "g": "glass"}}]})
    assert g.get(1, 1, 0) == "minecraft:glass" and g.get(1, 0, 0) == "minecraft:stone"


def test_dsl_group_transforms():
    prog = {"ops": [{"op": "group", "ops": [{"op": "set", "at": [1, 0, 0], "block": "oak_stairs[facing=east]"}],
                     "mirror": {"axis": "x", "at": 5}, "repeat": {"count": 3, "step": [0, 0, 2]}}]}
    g, e = execute(prog)
    assert not e and len(g) == 6
    assert g.get(9, 0, 4) == "minecraft:oak_stairs[facing=west]"
    g, e = execute({"ops": [{"op": "group", "ops": [{"op": "set", "at": [2, 0, 0], "block": "oak_log[axis=x]"}, {"op": "set", "at": [0, 0, -1], "block": "oak_stairs[facing=north]"}],
                             "rotate_y": 90, "pivot": [0, 0]}]})
    assert g.get(0, 0, 2) == "minecraft:oak_log[axis=z]" and g.get(1, 0, 0) == "minecraft:oak_stairs[facing=east]"


def test_dsl_errors_are_collected_not_fatal():
    g, e = execute({"ops": [{"op": "nope"}, {"op": "box", "from": [0, 0], "to": [1, 1, 1], "block": "stone"},
                            {"op": "set", "at": [0, 0, 0], "block": "$missing"}, {"op": "set", "at": [0, 0, 0], "block": "stone"}]})
    assert len(e) == 3 and len(g) == 1


# ---------- 校验 ----------
def test_validate_catches_problems():
    g, e = execute({"ops": [{"op": "box", "from": [0, 0, 0], "to": [3, 3, 3], "block": "stone"},
                            {"op": "box", "from": [10, 8, 10], "to": [13, 11, 13], "block": "stone"},
                            {"op": "set", "at": [1, 6, 1], "block": "sand"}, {"op": "set", "at": [0, 4, 0], "block": "mithril_block"}]})
    g, rep = validate(g, REG, {"max_size": [8, 8, 8]})
    text = " ".join(rep["errors"] + rep["warnings"])
    assert "未知方块" in text and "悬空" in text and "超过" in text and "重力" in text


def test_autoconnect_and_roof_orientation():
    g, e, rep = build()
    assert not e and not rep["errors"]
    assert parse_state(g.get(11, 0, 3))[1]["north"] == "true"            # 栅栏连起来了
    stairs = {parse_state(s)[1]["facing"] for s in g.cells.values() if "oak_stairs" in s}
    assert stairs == {"north", "south"}


# ---------- 导出 ----------
def _expect(g, reg):
    return {p: format_state(*reg.full_props(s)) for p, s in g.cells.items()}


def test_litematic_independent_decode(tmp_path):
    """不依赖 litemapy，按 Litematica 的位打包规则自己解一遍。"""
    import nbtlib
    g, _, _ = build()
    f = tmp_path / "t.litematic"; write_litematic(g, REG, f, "测试")
    n = nbtlib.load(str(f), gzipped=True)
    assert int(n["Version"]) == 7 and int(n["MinecraftDataVersion"]) == 5023
    r = next(iter(n["Regions"].values()))
    sx, sy, sz = (abs(int(r["Size"][k])) for k in "xyz")
    pal = []
    for p in r["BlockStatePalette"]:
        props = {str(k): str(v) for k, v in p.get("Properties", {}).items()}
        pal.append(format_state(str(p["Name"]).split(":")[1], props))
    bits = max(2, (len(pal) - 1).bit_length())
    longs = np.array(r["BlockStates"], dtype=np.int64).astype(np.uint64)
    assert len(longs) == math.ceil(sx * sy * sz * bits / 64)
    big = int.from_bytes(longs.tobytes(), "little")
    exp = _expect(g, REG); mask = (1 << bits) - 1; seen = 0
    for y in range(sy):
        for z in range(sz):
            for x in range(sx):
                i = (y * sz + z) * sx + x
                s = pal[(big >> (i * bits)) & mask]
                if s != "minecraft:air":
                    assert exp[(x, y, z)] == s; seen += 1
    assert seen == len(g)


@pytest.mark.parametrize("ver", [2, 3])
def test_schem_roundtrip(tmp_path, ver):
    g, _, _ = build()
    f = tmp_path / "t.schem"; write_schem(g, REG, f, "t", version=ver)
    g2, meta = read_any(f)
    assert meta["data_version"] == 5023 and g2.cells == _expect(g, REG)


def test_export_for_older_version(tmp_path):
    reg = get_registry("1.21.11")
    g, e, rep = build(reg=reg)
    write_litematic(g, reg, tmp_path / "o.litematic"); g2, meta = read_any(tmp_path / "o.litematic")
    assert meta["data_version"] == 4671 and len(g2) == len(g)


def test_mesh_export(tmp_path):
    import trimesh
    from atelier.mesh import ModelBaker
    g, _, _ = build()
    b = ModelBaker(REG); st = b.export_glb(g, tmp_path / "m.glb")
    sc = trimesh.load(str(tmp_path / "m.glb"))
    assert st["triangles"] > 500 and len(sc.geometry) >= 1
    # 楼梯不是整方块: 一个朝东楼梯应有上下两级
    q = b.quads("minecraft:oak_stairs[facing=east,half=bottom,shape=straight]")
    ys = {round(float(v[:, 1].max()), 2) for v, *_ in q}
    assert {0.5, 1.0} <= ys
    assert Path(b.export_obj(g, tmp_path / "obj")).exists()


# ---------- 3D 模型 ----------
def test_voxelize_colors():
    from atelier.meshvox import voxelize
    g, info = voxelize(ROOT / "examples" / "tower.glb", REG, max_size=32, palette="concrete")
    c = g.counts()
    assert max(g.size()) == 32 and {"minecraft:white_concrete", "minecraft:red_concrete", "minecraft:lime_concrete"} <= set(c)
    gs, info2 = voxelize(ROOT / "examples" / "tower.glb", REG, max_size=32, solid=True)
    assert info2["filled_inside"] > 0 and len(gs) > len(g)


# ---------- 大模型适配 ----------
def test_extract_json():
    assert extract_json('好的:\n```json\n{"a": [1, 2,], // c\n "b": "x}y"}\n```')["b"] == "x}y"
    assert extract_json('prefix {"a": {"b": 1}} suffix') == {"a": {"b": 1}}
    with pytest.raises(LLMError): extract_json("no json here")
    with pytest.raises(LLMError): extract_json('{"a": 1 /*TRUNCATED*/')


class _Fake(BaseHTTPRequestHandler):
    seen = []
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        _Fake.seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        if self.path == "/v1/messages":
            out = {"content": [{"type": "text", "text": '{"ok": "anthropic"}'}], "stop_reason": "end_turn"}
        else:
            out = {"choices": [{"message": {"content": '{"ok": "openai"}'}, "finish_reason": "stop"}]}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass


def test_llm_wire_formats():
    srv = HTTPServer(("127.0.0.1", 0), _Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    msg = [{"role": "user", "text": "hi", "images": [png]}]
    a = make_client({"provider": "anthropic", "model": "m1", "api_key": "k1", "base_url": base, "vision": True})
    assert extract_json(a.chat("sys", msg)) == {"ok": "anthropic"}
    path, hdr, body = _Fake.seen[-1]
    assert path == "/v1/messages" and hdr["x-api-key"] == "k1" and body["system"] == "sys" and body["model"] == "m1"
    assert body["messages"][0]["content"][0]["source"]["media_type"] == "image/png"
    o = make_client({"provider": "custom", "model": "m2", "api_key": "k2", "base_url": base + "/v1", "vision": True})
    assert extract_json(o.chat("sys", msg)) == {"ok": "openai"}
    path, hdr, body = _Fake.seen[-1]
    assert path == "/v1/chat/completions" and hdr["authorization"] == "Bearer k2" and body["messages"][0]["role"] == "system"
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    srv.shutdown()


# ---------- 整条流水线 (离线模拟模型) ----------
@pytest.mark.parametrize("prompt", ["一座石塔", "朱红色凉亭", "小木屋"])
def test_pipeline_text(prompt):
    events = []
    rec = pipeline.run({"prompt": prompt, "max_size": [21, 36, 21]}, config.load_config(), lambda *a: events.append(a[:2]))
    assert rec["blocks"] > 300 and not rec["report"]["errors"] and not rec["report"]["dsl_errors"]
    assert {"build.litematic", "build.schem", "model.glb", "preview.png", "program.json", "brief.json"} <= set(rec["files"])
    assert ("export", "done") in events
    assert all(a <= b for a, b in zip(rec["size"], [21, 36, 21]))


def test_pipeline_repair_loop():
    """第一次给出坏指令，修复轮给出好指令: 验证问题清单确实回传并被采纳。"""
    class Flaky:
        calls = []
        def chat(self, system, messages, task=None):
            Flaky.calls.append((task, messages[0]["text"]))
            if task == "brief": return '{"title": "修复测试", "concept": "", "size": [8,8,8]}'
            if task == "program": return json.dumps({"ops": [{"op": "box", "from": [0, 0, 0], "to": [4, 3, 4], "block": "stone"},
                                                             {"op": "box", "from": [0, 9, 0], "to": [2, 30, 2], "block": "adamantium"}]})
            if task == "repair": return json.dumps({"ops": [{"op": "box", "from": [0, 0, 0], "to": [4, 3, 4], "block": "stone"}]})
            return '{"verdict": "ok", "notes": []}'
    orig = pipeline.make_client; pipeline.make_client = lambda cfg: Flaky()
    try:
        rec = pipeline.run({"prompt": "x", "max_size": [8, 8, 8]}, config.load_config())
    finally:
        pipeline.make_client = orig
    tasks = [t for t, _ in Flaky.calls]
    assert tasks.count("repair") == 1 and "adamantium" in dict(Flaky.calls)["repair"]
    assert rec["blocks"] == 100 and not rec["report"]["errors"]


def test_pipeline_model_and_library(tmp_path):
    rec = pipeline.run({"mode": "model", "model_path": str(ROOT / "examples" / "tower.obj"), "voxel": {"size": 24}}, config.load_config())
    assert rec["mode"] == "model" and max(rec["size"]) == 24
    assert any(b["id"] == rec["id"] for b in store.list_builds())
    store.update_build(rec["id"], {"favorite": True, "tags": ["塔", "test"]})
    assert store.list_builds(favorite=True)[0]["tags"] == ["塔", "test"] and store.list_builds("塔")
    imp = pipeline.import_structure(store.build_dir(rec["id"]) / "build.litematic", "导入测试", config.load_config())
    assert imp["blocks"] == rec["blocks"] and imp["mode"] == "import"
    store.delete_build(imp["id"]); assert store.get_build(imp["id"]) is None
