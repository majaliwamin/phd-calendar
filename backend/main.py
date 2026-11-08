"""FastAPI backend. Run: uvicorn main:app --port 8000"""
import os, json, uuid, base64, urllib.parse
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
import asyncio
import db, export, images, comms
from comms_api import router as comms_router

app = FastAPI(title="PhD MNH Calendar")
WEB = os.path.join(os.path.dirname(db.BASE), "web")

app.include_router(comms_router)

async def _worker():
    """Reminder/call queue: runs on the server, so it keeps working when no browser is open."""
    def cycle():
        with db.conn() as c:
            return comms.tick(c)
    while True:
        try:
            await asyncio.to_thread(cycle)
        except Exception as e:
            print("[comms] worker error:", e)
        await asyncio.sleep(30)

@app.on_event("startup")
async def _start():
    db.init()
    with db.conn() as c:
        comms.init(c)
        comms.bootstrap_admin(c)
    asyncio.create_task(_worker())

def who(r: Request):
    u = urllib.parse.unquote(r.headers.get("x-editor", "")).strip()
    if not u:
        raise HTTPException(400, "Editor profile required")
    return u

def rows(c, sql, *a):
    return [dict(r) for r in c.execute(sql, a).fetchall()]

@app.get("/api/bootstrap")
def bootstrap():
    with db.conn() as c:
        return {"modules": rows(c, "select * from modules"),
                "facilitators": rows(c, "select * from facilitators where deleted=0"),
                "events": rows(c, "select * from events where deleted=0"),
                "assignments": rows(c, "select * from assignments where deleted=0"),
                "history": rows(c, "select * from history order by id desc limit 300"),
                "settings": {r["k"]: r["v"] for r in c.execute("select * from settings")}}

@app.post("/api/events")
async def new_event(r: Request):
    u = who(r); b = await r.json()
    with db.conn() as c:
        cur = c.execute("insert into events(deleted,kind) values(1,?)", (b.pop("kind", "session"),))
        eid = cur.lastrowid
        db.update(c, u, "events", eid, {**b, "deleted": 0})  # logged as creation (deleted 1 -> 0)
    return {"id": eid}

@app.put("/api/events/{eid}")
async def put_event(eid: int, r: Request):
    u = who(r); b = await r.json(); ch = b["changes"]
    with db.conn() as c:
        row = c.execute("select * from events where id=?", (eid,)).fetchone()
        if b.get("scope") == "series" and row["series_id"]:
            ch.pop("date", None)
            for o in c.execute("select id from events where series_id=? and overridden=0 and deleted=0 and id!=?", (row["series_id"], eid)).fetchall():
                db.update(c, u, "events", o["id"], ch)
            db.update(c, u, "events", eid, ch)
        else:
            db.update(c, u, "events", eid, ch)
            if row["series_id"]:
                c.execute("update events set overridden=1 where id=?", (eid,))
    return {"ok": True}

@app.delete("/api/events/{eid}")
def del_event(eid: int, r: Request):
    with db.conn() as c:
        db.update(c, who(r), "events", eid, {"deleted": 1})
    return {"ok": True}

@app.post("/api/assignments")
async def new_assignment(r: Request):
    u = who(r); b = await r.json()
    with db.conn() as c:
        aid = c.execute(
            "insert into assignments(title,module_id,due_date,due_time,deleted) values('',0,'','','1')"
        ).lastrowid
        db.update(c, u, "assignments", aid, {**b, "deleted": 0})
    return {"id": aid}

@app.put("/api/assignments/{aid}")
async def put_assignment(aid: int, r: Request):
    u = who(r); b = await r.json()
    with db.conn() as c:
        db.update(c, u, "assignments", aid, b["changes"])
    return {"ok": True}

@app.delete("/api/assignments/{aid}")
def del_assignment(aid: int, r: Request):
    with db.conn() as c:
        db.update(c, who(r), "assignments", aid, {"deleted": 1})
    return {"ok": True}
@app.post("/api/facilitators")
async def new_fac(r: Request):
    u = who(r); b = await r.json()
    with db.conn() as c:
        eid = c.execute("insert into facilitators(deleted) values(1)").lastrowid
        db.update(c, u, "facilitators", eid, {**b, "deleted": 0})
    return {"id": eid}

@app.put("/api/{ent}/{eid}")
async def put_generic(ent: str, eid: int, r: Request):
    if ent not in ("facilitators", "modules", "settings"):
        raise HTTPException(404)
    with db.conn() as c:
        db.update(c, who(r), ent, eid, await r.json())
    return {"ok": True}

