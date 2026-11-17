"""Coordinate design, building programs, validation, revisions, previews, and export."""
import json, time, traceback
from pathlib import Path
from . import store, references
from .blocks import get_registry, parse_state
from .dsl import execute, GUIDE
from .validate import validate
from .exporters import write_litematic, write_schem
from .llm import make_client, extract_json, LLMError
from .mesh import ModelBaker
from .render.iso import render_views, contact_sheet

SYS_BRIEF = """You are an architect planning a Minecraft build for an art project. Analyse the request (and any reference images /
reference structures) and reply with ONE JSON object, no prose:
{"title": short title in the user's language,
 "concept": 2-3 sentences: what makes this build read well (silhouette, rhythm, focal point),
 "style": style keywords,
 "size": [x, y, z] overall size in blocks (must fit MAX_SIZE),
 "palette": {"role": "block_id", ...} 5-10 roles such as wall, trim, roof, floor, glass, accent, light,
 "components": [{"name": ..., "description": ..., "from": [x,y,z], "to": [x,y,z]}, ...] the main masses with their bounding boxes,
 "details": ["concrete detailing ideas", ...],
 "search_queries": ["2-3 web search queries that would find useful visual references"]}
Use only real block ids of the target version. x = east, y = up, z = south, ground at y = 0."""

SYS_PROGRAM = """You are an expert Minecraft builder. You output a BUILD PROGRAM (JSON) that a deterministic interpreter turns into blocks.
Reply with ONE JSON object and nothing else.
""" + GUIDE + """
QUALITY BAR
- Follow the brief's size and palette. Think in components; give each a comment-free, compact set of ops.
- The result must be one connected structure standing on y=0 (no floating parts), with a door/entrance and a real interior where it makes sense.
- Prefer many small deliberate ops over a few giant boxes: depth on facades, window rhythm, roof overhangs, a clear silhouette."""

SYS_REPAIR = SYS_PROGRAM + """
You are now FIXING a previous program. You get the program and a list of problems found by the interpreter/validator.
Return the complete corrected program (same JSON format), changing only what is needed."""

SYS_CRITIQUE = """You are reviewing renders of a Minecraft build against its brief. The image is a contact sheet of four isometric views
(simple flat-colour preview: stairs/slabs are drawn as blocks). Judge silhouette, proportions, missing/odd parts, floating bits, material balance.
Reply with ONE JSON object: {"verdict": "ok" | "revise", "notes": ["short findings"], "program": <full revised BUILD PROGRAM, only if verdict is "revise">}
Only ask for a revision when it clearly improves the build. The program format is:
""" + GUIDE

SYS_REMAP = """A 3D model was voxelized into Minecraft blocks by nearest colour. Re-skin it to match the user's description by mapping
materials. Reply with ONE JSON object: {"mapping": {"current_block_id": "new_block_id", ...}, "notes": "one line"}.
Only full, solid, non-falling blocks. Leave out blocks that should stay. Use real block ids of the target version."""


class Cancelled(Exception):
    pass


def _block_hint(reg):
    return "VALID BLOCK IDS FOR MINECRAFT " + reg.id + " (omit the minecraft: prefix):\n" + " ".join(reg.blocks.keys())


def _issues_text(dsl_errors, report):
    lines = [f"- [interpreter] {w}: {m}" for w, m in dsl_errors]
    lines += [f"- [error] {e}" for e in report["errors"]] + [f"- [warning] {w}" for w in report["warnings"]]
    return "\n".join(lines)


def _build_from_program(program, reg, limits):
    grid, dsl_errors = execute(program)
    grid, report = validate(grid, reg, limits)
    report["dsl_errors"] = [f"{w}: {m}" for w, m in dsl_errors]
    return grid, dsl_errors, report


def export_all(grid, reg, d, title, cfg, emit=None):
    """把最终网格写成全部产物。"""
    d = Path(d)
    write_litematic(grid, reg, d / "build.litematic", name=title, author=cfg.get("author", "BlockAtelier"))
    write_schem(grid, reg, d / "build.schem", name=title, author=cfg.get("author", "BlockAtelier"), version=3)
    stats = ModelBaker(reg).export_glb(grid, d / "model.glb")
    views = render_views(grid, reg, str(d), size=640)
    contact_sheet(views, str(d / "preview.png"))
    Path(views[0]).replace(d / "thumb.png")
    for v in views[1:]: Path(v).unlink(missing_ok=True)
    return stats


