"""把 BlockAtelier 暴露成 MCP 服务器 —— 第二种“接入大模型”的方式:
不用填 API key，让任何支持 MCP 的客户端 (Claude 桌面端 / Claude Code / Codex / opencode / Cursor / Cline …) 里的模型直接当建筑师，
它调用这里的工具写指令、拿到校验结果和预览图、自己迭代。与 Blender MCP 同时连接时，模型还能接着在 Blender 里渲染。

启动:  python -m atelier.mcp_server          (stdio，需在项目目录下启动)
       python /绝对路径/run_mcp.py           (stdio，任意工作目录；opencode 等无法指定 cwd 的客户端用这个)
客户端配置示例见 README。
"""
import functools
import json
import sys
from pathlib import Path
try:                                  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server, Image
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:                   # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server, Image
    from mcp.server.fastmcp.exceptions import ToolError
from . import __version__, config, store, pipeline
from .blocks import get_registry, list_versions
from .dsl import GUIDE
from .render import external

mcp = _Server("blockatelier", instructions="Generate Minecraft builds (.litematic/.schem). Call get_build_guide first, "
              "then build_structure with a build program; look at the returned preview and issues, and iterate.")


def tool(fn):
    """注册工具，并把失败原因作为 ToolError 交给客户端里的模型。
    mcp 2.x 对其他异常只回 "Error executing tool <name>"，模型看不到“缺版本档案 / 找不到 Blender / build_id 不存在”这类可自行处理的原因。"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"{type(e).__name__}: {e}") from e
    return mcp.tool()(wrapper)


@tool
def get_build_guide(version: str = "") -> str:
    """Return the build-program format, the target Minecraft version and available versions. Call this first."""
    reg = get_registry(version or None)
    runtime = "desktop app" if getattr(sys, "frozen", False) else "source"   # 两种启动方式是同一份 atelier 内核
    return (f"BlockAtelier core {__version__} ({runtime}).\n"
            f"TARGET: Minecraft Java {reg.id} (DataVersion {reg.data_version}). Installed version profiles: "
            f"{[v['id'] for v in list_versions()]}\n{GUIDE}\nUse search_blocks to check block ids.")


@tool
def search_blocks(query: str, version: str = "") -> str:
    """Find valid block ids containing all the given words (e.g. 'oak stairs', 'copper', 'glass pane'). Returns ids with their properties."""
    reg = get_registry(version or None)
    return json.dumps({b: reg.blocks[b][0] if reg.blocks[b] else {} for b in reg.search(query, 40)})


@tool
def build_structure(program: dict, title: str = "", prompt: str = "", version: str = "", max_size: list[int] | None = None,
                    save: bool = True, parent_id: str = "") -> list:
    """Execute a build program. Validates blocks and structure, auto-connects fences/walls/panes, and (if save) writes
    build.litematic, build.schem, model.glb and a preview into the library. Returns a JSON report (errors, warnings, size,
    materials, file paths) plus a 4-view preview image. Fix reported errors and call again; pass parent_id to record lineage."""
    reg = get_registry(version or None)
    grid, _, report = pipeline.build_from_program(program, reg, {"max_size": max_size} if max_size else None)
    if len(grid) == 0:
        return [json.dumps(report, ensure_ascii=False)]
    cfg = config.load_config()
    bid = store.new_id(); d = store.build_dir(bid)
    name = title or program.get("name", "Untitled")
    out = {"report": report, "size_xyz": list(grid.size()), "blocks": len(grid)}
    if save:
        (d / "program.json").write_text(json.dumps(program, ensure_ascii=False, indent=1), "utf-8")
        pipeline.finalize(grid, reg, bid, name, cfg, report,
                          {"prompt": prompt, "mode": "mcp", "provider": "mcp", "parent_id": parent_id or None})
        out.update(build_id=bid, files={n: str(d / n) for n in ("build.litematic", "build.schem", "model.glb", "preview.png")})
        preview = (d / "preview.png").read_bytes()
    else:
        report["mesh"] = pipeline.export_all(grid, reg, d, name, cfg)
        preview = (d / "preview.png").read_bytes()
        store.delete_build(bid)
    return [json.dumps(out, ensure_ascii=False), Image(data=preview, format="png")]


@tool
def voxelize_model(path: str, max_size: int = 48, palette: str = "all", solid: bool = False, title: str = "", version: str = "") -> list:
    """Convert a 3D model file (.obj/.glb/.stl/.ply) into a Minecraft build by voxelizing it and matching colours to blocks.
    palette: all | color | concrete | wool | terracotta | stone | wood. Saves to the library and returns report + preview."""
    cfg = config.load_config()
    rec = pipeline.run({"mode": "model", "model_path": path, "prompt": "", "version": version or None,
                        "voxel": {"size": max_size, "palette": palette, "solid": solid}}, {**cfg, "provider": "mock"})
    if title: rec = store.update_build(rec["id"], {"title": title})
    d = store.build_dir(rec["id"])
    return [json.dumps({"build_id": rec["id"], "size_xyz": rec["size"], "blocks": rec["blocks"], "report": rec["report"],
                        "files": {n: str(d / n) for n in ("build.litematic", "build.schem", "model.glb")}}, ensure_ascii=False),
            Image(data=(d / "preview.png").read_bytes(), format="png")]


@tool
def list_builds(query: str = "") -> str:
    """List saved builds in the library (id, title, size, blocks, version)."""
    return json.dumps([{k: b[k] for k in ("id", "title", "size", "blocks", "version", "mode")} for b in store.list_builds(query)], ensure_ascii=False)


@tool
def get_build_program(build_id: str) -> str:
    """Return the saved build program of a build so it can be revised."""
    p = store.build_dir(build_id) / "program.json"
    return p.read_text("utf-8") if p.exists() else "{}"


@tool
def render_build(build_id: str, samples: int = 64, width: int = 1600, height: int = 1200, azimuth: float = 35, elevation: float = 28) -> list:
    """Render a saved build with a local Blender install (Cycles). Returns the image path and the image."""
    d = store.build_dir(build_id)
    out = d / "render_mcp.png"
    external.blender_render(d / "model.glb", out, config.load_config(),
                            {"samples": samples, "width": width, "height": height, "azimuth": azimuth, "elevation": elevation})
    from PIL import Image as PI
    import io
    im = PI.open(out); im.thumbnail((1024, 1024)); buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=85)
    return [str(out), Image(data=buf.getvalue(), format="jpeg")]


@tool
def get_blender_script(build_id: str) -> str:
    """Return Python code that imports a saved build into Blender and renders it. Pass it to a Blender MCP server's
    execute-code tool to render inside the user's running Blender instead of a headless one."""
    d = store.build_dir(build_id)
    return external.blender_mcp_snippet(d / "model.glb", d / "render_mcp.png")


if __name__ == "__main__":
    mcp.run()
