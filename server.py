import os, sqlite3, hashlib, time, secrets, re
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

DB = os.getenv("DB_PATH", "campus.db")
ALLOW_DEMO = os.getenv("ALLOW_DEMO", "1") == "1"
HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

with conn() as c:
    c.executescript("""
    create table if not exists regs(id integer primary key, key text unique, name text, college text,
      branch text, score int, dom text, role text, code text unique, ref text, ip text, t int, demo int default 0);
    create table if not exists events(id integer primary key, type text, ref text, t int);""")

class Reg(BaseModel):
    contact: str; name: str; college: str; branch: str = "Other"
    score: int; dom: str; role: str; ref: str = "direct"; demo: bool = False

class Ev(BaseModel):
    type: str; ref: str = "direct"

@app.post("/api/event")
def event(e: Ev):
    if e.type not in {"quiz_start", "quiz_done", "share"}:
        raise HTTPException(400, "bad event")
    with conn() as c:
        c.execute("insert into events(type,ref,t) values(?,?,?)", (e.type, e.ref[:20], int(time.time()*1000)))
    return {"ok": True}

@app.post("/api/register")
def register(r: Reg, req: Request):
    contact = r.contact.strip().lower()
    ok = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact) or re.fullmatch(r"\+?\d{10,13}", contact)
    if not ok: raise HTTPException(400, "Enter a valid email or 10-digit phone number.")
    if len(r.name.strip()) < 2 or len(r.college.strip()) < 3: raise HTTPException(400, "Name or college looks invalid.")
    if not 0 <= r.score <= 100: raise HTTPException(400, "bad score")
    key = hashlib.sha256(contact.encode()).hexdigest()
    ip = req.client.host if req.client else "?"
    demo = 1 if (r.demo and ALLOW_DEMO) else 0
    with conn() as c:
        old = c.execute("select * from regs where key=?", (key,)).fetchone()
        if old: return public(old)                      # duplicate contact: return existing record
        if not demo:
            n = c.execute("select count(*) from regs where ip=? and t>? and demo=0",
                          (ip, int(time.time()*1000) - 3600_000)).fetchone()[0]
            if n >= 5: raise HTTPException(429, "Too many registrations from this network. Try later.")
        ref = r.ref if c.execute("select 1 from regs where code=?", (r.ref,)).fetchone() else "direct"
        code = (re.sub(r"[^A-Za-z]", "", r.name)[:3] + secrets.token_hex(2)).upper()
        c.execute("insert into regs(key,name,college,branch,score,dom,role,code,ref,ip,t,demo) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (key, r.name.strip()[:40], r.college.strip()[:60], r.branch[:10], r.score, r.dom[:6], r.role[:6],
                   code, ref, ip, int(time.time()*1000), demo))
        return public(c.execute("select * from regs where code=?", (code,)).fetchone())

def public(row):  # never expose contact hash or IP
    return {k: row[k] for k in ("name", "college", "branch", "score", "dom", "role", "code", "ref", "t")} | {"demo": bool(row["demo"])}

@app.get("/api/state")
def state():
    with conn() as c:
        regs = [public(r) for r in c.execute("select * from regs order by t")]
        evs = [dict(r) for r in c.execute("select type,ref,t from events")]
    return {"regs": regs, "evs": evs}

@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "index.html"))

@app.get("/api/admin/csv")
def export_csv(key: str = ""):
    import csv, io
    from fastapi.responses import Response
    need = os.getenv("ADMIN_KEY", "")
    if need and key != need: raise HTTPException(403, "bad key")
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["name", "college", "branch", "score", "role", "code", "referred_by", "time_ms", "demo"])
    with conn() as c:
        for r in c.execute("select * from regs order by t"):
            w.writerow([r["name"], r["college"], r["branch"], r["score"], r["role"], r["code"], r["ref"], r["t"], r["demo"]])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=registrations.csv"})
