"""参考资料检索。三个来源，可靠性从高到低:
  1) 本地参考库: 你自己收集的 .litematic/.schem/.nbt (解析成尺寸+用料摘要) 和图片 (直接给视觉模型看)
  2) 用户本次上传的图片
  3) 联网搜索 (可选, 自建 SearXNG): 只取标题/摘要/链接作为文字线索
批判性说明: Planet Minecraft 之类的站点没有公开 API、且有反爬，自动下载别人的结构文件既不稳定也不该默认做；
所以“找类似的已有建筑”在本软件里落在本地参考库上 —— 你下载、你放进去，软件负责解析和匹配。
"""
import json, re, urllib.parse, urllib.request
from . import store, config


def _tokens(s):
    s = s.lower()
    return set(re.findall(r"[a-z0-9_]{3,}", s)) | set(re.findall(r"[一-鿿]", s))


def match_local(prompt, ref_ids=None, limit=3):
    refs = store.list_refs()
    if ref_ids:
        return [r for r in refs if r["id"] in ref_ids]
    pt = _tokens(prompt); scored = []
    for r in refs:
        score = len(pt & _tokens(r["name"] + " " + r["tags"]))
        if score: scored.append((score, r))
    return [r for _, r in sorted(scored, key=lambda t: -t[0])[:limit]]


def web_search(queries, cfg, per_query=4):
    base = (cfg.get("searxng_url") or "").rstrip("/")
    if not base: return []
    out = []
    for q in queries[:3]:
        try:
            url = f"{base}/search?" + urllib.parse.urlencode({"q": q, "format": "json"})
            with urllib.request.urlopen(url, timeout=15) as r:
                for it in json.loads(r.read()).get("results", [])[:per_query]:
                    out.append({"query": q, "title": it.get("title", ""), "url": it.get("url", ""), "snippet": (it.get("content") or "")[:240]})
        except Exception as e:
            out.append({"query": q, "error": str(e)})
    return out


def gather(prompt, cfg, ref_ids=None, image_paths=None, queries=None):
    """-> {"structures": [摘要], "images": [bytes], "web": [...], "text": 给模型的文字块}"""
    structs, images = [], []
    for r in match_local(prompt, ref_ids):
        if r["kind"] == "structure": structs.append(r["summary"])
        elif r["kind"] == "image":
            p = config.WORKSPACE / "refs" / r["filename"]
            if p.exists(): images.append(p.read_bytes())
    for p in image_paths or []:
        try: images.append(open(p, "rb").read())
        except OSError: pass
    web = web_search(queries or [], cfg) if queries else []
    lines = []
    if structs:
        lines.append("REFERENCE STRUCTURES (existing Minecraft builds; borrow proportions and material ratios, do not copy):")
        for s in structs:
            mats = ", ".join(f"{m['block']} {int(m['share'] * 100)}%" for m in s["materials"][:10])
            lines.append(f"- {s['name']}: size x,y,z = {s['size_xyz']}, {s['blocks']} blocks; materials: {mats}")
    good = [w for w in web if "title" in w]
    if good:
        lines.append("WEB SEARCH HITS (titles/snippets only):")
        lines += [f"- {w['title']} — {w['snippet']} ({w['url']})" for w in good[:8]]
    if images:
        lines.append(f"{len(images[:4])} reference image(s) are attached: use them for silhouette, proportions and colour.")
    return {"structures": structs, "images": images[:4], "web": web, "text": "\n".join(lines)}
