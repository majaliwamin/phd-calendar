"""HTTP layer for the communications engine. Every route enforces role permissions on the server."""
import hmac, json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
import comms, db

router = APIRouter()

def who(req, perm):
    h = req.headers.get("authorization", "")
    with db.conn() as c:
        s = comms.auth(c, h[7:] if h.lower().startswith("bearer ") else "")
    if not s: raise HTTPException(401, "Sign in with a staff access token (Communications → Access).")
    if not comms.can(s["role"], perm): raise HTTPException(403, "Your role is not permitted to do this.")
    return s

def guard(fn):
    try: return fn()
    except (ValueError, PermissionError) as e: raise HTTPException(403 if isinstance(e, PermissionError) else 400, str(e))

@router.get("/api/comms/whoami")
def whoami(req: Request):
    h = req.headers.get("authorization", "")
    with db.conn() as c: s = comms.auth(c, h[7:] if h.lower().startswith("bearer ") else "")
    if not s: raise HTTPException(401, "Not signed in")
    return {"name": s["name"], "role": s["role"], "perms": sorted(comms.PERMS[s["role"]]), "tz": "Africa/Blantyre"}

@router.post("/api/comms/staff")
async def staff(req: Request):
    s = who(req, "*"); b = await req.json()
    with db.conn() as c:
        t = guard(lambda: comms.new_staff(c, b["name"], b["role"], b.get("person_id") or None)); comms.audit(c, s["name"], "new_staff", b["role"])
    return {"token": t, "note": "Shown once – store it securely."}

@router.get("/api/comms/config")
def get_config(req: Request):
    who(req, "*")
    with db.conn() as c:
        cf = comms.cfg(c); lt = comms.one(c, "select v from csettings where k='last_test'")
    return {"settings": cf, "secrets": comms.masked(), "webhook_url": (cf["public_url"].rstrip("/") + "/webhooks/whatsapp") if cf["public_url"] else "(set Public URL first)",
            "last_test": json.loads(lt["v"]) if lt else None}

@router.put("/api/comms/config")
async def put_config(req: Request):
    s = who(req, "*"); b = await req.json()
    with db.conn() as c:
        guard(lambda: comms.set_cfg(c, b.get("settings", {}))); comms.save_secrets(b.get("secrets", {})); comms.audit(c, s["name"], "config_change", ",".join(b.get("settings", {}).keys()))
    return {"ok": True}

@router.post("/api/comms/test")
def test(req: Request):
    who(req, "*")
    with db.conn() as c: return comms.test_connection(c)

@router.get("/api/comms/stats")
def stats(req: Request):
    who(req, "view")
    with db.conn() as c:
        return {"stats": comms.stats(c), "queue": comms.rows(c, "select r.id,r.kind,r.offset_min,r.due,r.status,r.note,r.attempts,p.name person from reminders r left join people p on p.id=r.person_id where r.status in ('pending','failed') order by r.due limit 60"),
                "calls": comms.rows(c, "select c.*,p.name person from calls c left join people p on p.id=c.person_id order by c.id desc limit 30"),
                "inapp": comms.rows(c, "select * from inapp order by id desc limit 20"), "announcements": comms.rows(c, "select * from announcements order by id desc limit 20")}

@router.get("/api/comms/history")
def history(req: Request, module_id: int = 0, kind: str = "", status: str = ""):
    who(req, "view")
    with db.conn() as c:
        return comms.rows(c, "select r.id,r.kind,r.status,r.due,r.note,r.event_id,p.name person from reminders r left join people p on p.id=r.person_id where (?=0 or p.module_id=?) and (?='' or r.kind=?) and (?='' or r.status=?) order by r.id desc limit 200", module_id, module_id, kind, kind, status, status)

@router.get("/api/comms/people")
def people(req: Request):
    who(req, "people")
    with db.conn() as c:
        out = comms.rows(c, "select * from people where deleted=0 order by name")
        for p in out: p["consent"] = {t: comms.has_consent(c, p["id"], t) for t in comms.CTYPES}
    return out

@router.post("/api/comms/people")
async def save_person(req: Request):
    s = who(req, "people"); b = await req.json()
    with db.conn() as c:
        pid = guard(lambda: comms.save_person(c, b, b.get("id")))
        for t, v in (b.get("consent") or {}).items():
            if comms.has_consent(c, pid, t) != bool(v): guard(lambda: comms.set_consent(c, pid, t, "granted" if v else "withdrawn", b.get("consent_source", "recorded by " + s["name"])))
        comms.audit(c, s["name"], "person_saved", pid)
    return {"id": pid}

@router.post("/api/comms/people/{pid}/call-permission")
def ask_call_permission(pid: int, req: Request):
    s = who(req, "people")
    with db.conn() as c:
        p = comms.one(c, "select * from people where id=?", pid)
        if not p or not comms.has_consent(c, pid, "whatsapp_messages"): raise HTTPException(400, "Recipient has not opted into WhatsApp messages.")
        try: wid = comms.PROV.perm_request(c, p, "May the Academic Calendar call you on WhatsApp with session alerts?")
        except Exception as e: raise HTTPException(502, str(e))
        comms.log_msg(c, p, "out", wid, "[call permission request]", "sent"); comms.audit(c, s["name"], "call_permission_request", pid)
    return {"sent": True}