@app.delete("/api/facilitators/{eid}")
def del_fac(eid: int, r: Request):
    with db.conn() as c:
        db.update(c, who(r), "facilitators", eid, {"deleted": 1})
    return {"ok": True}

@app.post("/api/facilitators/{eid}/avatar")
async def avatar(eid: int, r: Request, file: UploadFile = File(...)):
    u = who(r)
    if os.path.splitext(file.filename or "")[1].lower() not in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"):
        raise HTTPException(415, "Use a JPG, PNG, WebP or HEIC photo.")
    with db.conn() as c:
        if not c.execute("select 1 from facilitators where id=? and deleted=0", (eid,)).fetchone():
            raise HTTPException(404, "Facilitator not found")
    try:
        jpg = images.to_jpeg(await file.read(), file.filename or "")
    except ValueError as e:
        raise HTTPException(415, str(e))
    name = uuid.uuid4().hex + ".jpg"
    with open(os.path.join(db.UPLOADS, name), "wb") as f:
        f.write(jpg)
    with db.conn() as c:
        db.update(c, u, "facilitators", eid, {"avatar": name})
    return {"avatar": name}

@app.post("/api/convert")
async def convert(file: UploadFile = File(...)):
    try:
        return Response(images.to_jpeg(await file.read(), file.filename or ""), media_type="image/jpeg")
    except ValueError as e:
        raise HTTPException(415, str(e))

@app.delete("/api/facilitators/{eid}/avatar")
def rm_avatar(eid: int, r: Request):
    with db.conn() as c:
        db.update(c, who(r), "facilitators", eid, {"avatar": None})
    return {"ok": True}

@app.post("/api/undo")
def undo():
    with db.conn() as c: return {"ok": db.undo(c)}

@app.post("/api/redo")
def redo():
    with db.conn() as c: return {"ok": db.redo(c)}

@app.post("/api/history/{hid}/restore")
def restore(hid: int, r: Request):
    """Restore the previous value recorded by one history entry (logged as a new change)."""
    with db.conn() as c:
        h = c.execute("select * from history where id=?", (hid,)).fetchone()
        if not h: raise HTTPException(404)
        db.update(c, who(r), h["entity"], h["eid"], {h["field"]: h["old"]})
    return {"ok": True}

@app.get("/api/backup")
def backup():
    with db.conn() as c:
        d = {t: rows(c, f"select * from {t}") for t in ("modules", "facilitators", "events", "assignments", "history", "settings")}
    d["avatars"] = {f["avatar"]: base64.b64encode(open(os.path.join(db.UPLOADS, f["avatar"]), "rb").read()).decode()
                    for f in d["facilitators"] if f["avatar"] and os.path.exists(os.path.join(db.UPLOADS, f["avatar"]))}
    return Response(json.dumps(d), media_type="application/json", headers={"Content-Disposition": "attachment; filename=calendar-backup.json"})

@app.post("/api/restore")
async def restore_backup(r: Request):
    who(r); d = await r.json()
    for n, b in d.get("avatars", {}).items():
        open(os.path.join(db.UPLOADS, os.path.basename(n)), "wb").write(base64.b64decode(b))
    with db.conn() as c:
        for t in ("modules", "facilitators", "events", "assignments", "history", "settings"):
            c.execute(f"delete from {t}")
            for row in d.get(t, []):
                c.execute(f"insert into {t}({','.join(row)}) values({','.join('?' * len(row))})", list(row.values()))
    return {"ok": True}

@app.get("/api/export/{fmt}")
def exp(fmt: str, week: int = 0):
    if not 0 <= week <= 5: raise HTTPException(400)
    if fmt == "pdf": return Response(export.pdf(week), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=week{11+week}.pdf"})
    if fmt == "docx": return Response(export.docx(week), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f"attachment; filename=week{11+week}.docx"})
    raise HTTPException(404)

@app.get("/api/ics")
def ics():
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PhD MNH Calendar//EN"]
    with db.conn() as c:
        for e in c.execute("select * from events where deleted=0"):
            d = e["date"].replace("-", "")
            L += ["BEGIN:VEVENT", f"UID:{e['id']}@mnh-calendar", f"SUMMARY:{e['title']}"]
            L += [f"DTSTART:{d}T{e['start'].replace(':','')}00", f"DTEND:{d}T{e['end'].replace(':','')}00"] if e["start"] else [f"DTSTART;VALUE=DATE:{d}"]
            L += [f"LOCATION:{e['venue'] or ''}", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return Response("\r\n".join(L), media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=calendar.ics"})

os.makedirs(db.UPLOADS, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=db.UPLOADS), name="uploads")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
