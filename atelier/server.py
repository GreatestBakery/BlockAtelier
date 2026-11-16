"""本地 Web 服务: REST API + 静态前端。只监听 127.0.0.1。"""
import json, re, shutil, threading, time, traceback, uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import config, store, pipeline, __version__
from .blocks import get_registry, list_versions, latest_version
from .render import external

app = FastAPI(title="BlockAtelier", version=__version__)
JOBS = {}
MODEL_EXT = {".obj", ".glb", ".gltf", ".stl", ".ply", ".off", ".3mf", ".dae"}
STRUCT_EXT = {".litematic", ".schem", ".schematic", ".nbt"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


class GenerateRequest(BaseModel):
    prompt: str = ""
    mode: str = "text"                 # text | model
    version: Optional[str] = None
    max_size: list[int] = [32, 32, 32]
    style: str = ""
    model_upload: Optional[str] = None  # 上传后返回的文件名
    voxel: dict = {}
    image_uploads: list[str] = []
    ref_ids: list[str] = []
    parent_id: Optional[str] = None
    tags: list[str] = []


def _safe(name):
    name = re.sub(r"[^\w.\-一-鿿]", "_", Path(name).name)
    return name[-80:] or "file"


def _job(fn):
    jid = uuid.uuid4().hex[:10]
    job = JOBS[jid] = {"id": jid, "status": "running", "events": [], "result": None, "error": None}
    def emit(stage, status, message, data=None):
        job["events"].append({"t": time.time(), "stage": stage, "status": status, "message": message, "data": data})
    def work():
        try:
            job["result"] = fn(emit); job["status"] = "done"
        except Exception as e:
            traceback.print_exc()
            job["error"] = str(e); job["status"] = "error"
            emit("error", "error", str(e))
    threading.Thread(target=work, daemon=True).start()
    return {"job_id": jid}


@app.get("/api/meta")
def meta():
    cfg = config.load_config()
    pub = {k: v for k, v in cfg.items() if k != "api_key"}
    pub["has_key"] = bool(cfg.get("api_key"))
    return {"app": __version__, "versions": list_versions(), "latest": latest_version(), "config": pub,
            "presets": config.PROVIDER_PRESETS, "palettes": ["all", "color", "concrete", "wool", "terracotta", "stone", "wood"],
            "blender": bool(external.find_blender(cfg))}


@app.post("/api/config")
def set_config(patch: dict):
    if patch.get("api_key") == "": patch.pop("api_key")      # 空 = 不改
    config.save_config(patch)
    return meta()


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in MODEL_EXT | IMAGE_EXT | STRUCT_EXT:
        raise HTTPException(400, f"不支持的文件类型 {ext}")
    name = uuid.uuid4().hex[:8] + "_" + _safe(file.filename)
    dst = config.WORKSPACE / "uploads"; dst.mkdir(parents=True, exist_ok=True)
    with open(dst / name, "wb") as f: shutil.copyfileobj(file.file, f)
    return {"name": name, "original": file.filename,
            "kind": "model" if ext in MODEL_EXT else ("image" if ext in IMAGE_EXT else "structure")}


def _upload_path(name):
    p = config.WORKSPACE / "uploads" / _safe(name)
    if not p.exists(): raise HTTPException(404, "上传文件不存在")
    return str(p)


@app.post("/api/generate")
def generate(req: GenerateRequest):
    r = req.model_dump()
    if req.mode == "model":
        if not req.model_upload: raise HTTPException(400, "模型模式需要先上传 3D 模型")
        r["model_path"] = _upload_path(req.model_upload); r["model_name"] = req.model_upload.split("_", 1)[-1]
    elif not req.prompt.strip():
        raise HTTPException(400, "请填写文字描述")
    r["image_paths"] = [_upload_path(n) for n in req.image_uploads]
    cfg = config.load_config()
    return _job(lambda emit: pipeline.run(r, cfg, emit))


@app.get("/api/jobs/{jid}")
def job(jid: str, since: int = 0):
    j = JOBS.get(jid)
    if not j: raise HTTPException(404)
    return {"status": j["status"], "events": j["events"][since:], "next": len(j["events"]), "result": j["result"], "error": j["error"]}


@app.get("/api/builds")
def builds(q: str = "", favorite: bool = False): return store.list_builds(q, favorite)


@app.get("/api/builds/{bid}")
def build(bid: str):
    b = store.get_build(bid)
    if not b: raise HTTPException(404)
    d = store.build_dir(bid)
    for name in ("program", "brief"):
        p = d / f"{name}.json"
        b[name] = json.loads(p.read_text("utf-8")) if p.exists() else None
    return b


@app.patch("/api/builds/{bid}")
def patch_build(bid: str, patch: dict): return store.update_build(bid, patch)


@app.delete("/api/builds/{bid}")
def del_build(bid: str): store.delete_build(bid); return {"ok": True}


@app.get("/api/builds/{bid}/file/{name}")
def build_file(bid: str, name: str, download: bool = False):
    p = store.build_dir(_safe(bid)) / _safe(name)
    if not p.exists(): raise HTTPException(404)
    b = store.get_build(bid) or {}
    fn = f"{_safe(b.get('title') or bid)}_{bid}{p.suffix}" if download else None
    return FileResponse(p, filename=fn)


class RenderRequest(BaseModel):
    engine: str = "CYCLES"
    samples: int = 64
    width: int = 1600
    height: int = 1200
    azimuth: float = 35
    elevation: float = 28
    ortho: bool = False
    views: int = 1


@app.post("/api/builds/{bid}/render")
def render(bid: str, req: RenderRequest):
    d = store.build_dir(_safe(bid)); cfg = config.load_config()
    if not (d / "model.glb").exists(): raise HTTPException(404)
    def work(emit):
        emit("render", "run", f"Blender {req.engine} 渲染中 ({req.width}×{req.height}, {req.samples} 采样)…")
        out = d / f"render_{time.strftime('%H%M%S')}.png"
        paths = external.blender_render(d / "model.glb", out, cfg, req.model_dump())
        emit("render", "done", f"完成 {len(paths)} 张", {"files": [Path(p).name for p in paths]})
        return {"files": [Path(p).name for p in paths]}
    return _job(work)


@app.get("/api/builds/{bid}/blender_snippet", response_class=PlainTextResponse)
def snippet(bid: str):
    d = store.build_dir(_safe(bid))
    return external.blender_mcp_snippet(d / "model.glb", d / "render_mcp.png")


@app.post("/api/builds/{bid}/export/{fmt}")
def export(bid: str, fmt: str):
    """按需导出: schem2 (Sponge v2) / obj (MCprep 友好的 zip)。"""
    from .importers import read_any
    from .exporters import write_schem
    from .mesh import ModelBaker
    b = store.get_build(bid)
    if not b: raise HTTPException(404)
    d = store.build_dir(bid); reg = get_registry(b["version"])
    grid, _ = read_any(d / "build.schem")
    if fmt == "schem2":
        write_schem(grid, reg, d / "build_v2.schem", name=b["title"], version=2); return {"file": "build_v2.schem"}
    if fmt == "obj":
        tmp = d / "_obj"; shutil.rmtree(tmp, ignore_errors=True)
        ModelBaker(reg).export_obj(grid, tmp, "build")
        shutil.make_archive(str(d / "build_obj"), "zip", tmp); shutil.rmtree(tmp, ignore_errors=True)
        return {"file": "build_obj.zip"}
    raise HTTPException(400, "未知格式")


@app.get("/api/refs")
def refs(): return store.list_refs()


@app.post("/api/refs")
async def add_ref(file: UploadFile = File(...), tags: str = Form(""), as_build: bool = Form(False)):
    from .importers import read_any, summarize
    ext = Path(file.filename).suffix.lower()
    if ext not in STRUCT_EXT | IMAGE_EXT: raise HTTPException(400, "参考库只接受结构文件或图片")
    name = uuid.uuid4().hex[:8] + "_" + _safe(file.filename)
    dst = config.WORKSPACE / "refs"; dst.mkdir(parents=True, exist_ok=True)
    with open(dst / name, "wb") as f: shutil.copyfileobj(file.file, f)
    title = Path(file.filename).stem
    if ext in IMAGE_EXT:
        rid = store.add_ref(title, name, "image", {}, tags)
    else:
        try:
            grid, m = read_any(dst / name)
        except Exception as e:
            (dst / name).unlink(missing_ok=True); raise HTTPException(400, f"解析失败: {e}")
        rid = store.add_ref(title, name, "structure", {**summarize(grid, title), **m}, tags)
        if as_build:
            pipeline.import_structure(dst / name, title, config.load_config())
    return store.get_ref(rid)


@app.delete("/api/refs/{rid}")
def del_ref(rid: str): store.delete_ref(rid); return {"ok": True}


@app.get("/api/blocks")
def blocks(q: str = "", version: Optional[str] = None):
    reg = get_registry(version or None)
    return [{"id": b, "rgb": reg.info(b).get("rgb"), "shape": reg.info(b).get("shape")} for b in reg.search(q, 60)]


app.mount("/", StaticFiles(directory=str(config.ROOT / "web"), html=True), name="web")
