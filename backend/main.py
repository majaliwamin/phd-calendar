"""FastAPI backend. Run: uvicorn main:app --port 8000"""
import os, json, uuid, base64, urllib.parse, shutil
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
import asyncio, threading
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
    threading.Thread(target=comms.asterisk_event_monitor, name="asterisk-ami-events", daemon=True).start()

def calendar_staff(r: Request, permission="calendar_view"):
    header = r.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    with db.conn() as c:
        staff = comms.auth(c, token)
    if not staff:
        raise HTTPException(401, "Sign in with your staff access token under WhatsApp & Communications → Access.")
    if not comms.can(staff["role"], permission):
        raise HTTPException(403, "Your staff role is not permitted to perform this calendar action.")
    return staff

def calendar_user(r: Request, permission="calendar_view"):
    return calendar_staff(r, permission)["name"]

def who(r: Request):
    return calendar_user(r, "calendar_edit")

def rows(c, sql, *a):
    return [dict(r) for r in c.execute(sql, a).fetchall()]

def validate_event(c, changes, existing=None):
    from datetime import date as _date
    merged = dict(existing or {})
    merged.update(changes)
    allowed = db.FIELDS["events"]
    unknown = set(changes) - allowed
    if unknown: raise HTTPException(400, "Unsupported event fields: " + ", ".join(sorted(unknown)))
    if not str(merged.get("title") or "").strip(): raise HTTPException(400, "Event title is required.")
    try: _date.fromisoformat(str(merged.get("date") or ""))
    except ValueError: raise HTTPException(400, "Enter a valid event date (YYYY-MM-DD).")
    start, end = merged.get("start"), merged.get("end")
    if bool(start) != bool(end): raise HTTPException(400, "Enter both start and end times, or leave both blank.")
    if start:
        import re
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(start)) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(end)):
            raise HTTPException(400, "Times must use 24-hour HH:MM format.")
        if start >= end: raise HTTPException(400, "End time must be later than start time.")
    if merged.get("status") not in (None, "scheduled", "cancelled"):
        raise HTTPException(400, "Event status must be scheduled or cancelled.")
    if merged.get("module_id"):
        if not c.execute("select 1 from modules where id=?", (merged["module_id"],)).fetchone(): raise HTTPException(400, "Selected module does not exist.")
    if merged.get("facilitator_id"):
        if not c.execute("select 1 from facilitators where id=? and deleted=0", (merged["facilitator_id"],)).fetchone(): raise HTTPException(400, "Selected facilitator does not exist.")

@app.get("/api/bootstrap")
def bootstrap(r: Request):
    staff = calendar_staff(r, "calendar_view")
    with db.conn() as c:
        if staff["role"] in ("student", "class_rep"):
            if not staff["person_id"]: raise HTTPException(400, "Student/class-representative account is not linked to a person record.")
            person = c.execute("select * from people where id=? and deleted=0", (staff["person_id"],)).fetchone()
            if not person: raise HTTPException(404, "Linked student profile not found.")
            mods = rows(c, "select * from modules where id=?", person["module_id"]) if person["module_id"] else []
            facs = rows(c, "select * from facilitators where id=? and deleted=0", person["facilitator_id"]) if person["facilitator_id"] else []
            events = rows(c, "select * from events where deleted=0 and ((? is not null and module_id=?) or (? is not null and facilitator_id=?))", person["module_id"], person["module_id"], person["facilitator_id"], person["facilitator_id"])
            history = rows(c, "select * from history where user=? order by id desc limit 100", staff["name"])
        else:
            mods = rows(c, "select * from modules")
            facs = rows(c, "select * from facilitators where deleted=0")
            events = rows(c, "select * from events where deleted=0")
            history = rows(c, "select * from history order by id desc limit 300")
        return {"modules": mods, "facilitators": facs, "events": events, "history": history,
                "settings": {r["k"]: r["v"] for r in c.execute("select * from settings")}}

@app.post("/api/events")
async def new_event(r: Request):
    u = who(r); b = await r.json()
    with db.conn() as c:
        validate_event(c, b)
        cur = c.execute("insert into events(deleted,kind) values(1,?)", (b.pop("kind", "session"),))
        eid = cur.lastrowid
        db.update(c, u, "events", eid, {**b, "deleted": 0})  # logged as creation (deleted 1 -> 0)
    return {"id": eid}

@app.put("/api/events/{eid}")
async def put_event(eid: int, r: Request):
    u = who(r); b = await r.json(); ch = b.get("changes")
    if not isinstance(ch, dict): raise HTTPException(400, "Event changes must be an object.")
    with db.conn() as c:
        row = c.execute("select * from events where id=? and deleted=0", (eid,)).fetchone()
        if not row: raise HTTPException(404, "Event not found.")
        validate_event(c, ch, dict(row))
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
async def convert(r: Request, file: UploadFile = File(...)):
    calendar_user(r, "calendar_view")
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
def undo(r: Request):
    calendar_user(r, "calendar_edit")
    with db.conn() as c: return {"ok": db.undo(c)}

@app.post("/api/redo")
def redo(r: Request):
    calendar_user(r, "calendar_edit")
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
def backup(r: Request):
    calendar_user(r, "*")
    with db.conn() as c:
        calendar_tables = ("modules", "facilitators", "events", "history", "settings")
        comms_tables = ("staff", "people", "consents", "event_sigs", "reminders", "messages", "calls", "asterisk_channels", "acks", "inapp", "reports", "announcements", "csettings", "audit")
        d = {t: rows(c, f"select * from {t}") for t in calendar_tables}
        d["communications"] = {t: rows(c, f"select * from {t}") for t in comms_tables}
    d["avatars"] = {f["avatar"]: base64.b64encode(open(os.path.join(db.UPLOADS, f["avatar"]), "rb").read()).decode()
                    for f in d["facilitators"] if f["avatar"] and os.path.exists(os.path.join(db.UPLOADS, f["avatar"]))}
    return Response(json.dumps(d), media_type="application/json", headers={"Content-Disposition": "attachment; filename=calendar-backup.json"})