def run(request, cfg, emit=lambda *a, **k: None, build_id=None):
    """执行一次生成。request 字段见 server.GenerateRequest。返回作品记录 (dict)。"""
    t0 = time.time()
    bid = build_id or store.new_id()
    d = store.build_dir(bid)
    reg = get_registry(request.get("version") or None)
    max_size = [int(v) for v in (request.get("max_size") or [32, 32, 32])]
    limits = {"max_size": max_size}
    prompt = (request.get("prompt") or "").strip()
    mode = request.get("mode") or ("model" if request.get("model_path") else "text")
    (d / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=1), "utf-8")
    emit("intake", "done", f"目标版本 {reg.id} (DataVersion {reg.data_version})，尺寸上限 {max_size}，模式 {mode}")
    client = make_client(cfg)
    log = []

    def ask(system, text, task, images=None):
        t = time.time()
        out = client.chat(system, [{"role": "user", "text": text, "images": images or []}], task=task)
        log.append({"task": task, "seconds": round(time.time() - t, 1), "prompt_chars": len(text), "reply": out})
        (d / "llm_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), "utf-8")
        return extract_json(out)

    title, program, brief, grid, report = prompt[:24] or "未命名", None, None, None, None

    if mode == "model":
        # ---------- 路线 B: 3D 模型 -> 体素 ----------
        from .meshvox import voxelize, remap_blocks
        vx = request.get("voxel") or {}
        emit("voxelize", "run", "体素化 3D 模型…")
        grid, info = voxelize(request["model_path"], reg, max_size=int(vx.get("size", max(max_size))),
                              palette=vx.get("palette", "all"), solid=bool(vx.get("solid")), up=vx.get("up", "auto"))
        emit("voxelize", "done", f"{info['triangles']} 个三角面 -> {info['size']}，{info['distinct_blocks']} 种方块", info)
        title = Path(request.get("model_name") or request["model_path"]).stem
        if prompt:
            emit("remap", "run", "让模型按文字描述调整材质…")
            try:
                counts = {s.replace("minecraft:", ""): n for s, n in grid.counts().items()}
                r = ask(SYS_REMAP, f"USER REQUEST: {prompt}\nCURRENT MATERIALS (block: count): {json.dumps(counts)}\n\n{_block_hint(reg)}", "remap")
                mapping = {}
                for k, v in (r.get("mapping") or {}).items():
                    ck, _ = reg.normalize(k); cv, _ = reg.normalize(v)
                    if ck and cv and reg.info(parse_state(cv)[0]).get("opaque"): mapping[ck] = cv
                grid = remap_blocks(grid, mapping)
                emit("remap", "done", f"替换了 {len(mapping)} 种材质。{r.get('notes', '')}", {"mapping": mapping})
            except LLMError as e:
                emit("remap", "warn", f"材质调整跳过: {e}")
        grid, report = validate(grid, reg, None)
        report["dsl_errors"] = []; report["voxel"] = info
    else:
        # ---------- 路线 A: 文本 (+参考) -> 指令 -> 体素 ----------
        parent = request.get("parent_id")
        parent_prog = None
        if parent:
            pp = store.build_dir(parent) / "program.json"
            if pp.exists(): parent_prog = json.loads(pp.read_text("utf-8"))
        emit("references", "run", "整理参考资料…")
        refs = references.gather(prompt, cfg, request.get("ref_ids"), request.get("image_paths"))
        emit("references", "done", f"参考结构 {len(refs['structures'])} 个，参考图 {len(refs['images'])} 张", {"structures": refs["structures"]})
        head = f"USER REQUEST: {prompt}\nTARGET VERSION: Minecraft Java {reg.id}\nMAX_SIZE = [{max_size[0]}, {max_size[1]}, {max_size[2]}]  (x, y, z)\n"
        if request.get("style"): head += f"STYLE HINT: {request['style']}\n"
        emit("brief", "run", "分析需求、定设计方案…")
        brief = ask(SYS_BRIEF, head + "\n" + refs["text"], "brief", refs["images"])
        (d / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), "utf-8")
        title = str(brief.get("title") or title)[:60]
        emit("brief", "done", f"《{title}》 {brief.get('concept', '')}", brief)
        if brief.get("search_queries") and cfg.get("searxng_url"):
            web = references.web_search(brief["search_queries"], cfg)
            extra = "\n".join(f"- {w['title']} — {w['snippet']}" for w in web if "title" in w)
            if extra: refs["text"] += "\nWEB SEARCH HITS:\n" + extra
            emit("references", "done", f"联网检索到 {len([w for w in web if 'title' in w])} 条线索", {"web": web})

        emit("program", "run", "生成建筑指令…")
        body = head + "\nDESIGN BRIEF:\n" + json.dumps(brief, ensure_ascii=False) + "\n\n" + refs["text"] + "\n\n" + _block_hint(reg)
        if parent_prog:
            body += "\n\nThis is a REVISION of an existing build. Modify the program below according to the user request and return the full program:\n" + json.dumps(parent_prog, ensure_ascii=False)
        program = ask(SYS_PROGRAM, body, "program", refs["images"])
        grid, dsl_errors, report = _build_from_program(program, reg, limits)
        emit("program", "done", f"{len(program.get('ops', []))} 条指令 -> {report['stats'].get('blocks', 0)} 个方块",
             {"errors": report["errors"], "warnings": report["warnings"], "dsl_errors": report["dsl_errors"]})

        # 校验不过 -> 带着问题清单让模型修
        rounds = int(cfg.get("repair_rounds", 2)); i = 0
        while (dsl_errors or report["errors"]) and i < rounds:
            i += 1
            emit("repair", "run", f"第 {i} 轮修复: {len(dsl_errors) + len(report['errors'])} 个问题")
            try:
                fixed = ask(SYS_REPAIR, head + "\nPROBLEMS:\n" + _issues_text(dsl_errors, report) + "\n\nPROGRAM:\n" +
                            json.dumps(program, ensure_ascii=False) + "\n\n" + _block_hint(reg), "repair")
            except LLMError as e:
                emit("repair", "warn", f"修复失败: {e}"); break
            g2, e2, r2 = _build_from_program(fixed, reg, limits)
            if len(e2) + len(r2["errors"]) <= len(dsl_errors) + len(report["errors"]) and len(g2):
                program, grid, dsl_errors, report = fixed, g2, e2, r2
            emit("repair", "done", f"剩余问题 {len(dsl_errors) + len(report['errors'])} 个")
        if len(grid) == 0:
            raise RuntimeError("生成结果为空: " + "; ".join(report["dsl_errors"] + report["errors"])[:400])

        # 渲染预览 -> 让视觉模型看图自评
        for c in range(int(cfg.get("critique_rounds", 1)) if cfg.get("vision", True) else 0):
            emit("critique", "run", "渲染预览并让模型看图自评…")
            views = render_views(grid, reg, str(d), size=512)
            sheet = contact_sheet(views, str(d / f"critique_{c}.png"))
            for v in views: Path(v).unlink(missing_ok=True)
            try:
                r = ask(SYS_CRITIQUE, head + "\nDESIGN BRIEF:\n" + json.dumps(brief, ensure_ascii=False) + "\n\nCURRENT PROGRAM:\n" +
                        json.dumps(program, ensure_ascii=False) + "\n\nVALIDATOR NOTES:\n" + (_issues_text([], report) or "none"),
                        "critique", [open(sheet, "rb").read()])
            except LLMError as e:
                emit("critique", "warn", f"自评跳过: {e}"); break
            notes = "; ".join(str(n) for n in r.get("notes", []))[:300]
            if r.get("verdict") == "revise" and isinstance(r.get("program"), dict):
                g2, e2, r2 = _build_from_program(r["program"], reg, limits)
                if len(g2) and not e2 and len(r2["errors"]) <= len(report["errors"]):
                    program, grid, dsl_errors, report = r["program"], g2, e2, r2
                    emit("critique", "done", "已采纳修改: " + notes); continue
                emit("critique", "warn", "修改版有新问题，保留原版。" + notes)
            else:
                emit("critique", "done", "通过: " + notes)
            break
        (d / "program.json").write_text(json.dumps(program, ensure_ascii=False, indent=1), "utf-8")

    emit("export", "run", "导出 .litematic / .schem / 3D 预览…")
    mesh_stats = export_all(grid, reg, d, title, cfg)
    report["mesh"] = mesh_stats
    report["materials"] = [{"block": s, "count": n} for s, n in list(grid.counts().items())[:40]]
    report["seconds"] = round(time.time() - t0, 1)
    rec = store.save_build({"id": bid, "title": title, "prompt": prompt, "mode": mode, "version": reg.id,
                            "provider": cfg.get("provider", ""), "model": cfg.get("model", ""), "size": list(grid.size()),
                            "blocks": len(grid), "parent_id": request.get("parent_id"), "report": report,
                            "tags": request.get("tags") or []})
    emit("export", "done", f"完成: {rec['size'][0]}×{rec['size'][1]}×{rec['size'][2]}，{rec['blocks']} 个方块，用时 {report['seconds']}s", {"build_id": bid})
    return rec


def import_structure(path, name, cfg, version=None):
    """把现成的结构文件作为作品入库 (同时完成 格式互转 + 预览)。注意: 不做跨版本数据升级，未知方块会被丢弃并报告。"""
    from .importers import read_any
    reg = get_registry(version or None)
    grid, meta = read_any(path)
    grid, report = validate(grid, reg, None)
    report["dsl_errors"] = []; report["source"] = meta
    bid = store.new_id(); d = store.build_dir(bid)
    report["mesh"] = export_all(grid, reg, d, name, cfg)
    report["materials"] = [{"block": s, "count": n} for s, n in list(grid.counts().items())[:40]]
    return store.save_build({"id": bid, "title": name, "prompt": f"导入自 {Path(path).name}", "mode": "import", "version": reg.id,
                             "size": list(grid.size()), "blocks": len(grid), "report": report})
