"""Discover Blender and prepare local rendering or external-tool commands."""
import importlib.util, shutil, subprocess, sys
from pathlib import Path

JOB = Path(__file__).with_name("blender_job.py")


def find_blender(cfg):
    exe = cfg.get("blender_path") or "blender"
    p = shutil.which(exe) or (exe if Path(exe).exists() else None)
    if p: return [p, "-b", "--python-exit-code", "1", "-P", str(JOB), "--"]
    if importlib.util.find_spec("bpy"): return [sys.executable, str(JOB), "--"]
    return None


def blender_render(glb, out, cfg, opts=None, log=None):
    cmd = find_blender(cfg)
    if not cmd:
        raise RuntimeError("找不到 Blender。请安装 Blender 并在设置里填可执行文件路径，或 pip install bpy；"
                           "也可以用“复制 Blender MCP 脚本”让已连接 Blender MCP 的模型来渲染。")
    args = ["--glb", str(glb), "--out", str(out)]
    for k, v in (opts or {}).items(): args += [f"--{k}", str(v)]
    r = subprocess.run(cmd + args, capture_output=True, text=True, timeout=3600, cwd=str(Path(out).parent))
    if log: log(r.stdout[-1500:])
    if r.returncode != 0 or "ATELIER_RENDERED" not in r.stdout:
        raise RuntimeError("Blender 渲染失败: " + (r.stderr or r.stdout)[-800:])
    n = int((opts or {}).get("views", 1))
    return [str(out)] if n <= 1 else [str(out).replace(".png", f"_{i}.png") for i in range(n)]


def blender_mcp_snippet(glb, out, opts=None):
    """生成一段可直接交给 Blender MCP (execute_blender_code) 的代码: 在用户正在运行的 Blender 里导入并渲染。"""
    src = JOB.read_text("utf-8").split("def _cli():")[0]
    o = {"glb": str(glb), "out": str(out), "keep_scene": False, **(opts or {})}
    return src + f"\nprint(render_build({o!r}))\n"


def chunky_command(scene_dir, scene_name, chunky_jar="ChunkyLauncher.jar"):
    """Chunky 无头渲染命令 (需要你先在 Chunky 里对含有该建筑的存档建好场景)。"""
    return ["java", "-jar", chunky_jar, "-scene-dir", str(scene_dir), "-render", scene_name]
