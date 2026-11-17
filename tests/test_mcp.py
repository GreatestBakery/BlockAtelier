"""MCP server launch checks: `run_mcp.py` must work for clients that cannot set a working directory (e.g. opencode)."""
import json, os, subprocess, sys
from pathlib import Path
import pytest

pytest.importorskip("mcp")
ROOT = Path(__file__).resolve().parent.parent


def _session(cwd, env, requests):
    """Start the stdio server, send newline-delimited JSON-RPC messages and return responses by id."""
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"}]
    msgs += [{"jsonrpc": "2.0", "id": i + 1, "method": m, "params": p} for i, (m, p) in enumerate(requests)]
    p = subprocess.Popen([sys.executable, str(ROOT / "run_mcp.py")], cwd=cwd, env={**os.environ, **env},
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        out = {}
        for m in msgs:
            p.stdin.write(json.dumps(m) + "\n"); p.stdin.flush()
            if "id" in m:
                line = p.stdout.readline()
                assert line, p.stderr.read()
                r = json.loads(line)        # stdout must carry protocol messages only
                out[r["id"]] = r
        return out
    finally:
        p.stdin.close(); p.terminate(); p.wait(10)


def test_run_mcp_from_another_directory(tmp_path):
    env = {"ATELIER_DATA": str(tmp_path / "no-profiles"), "ATELIER_WORKSPACE": str(tmp_path / "ws")}
    r = _session(tmp_path, env, [("tools/list", {}), ("tools/call", {"name": "get_build_guide", "arguments": {}})])
    assert r[0]["result"]["serverInfo"]["name"] == "blockatelier"
    tools = {t["name"]: t for t in r[1]["result"]["tools"]}
    assert {"get_build_guide", "search_blocks", "build_structure", "voxelize_model", "list_builds",
            "get_build_program", "render_build", "get_blender_script"} <= set(tools)
    assert tools["build_structure"]["inputSchema"]["required"] == ["program"]   # 包装后参数签名不变
    # 失败原因要让客户端里的模型看得到 (这里故意没有版本档案)
    res = r[2]["result"]
    assert res["isError"] and "update_version.py" in res["content"][0]["text"]


def test_mcp_build_matches_application_pipeline(monkeypatch, tmp_path):
    """同一份程序，经 MCP 工具与经网页/桌面管线，得到的方块和校验报告必须一致 (同一内核)。"""
    from atelier import config, pipeline, store, mcp_server
    from atelier.blocks import get_registry
    from atelier.importers import read_any
    monkeypatch.setattr(config, "WORKSPACE", tmp_path); monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    program = json.loads((ROOT / "examples" / "sample_program.json").read_text("utf-8"))
    reg = get_registry(None)
    grid, _, report = pipeline.build_from_program(json.loads(json.dumps(program)), reg, None)
    app_rec = pipeline.finalize(grid, reg, store.new_id(), "app", config.load_config(), report, {"mode": "text"})
    out = json.loads(mcp_server.build_structure(json.loads(json.dumps(program)), title="mcp")[0])
    mcp_rec = store.get_build(out["build_id"])
    assert mcp_rec["mode"] == "mcp" and (mcp_rec["size"], mcp_rec["blocks"]) == (app_rec["size"], app_rec["blocks"])
    for key in ("errors", "warnings", "dsl_errors", "stats", "materials", "mesh"):
        assert mcp_rec["report"][key] == app_rec["report"][key], key
    for name in ("build.litematic", "build.schem"):
        a, _ = read_any(store.build_dir(app_rec["id"]) / name); b, _ = read_any(store.build_dir(mcp_rec["id"]) / name)
        assert a.counts() == b.counts() and a.size() == b.size(), name