@router.get("/api/comms/student/agenda")
def student_agenda(req: Request):
    s = who(req, "student")
    if not s.get("person_id"): raise HTTPException(400, "This staff token is not linked to a student/person record.")
    with db.conn() as c:
        person = comms.one(c, "select * from people where id=? and deleted=0", s["person_id"])
        if not person: raise HTTPException(404, "Linked student profile not found.")
        events = comms.rows(c, "select * from events where deleted=0 and status!='cancelled' and ((? is not null and module_id=?) or (? is not null and facilitator_id=?)) order by date,start",
                            person["module_id"], person["module_id"], person["facilitator_id"], person["facilitator_id"])
        acked = {r["event_id"] for r in comms.rows(c, "select event_id from acks where person_id=?", person["id"])}
        notices = comms.rows(c, "select id,ts,text,ref from inapp where person_id=? order by id desc limit 30", person["id"])
        return {"person": {"id": person["id"], "name": person["name"], "role": person["role"]},
                "events": [{**e, "acknowledged": e["id"] in acked} for e in events], "notices": notices}

@router.post("/api/comms/student/ack/{event_id}")
def student_ack(event_id: int, req: Request):
    s = who(req, "student")
    if not s.get("person_id"): raise HTTPException(400, "This staff token is not linked to a student/person record.")
    with db.conn() as c:
        person = comms.one(c, "select * from people where id=? and deleted=0", s["person_id"])
        event = comms.one(c, "select * from events where id=? and deleted=0 and status!='cancelled'", event_id)
        if not person or not event: raise HTTPException(404, "Student or event not found.")
        assigned = (person["module_id"] and event["module_id"] == person["module_id"]) or (person["facilitator_id"] and event["facilitator_id"] == person["facilitator_id"])
        if not assigned: raise HTTPException(403, "This event is not assigned to your student profile.")
        c.execute("insert or ignore into acks(event_id,person_id,ts) values(?,?,?)", (event_id, person["id"], comms.iso(comms.now())))
        comms.audit(c, s["name"], "student_ack", event_id)
    return {"ok": True, "acknowledged": True}

@router.get("/api/comms/conversations")
def conversations(req: Request):
    who(req, "converse")
    with db.conn() as c:
        return comms.rows(c, "select m.phone, p.name, max(m.id) last_id, sum(case when m.direction='in' and m.unread=1 then 1 else 0 end) unread, (select body from messages x where x.id=max(m.id)) last_body from messages m left join people p on p.id=m.person_id group by m.phone order by last_id desc")

@router.get("/api/comms/conversations/{phone}")
def thread(phone: str, req: Request):
    s = who(req, "converse"); phone = "+" + phone.lstrip("+ ")
    with db.conn() as c:
        c.execute("update messages set unread=0 where phone=? and direction='in'", (phone,)); comms.audit(c, s["name"], "read_conversation", phone)
        return {"messages": comms.rows(c, "select * from messages where phone=? order by id", phone), "window_open": comms.window_open(c, phone)}

@router.post("/api/comms/conversations/{phone}/reply")
async def reply(phone: str, req: Request):
    s = who(req, "converse"); b = await req.json(); phone = "+" + phone.lstrip("+ ")
    with db.conn() as c:
        p = comms.person_by_phone(c, phone)
        if not p or not comms.has_consent(c, p["id"], "whatsapp_messages"): raise HTTPException(400, "Recipient is unknown or has not opted in.")
        ok, err = comms.deliver(c, p, b["text"], "reply"); comms.audit(c, s["name"], "reply", phone)
    if not ok: raise HTTPException(502, err)
    return {"sent": True}

@router.post("/api/comms/announce")
async def announce(req: Request):
    s = who(req, "announce"); b = await req.json()
    with db.conn() as c:
        return guard(lambda: comms.announce(c, s["name"], s["role"], b.get("text", ""), b.get("filter", {}), bool(b.get("confirm")), bool(b.get("emergency"))))

@router.get("/api/comms/reports")
def reports(req: Request):
    s = who(req, "reports")
    with db.conn() as c: return comms.rows(c, "select r.*, p.name reporter, m.code module from reports r left join people p on p.id=r.person_id left join modules m on m.id=r.module_id order by r.id desc")

@router.post("/api/comms/reports")
async def new_report(req: Request):
    h = req.headers.get("authorization", ""); b = await req.json()
    with db.conn() as c:
        s = comms.auth(c, h[7:] if h.lower().startswith("bearer ") else "")
        if not s or not (comms.can(s["role"], "submit") or comms.can(s["role"], "reports")): raise HTTPException(403, "Your role cannot submit reports.")
        pid = s["person_id"] or b.get("person_id")
        ref = comms.new_report(c, pid, b.get("module_id") or None, b.get("kind", "other"), b.get("body", ""))
    return {"ref": ref}

@router.put("/api/comms/reports/{rid}")
async def update_report(rid: int, req: Request):
    s = who(req, "reports"); b = await req.json()
    if s["role"] in ("hod", "dean"): raise HTTPException(403, "Read-only for your role; coordinators record verification.")
    with db.conn() as c: guard(lambda: comms.set_report(c, rid, b["status"], b.get("note", ""), s["name"]))
    return {"ok": True}

@router.get("/webhooks/whatsapp")
def wa_verify(request: Request):
    q = request.query_params; tok = comms.load_secrets().get("wa_verify_token")
    if tok and q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), tok): return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")

@router.post("/webhooks/whatsapp")
async def wa_hook(request: Request):
    raw = await request.body()
    if not comms.verify_sig(raw, request.headers.get("x-hub-signature-256"), comms.load_secrets().get("wa_app_secret")): raise HTTPException(403, "Bad signature")
    with db.conn() as c: comms.handle_wa(c, json.loads(raw or b"{}"))
    return PlainTextResponse("ok")