@app.post("/api/restore")
async def restore_backup(r: Request):
    calendar_user(r, "*")
    d = await r.json()
    tables = ("modules", "facilitators", "events", "history", "settings")
    if not isinstance(d, dict) or any(not isinstance(d.get(t), list) for t in tables) or not isinstance(d.get("avatars", {}), dict):
        raise HTTPException(400, "Invalid backup: required tables or avatar map are missing.")
    # Validate avatar payloads before changing the live database.
    avatars = {}
    try:
        for name, payload in d.get("avatars", {}).items():
            safe = os.path.basename(name)
            if safe != name or not safe.lower().endswith(".jpg") or not isinstance(payload, str): raise ValueError("Invalid avatar entry")
            raw = base64.b64decode(payload, validate=True)
            if len(raw) > 8 * 1024 * 1024: raise ValueError("Avatar exceeds 8 MB")
            avatars[safe] = raw
    except Exception as ex:
        raise HTTPException(400, f"Invalid avatar data: {ex}")
    allowed = {"modules": {"id","code","name","color"}, "facilitators": {"id","name","designation","module_id","contact","avatar","deleted"},
               "events": {"id","title","module_id","facilitator_id","venue","description","date","start","end","kind","series_id","overridden","deleted","status","stype"},
               "history": {"id","ts","user","entity","eid","label","field","old","new","undone"}, "settings": {"k","v"}}
    for table in tables:
        for row in d[table]:
            if not isinstance(row, dict) or not set(row).issubset(allowed[table]) or not row:
                raise HTTPException(400, f"Invalid {table} record in backup.")
    comms_tables = ("staff", "people", "consents", "event_sigs", "reminders", "messages", "calls", "asterisk_channels", "acks", "inapp", "reports", "announcements", "csettings", "audit")
    comms_data = d.get("communications", {})
    if comms_data and (not isinstance(comms_data, dict) or any(not isinstance(comms_data.get(t), list) for t in comms_tables)):
        raise HTTPException(400, "Invalid communications section in backup.")
    # Stage avatar bytes before touching live records, then restore database rows
    # atomically. Legacy calendar-only backups leave communications data unchanged.
    stage_dir = os.path.join(db.UPLOADS, ".restore-" + uuid.uuid4().hex)
    try:
        os.makedirs(stage_dir, exist_ok=True)
        for name, raw in avatars.items():
            with open(os.path.join(stage_dir, name), "wb") as f: f.write(raw)
    except Exception as ex:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise HTTPException(400, f"Could not stage backup avatars; no database records were changed: {ex}")
    try:
        with db.conn() as c:
            c.execute("begin immediate")
            for t in tables:
                c.execute(f"delete from {t}")
                for row in d[t]:
                    cols=list(row)
                    c.execute(f"insert into {t}({','.join(cols)}) values({','.join('?' * len(cols))})", [row[k] for k in cols])
            if comms_data:
                for t in comms_tables:
                    c.execute(f"delete from {t}")
                    columns={r[1] for r in c.execute(f"pragma table_info({t})")}
                    for row in comms_data[t]:
                        if not isinstance(row, dict) or not row or not set(row).issubset(columns):
                            raise ValueError(f"Invalid {t} record in backup")
                        cols=list(row)
                        c.execute(f"insert into {t}({','.join(cols)}) values({','.join('?' * len(cols))})", [row[k] for k in cols])
    except Exception as ex:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise HTTPException(400, f"Backup database restore failed; SQLite transaction was rolled back: {ex}")
    try:
        for name in avatars:
            os.replace(os.path.join(stage_dir, name), os.path.join(db.UPLOADS, name))
    except Exception as ex:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise HTTPException(500, f"Database records were restored, but an avatar file could not be finalized: {ex}")
    shutil.rmtree(stage_dir, ignore_errors=True)
    return {"ok": True, "restored": {t: len(d[t]) for t in tables}, "communications": {t: len(comms_data.get(t, [])) for t in comms_tables} if comms_data else "unchanged (legacy backup)", "avatars": len(avatars)}

@app.get("/api/export/{fmt}")
def exp(fmt: str, r: Request, week: int = 0):
    calendar_user(r, "calendar_export")
    if not 0 <= week <= 5: raise HTTPException(400)
    if fmt == "pdf": return Response(export.pdf(week), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=week{11+week}.pdf"})
    if fmt == "docx": return Response(export.docx(week), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f"attachment; filename=week{11+week}.docx"})
    raise HTTPException(404)

@app.get("/api/ics")
def ics(r: Request):
    calendar_user(r, "calendar_export")
    def esc_ics(v):
        return str(v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PhD MNH Calendar//EN"]
    with db.conn() as c:
        for e in c.execute("select * from events where deleted=0"):
            d = e["date"].replace("-", "")
            L += ["BEGIN:VEVENT", f"UID:{e['id']}@mnh-calendar", f"SUMMARY:{esc_ics(e['title'])}"]
            L += [f"DTSTART:{d}T{e['start'].replace(':','')}00", f"DTEND:{d}T{e['end'].replace(':','')}00"] if e["start"] else [f"DTSTART;VALUE=DATE:{d}"]
            L += [f"LOCATION:{esc_ics(e['venue'])}", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return Response("\r\n".join(L), media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=calendar.ics"})

os.makedirs(db.UPLOADS, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=db.UPLOADS), name="uploads")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
