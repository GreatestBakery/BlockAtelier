"""作品库: 每个作品一个文件夹 (所有产物都是普通文件，可直接拷走)，SQLite 只做索引和检索。"""
import json, shutil, sqlite3, time, uuid
from contextlib import contextmanager
from pathlib import Path
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS builds(
  id TEXT PRIMARY KEY, title TEXT, prompt TEXT, mode TEXT, version TEXT, provider TEXT, model TEXT,
  size TEXT, blocks INTEGER, tags TEXT DEFAULT '', favorite INTEGER DEFAULT 0, notes TEXT DEFAULT '',
  parent_id TEXT, created REAL, report TEXT);
CREATE TABLE IF NOT EXISTS refs(
  id TEXT PRIMARY KEY, name TEXT, filename TEXT, kind TEXT, tags TEXT DEFAULT '', summary TEXT, created REAL);
"""


def _dirs():
    for d in ("builds", "refs", "uploads"):
        (config.WORKSPACE / d).mkdir(parents=True, exist_ok=True)


@contextmanager
def db():
    _dirs()
    con = sqlite3.connect(config.WORKSPACE / "library.db")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def new_id(): return time.strftime("%y%m%d-") + uuid.uuid4().hex[:6]
def build_dir(bid):
    d = config.WORKSPACE / "builds" / bid; d.mkdir(parents=True, exist_ok=True); return d


def _row(r):
    d = dict(r)
    d["size"] = json.loads(d["size"] or "[]"); d["report"] = json.loads(d.get("report") or "{}")
    d["tags"] = [t for t in (d["tags"] or "").split(",") if t]
    bd = config.WORKSPACE / "builds" / d["id"]
    d["files"] = sorted(p.name for p in bd.iterdir() if p.is_file()) if bd.exists() else []
    return d


def save_build(rec):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO builds(id,title,prompt,mode,version,provider,model,size,blocks,tags,favorite,notes,parent_id,created,report)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rec["id"], rec.get("title", ""), rec.get("prompt", ""), rec.get("mode", "text"), rec.get("version", ""),
                     rec.get("provider", ""), rec.get("model", ""), json.dumps(rec.get("size", [])), rec.get("blocks", 0),
                     ",".join(rec.get("tags", [])), int(rec.get("favorite", 0)), rec.get("notes", ""), rec.get("parent_id"),
                     rec.get("created", time.time()), json.dumps(rec.get("report", {}), ensure_ascii=False)))
    return get_build(rec["id"])


def get_build(bid):
    with db() as con:
        r = con.execute("SELECT * FROM builds WHERE id=?", (bid,)).fetchone()
    return _row(r) if r else None


def list_builds(q="", favorite=False, limit=200):
    sql, args = "SELECT * FROM builds WHERE 1=1", []
    if q:
        sql += " AND (title LIKE ? OR prompt LIKE ? OR tags LIKE ? OR notes LIKE ?)"; args += [f"%{q}%"] * 4
    if favorite: sql += " AND favorite=1"
    sql += " ORDER BY created DESC LIMIT ?"; args.append(limit)
    with db() as con:
        return [_row(r) for r in con.execute(sql, args).fetchall()]


def update_build(bid, patch):
    cols = {k: v for k, v in patch.items() if k in ("title", "notes", "favorite", "tags")}
    if "tags" in cols and isinstance(cols["tags"], list): cols["tags"] = ",".join(t.strip() for t in cols["tags"] if t.strip())
    if "favorite" in cols: cols["favorite"] = int(bool(cols["favorite"]))
    if cols:
        with db() as con:
            con.execute(f"UPDATE builds SET {','.join(k + '=?' for k in cols)} WHERE id=?", [*cols.values(), bid])
    return get_build(bid)


def delete_build(bid):
    with db() as con: con.execute("DELETE FROM builds WHERE id=?", (bid,))
    shutil.rmtree(config.WORKSPACE / "builds" / bid, ignore_errors=True)


# ---- 参考库 ----
def add_ref(name, filename, kind, summary, tags=""):
    rid = uuid.uuid4().hex[:8]
    with db() as con:
        con.execute("INSERT INTO refs VALUES(?,?,?,?,?,?,?)", (rid, name, filename, kind, tags, json.dumps(summary, ensure_ascii=False), time.time()))
    return rid


def list_refs():
    with db() as con:
        out = []
        for r in con.execute("SELECT * FROM refs ORDER BY created DESC").fetchall():
            d = dict(r); d["summary"] = json.loads(d["summary"] or "{}"); out.append(d)
        return out


def get_ref(rid):
    return next((r for r in list_refs() if r["id"] == rid), None)


def delete_ref(rid):
    r = get_ref(rid)
    if r:
        (config.WORKSPACE / "refs" / r["filename"]).unlink(missing_ok=True)
        with db() as con: con.execute("DELETE FROM refs WHERE id=?", (rid,))
