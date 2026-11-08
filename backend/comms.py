"""Communications engine: consent, reminder queue, WhatsApp Cloud API, Twilio phone fallback,
two-way inbox, announcements, class-rep reports and escalation. Standard library only."""
import json, os, re, hmac, hashlib, secrets, urllib.request, urllib.parse, urllib.error, datetime as dt
from zoneinfo import ZoneInfo
import db

TZ = ZoneInfo("Africa/Blantyre")
SECRET_FILE = os.path.join(db.DATA, "secrets.json")      # backend-only, never served or returned unmasked
SECRET_KEYS = ("wa_token", "wa_phone_id", "wa_waba_id", "wa_verify_token", "wa_app_secret", "tw_sid", "tw_token", "tw_from")
DEFAULTS = {"offsets": [1440, 120, 30, 10, 0], "call_at_start": True, "call_scope": "all", "retries": 2, "retry_gap_min": 5,
            "call_start": "07:00", "call_end": "20:00", "quiet_start": "21:00", "quiet_end": "06:00",
            "tpl_reminder": "academic_reminder", "tpl_notice": "academic_notice", "tpl_lang": "en", "graph": "v21.0",
            "public_url": "", "esc_hod_h": 48, "esc_dean_h": 120, "max_bulk": 25, "call_lang": "en-GB"}
PERMS = {"admin": {"*"}, "coordinator": {"view", "announce", "reports", "converse", "people"},
         "hod": {"view", "announce", "reports"}, "dean": {"view", "announce", "reports"}, "class_rep": {"submit"}}
CTYPES = ("whatsapp_messages", "whatsapp_calls", "phone_calls")
CLOCK = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY, name TEXT, role TEXT, token_hash TEXT UNIQUE, person_id INTEGER, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT, role TEXT, phone TEXT UNIQUE, lang TEXT DEFAULT 'en', module_id INTEGER, facilitator_id INTEGER, cohort TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS consents(id INTEGER PRIMARY KEY, person_id INTEGER, ctype TEXT, status TEXT, ts TEXT, source TEXT, withdrawn_ts TEXT, expires_ts TEXT);
CREATE TABLE IF NOT EXISTS event_sigs(event_id INTEGER PRIMARY KEY, sig TEXT);
CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, event_id INTEGER, person_id INTEGER, kind TEXT, offset_min INTEGER, due TEXT, status TEXT, ev_sig TEXT,
  ikey TEXT UNIQUE, note TEXT, attempts INTEGER DEFAULT 0, last_try TEXT, emergency INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, person_id INTEGER, phone TEXT, direction TEXT, wa_id TEXT UNIQUE, body TEXT, mtype TEXT, status TEXT, ts TEXT, event_id INTEGER, error TEXT, unread INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY, person_id INTEGER, event_id INTEGER, provider TEXT, call_id TEXT, status TEXT, attempt INTEGER, ts TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS acks(event_id INTEGER, person_id INTEGER, ts TEXT, PRIMARY KEY(event_id, person_id));
CREATE TABLE IF NOT EXISTS inapp(id INTEGER PRIMARY KEY, person_id INTEGER, ts TEXT, text TEXT, ref TEXT);
CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, ref TEXT, module_id INTEGER, kind TEXT, body TEXT, person_id INTEGER, status TEXT, level INTEGER DEFAULT 0, created TEXT, updated TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS announcements(id INTEGER PRIMARY KEY, ts TEXT, actor TEXT, text TEXT, filt TEXT, count INTEGER, emergency INTEGER);
CREATE TABLE IF NOT EXISTS csettings(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, actor TEXT, action TEXT, detail TEXT);
"""

def now(): return CLOCK() if CLOCK else dt.datetime.now(TZ)
def iso(d): return d.astimezone(TZ).isoformat(timespec="seconds")
def rows(c, sql, *a): return [dict(r) for r in c.execute(sql, a).fetchall()]
def one(c, sql, *a):
    r = c.execute(sql, a).fetchone(); return dict(r) if r else None
def init(c): c.executescript(SCHEMA)
def audit(c, actor, action, detail=""): c.execute("insert into audit(ts,actor,action,detail) values(?,?,?,?)", (iso(now()), actor, action, str(detail)[:500]))

# ---------- secrets / settings ----------
def load_secrets():
    try: return json.load(open(SECRET_FILE))
    except Exception: return {}
def save_secrets(d):
    s = load_secrets(); s.update({k: v for k, v in d.items() if k in SECRET_KEYS and v})
    os.makedirs(db.DATA, exist_ok=True); json.dump(s, open(SECRET_FILE, "w"))
    try: os.chmod(SECRET_FILE, 0o600)
    except Exception: pass
def masked():
    return {k: (("•••• " + v[-4:]) if v and k != "wa_phone_id" and k != "wa_waba_id" else v or "") for k, v in ((k, load_secrets().get(k, "")) for k in SECRET_KEYS)}
def cfg(c):
    d = dict(DEFAULTS)
    for r in c.execute("select * from csettings"):
        try: d[r["k"]] = json.loads(r["v"])
        except Exception: pass
    return d
def set_cfg(c, new):
    for k, v in new.items():
        if k not in DEFAULTS: continue
        if k == "offsets": v = sorted({int(x) for x in v if 0 <= int(x) <= 10080}, reverse=True)
        elif isinstance(DEFAULTS[k], bool): v = bool(v)
        elif isinstance(DEFAULTS[k], int): v = max(0, min(int(v), 100000))
        else: v = str(v).strip()
        c.execute("insert into csettings values(?,?) on conflict(k) do update set v=excluded.v", (k, json.dumps(v)))

# ---------- staff / roles ----------
def can(role, perm): p = PERMS.get(role, set()); return "*" in p or perm in p
def _h(t): return hashlib.sha256(t.encode()).hexdigest()
def new_staff(c, name, role, person_id=None):
    if role not in PERMS: raise ValueError("Unknown role")
    t = secrets.token_urlsafe(24)
    c.execute("insert into staff(name,role,token_hash,person_id) values(?,?,?,?)", (name, role, _h(t), person_id)); return t
def auth(c, tok): return one(c, "select * from staff where token_hash=? and active=1", _h(tok)) if tok else None
def bootstrap_admin(c):
    if c.execute("select count(*) from staff").fetchone()[0] == 0:
        t = new_staff(c, "Administrator", "admin")
        with open(os.path.join(db.DATA, "ADMIN_TOKEN.txt"), "w") as f: f.write(t)
        print(f"[comms] First-run admin token written to {os.path.join(db.DATA, 'ADMIN_TOKEN.txt')}")

# ---------- phones, people, consent ----------
def norm_phone(raw, cc="265"):
    s = re.sub(r"[\s\-().]", "", str(raw or ""))
    s = "+" + s[2:] if s.startswith("00") else s if s.startswith("+") else "+" + cc.lstrip("+") + s[1:] if s.startswith("0") else "+" + cc.lstrip("+") + s
    if not re.fullmatch(r"\+[1-9]\d{7,14}", s): raise ValueError("Enter a valid international number, e.g. +265 99 123 4567")
    if s.startswith("+265") and len(s) != 13: raise ValueError("Malawi numbers are +265 followed by 9 digits.")
    return s
def save_person(c, d, pid=None):
    phone = norm_phone(d.get("phone"), d.get("cc", "265"))
    f = (d["name"].strip(), d.get("role", "student"), phone, d.get("lang", "en"), d.get("module_id") or None, d.get("facilitator_id") or None, d.get("cohort") or None)
    if not f[0]: raise ValueError("Name required")
    if pid: c.execute("update people set name=?,role=?,phone=?,lang=?,module_id=?,facilitator_id=?,cohort=? where id=?", (*f, pid)); return pid
    return c.execute("insert into people(name,role,phone,lang,module_id,facilitator_id,cohort) values(?,?,?,?,?,?,?)", f).lastrowid
def set_consent(c, pid, ctype, status, source, expires=None):
    if ctype not in CTYPES or status not in ("granted", "withdrawn"): raise ValueError("Invalid consent")
    n = iso(now())
    c.execute("insert into consents(person_id,ctype,status,ts,source,withdrawn_ts,expires_ts) values(?,?,?,?,?,?,?)",
              (pid, ctype, status, n, source, n if status == "withdrawn" else None, expires))
def has_consent(c, pid, ctype):
    r = one(c, "select * from consents where person_id=? and ctype=? order by id desc limit 1", pid, ctype)
    return bool(r and r["status"] == "granted" and (not r["expires_ts"] or r["expires_ts"] > iso(now())))
def withdraw_all(c, pid, source):
    for t in CTYPES:
        if has_consent(c, pid, t): set_consent(c, pid, t, "withdrawn", source)
def person_by_phone(c, phone): return one(c, "select * from people where phone=? and deleted=0", phone)

# ---------- events -> text ----------
def ev(c, i): return one(c, "select * from events where id=?", i)
def ev_start(e): return dt.datetime.fromisoformat(f"{e['date']}T{e['start']}:00").replace(tzinfo=TZ)
def ev_end(e): return dt.datetime.fromisoformat(f"{e['date']}T{e['end'] or e['start']}:00").replace(tzinfo=TZ)
def sig_of(e): return hashlib.md5("|".join(str(e[k]) for k in ("date", "start", "end", "title", "venue", "facilitator_id", "module_id")).encode()).hexdigest()[:12]
def in_window(n, a, b):
    t = n.strftime("%H:%M"); return (a <= t < b) if a <= b else (t >= a or t < b)
def greet(n): return "Good morning" if n.hour < 12 else "Good afternoon" if n.hour < 17 else "Good evening"
_T = set("dr prof professor mr mrs ms miss mx rev reverend sir dame hon eng engr pastor fr chief lord lady madam mister".split())
def first_name(n):
    t = [x for x in re.sub(r"[.,()]", " ", n or "").split() if x]
    while len(t) > 1 and t[0].lower() in _T: t.pop(0)
    return t[0] if t else ""
def human(m): return f"{m // 60} hours" if m >= 60 and m % 60 == 0 else f"{m} minutes"
def details(c, e):
    m = one(c, "select * from modules where id=?", e["module_id"]) if e["module_id"] else None
    f = one(c, "select * from facilitators where id=?", e["facilitator_id"]) if e["facilitator_id"] else None
    st, en = ev_start(e), ev_end(e); mins = int((en - st).total_seconds() // 60)
    return m, f, st, en, mins
def reminder_text(c, p, e, off):
    m, f, st, en, mins = details(c, e); n = now()
    L = [f"{greet(n)}, {first_name(p['name'])}.", "",
         "Academic reminder: your session " + ("is due to begin now." if off == 0 else f"starts in {human(off)}."), ""]
    if m: L.append(f"Module: {m['code']} – {m['name']}")
    L += [f"Session: {e['title']}"] + ([f"Facilitator: {f['name']}"] if f else [])
    L += [f"Date: {st:%A %d %b %Y}", f"Time: {e['start']}–{e['end'] or '?'} ({human(mins) if mins else 'duration not set'})"]
    if e["venue"]: L.append(f"Venue: {e['venue']}")
    return "\n".join(L + ["", "Reply ACK to acknowledge, or STOP to opt out."])
def reminder_params(c, p, e):
    m, f, st, en, mins = details(c, e)
    return [first_name(p["name"]), m["code"] if m else "—", e["title"], f"{st:%a %d %b %Y}", f"{e['start']}–{e['end']}", f["name"] if f else "—", e["venue"] or "—"]
def notice_text(c, p, e, what):
    m, f, st, en, mins = details(c, e) if e["start"] else (None,) * 5
    base = f"Academic update: the session “{e['title']}”"
    return base + (" has been CANCELLED." if what == "cancelled" else f" has been rescheduled to {st:%A %d %b %Y}, {e['start']}–{e['end']}." + (f" Venue: {e['venue']}." if e["venue"] else ""))

# ---------- reminders ----------
def recipients_for(c, e):
    out = []
    for p in rows(c, "select * from people where deleted=0"):
        if (e["module_id"] and p["module_id"] == e["module_id"]) or (e["facilitator_id"] and p["facilitator_id"] == e["facilitator_id"]):
            if has_consent(c, p["id"], "whatsapp_messages"): out.append(p)
    return out
def add_rem(c, eid, pid, kind, off, due, sig, note=None, att=0, emergency=0):
    c.execute("insert or ignore into reminders(event_id,person_id,kind,offset_min,due,status,ev_sig,ikey,note,emergency) values(?,?,?,?,?,'pending',?,?,?,?)",
              (eid, pid, kind, off, iso(due), sig, f"{eid}:{pid}:{kind}:{off}:{sig}:{att}", note, emergency))
def queue(c, pid, text, kind="notice", eid=None, emergency=0):
    add_rem(c, eid, pid, kind, -1, now(), secrets.token_hex(4), text, emergency=emergency)
def sync(c):
    cf, n = cfg(c), now()
    for e in rows(c, "select * from events"):
        gone = bool(e["deleted"] or e["status"] == "cancelled")
        old = one(c, "select * from event_sigs where event_id=?", e["id"]); sig = "X" if gone else sig_of(e)
        if (old and old["sig"] == sig) or (not old and (gone or not e["start"])): continue
        if old:
            c.execute("update reminders set status='superseded' where event_id=? and status='pending' and kind in ('remind','call')", (e["id"],))
            if old["sig"] != "X" and (gone or e["start"]):
                for p in recipients_for(c, e): queue(c, p["id"], notice_text(c, p, e, "cancelled" if gone else "rescheduled"), "notice", e["id"])
        c.execute("insert into event_sigs values(?,?) on conflict(event_id) do update set sig=excluded.sig", (e["id"], sig))
        if gone or not e["start"]: continue
        st = ev_start(e)
        for p in recipients_for(c, e):
            for off in cf["offsets"]:
                if st - dt.timedelta(minutes=off) >= n - dt.timedelta(minutes=5): add_rem(c, e["id"], p["id"], "remind", off, st - dt.timedelta(minutes=off), sig)
            scope = cf["call_scope"] == "all" or (cf["call_scope"] == "exam" and e["kind"] == "exam")
            if cf["call_at_start"] and scope and has_consent(c, p["id"], "phone_calls") and st >= n - dt.timedelta(minutes=5):
                add_rem(c, e["id"], p["id"], "call", 0, st, sig)

# ---------- providers ----------
def http(url, data=None, headers=None, form=False, auth=None):
    body = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode() if data is not None else None
    h = dict(headers or {})
    if data is not None and not form: h["Content-Type"] = "application/json"
    if auth: h["Authorization"] = "Basic " + __import__("base64").b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, body, h), timeout=20) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {}
class Provider:
    def _wa(self, c, path, payload):
        s = load_secrets()
        if not (s.get("wa_token") and s.get("wa_phone_id")): raise RuntimeError("WhatsApp is not configured (token / phone number ID missing).")
        st, j = http(f"https://graph.facebook.com/{cfg(c)['graph']}/{s['wa_phone_id']}/{path}", payload, {"Authorization": "Bearer " + s["wa_token"]})
        if st >= 300: raise RuntimeError(f"WhatsApp API {st}: {(j.get('error') or {}).get('message', 'request failed')}")
        return j
    def msg(self, c, p, text, kind, params, window_open):
        to = p["phone"].lstrip("+"); f = cfg(c)
        if window_open:
            j = self._wa(c, "messages", {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}})
        else:   # outside the 24h customer-service window only approved templates may be sent
            name, vals = (f["tpl_reminder"], params) if kind == "remind" and params else (f["tpl_notice"], [" ".join(text.split())[:900]])
            j = self._wa(c, "messages", {"messaging_product": "whatsapp", "to": to, "type": "template", "template": {"name": name, "language": {"code": f["tpl_lang"]},
                 "components": [{"type": "body", "parameters": [{"type": "text", "text": str(v)} for v in vals]}]}})
        return j["messages"][0]["id"]
    def perm_request(self, c, p, text):
        j = self._wa(c, "messages", {"messaging_product": "whatsapp", "to": p["phone"].lstrip("+"), "type": "interactive",
             "interactive": {"type": "call_permission_request", "action": {"name": "call_permission_request"}, "body": {"text": text}}})
        return j["messages"][0]["id"]
    def call(self, c, p, text, attempt):
        s, f = load_secrets(), cfg(c)
        if not (s.get("tw_sid") and s.get("tw_token") and s.get("tw_from")): raise RuntimeError("Telephone provider (Twilio) is not configured.")
        data = {"To": p["phone"], "From": s["tw_from"], "Twiml": f'<Response><Say language="{f["call_lang"]}">{text.replace("&", "and").replace("<", " ")}</Say></Response>'}
        if f["public_url"]: data.update({"StatusCallback": f["public_url"].rstrip("/") + "/webhooks/twilio", "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"]})
        d = urllib.parse.urlencode(data, doseq=True).encode()
        req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{s['tw_sid']}/Calls.json", d,
              {"Authorization": "Basic " + __import__("base64").b64encode(f"{s['tw_sid']}:{s['tw_token']}".encode()).decode()})
        try:
            with urllib.request.urlopen(req, timeout=20) as r: return json.loads(r.read())["sid"]
        except urllib.error.HTTPError as e: raise RuntimeError(f"Twilio {e.code}: {e.read()[:200]!r}")
PROV = Provider()

def window_open(c, phone):
    r = one(c, "select ts from messages where phone=? and direction='in' order by id desc limit 1", phone)
    return bool(r and dt.datetime.fromisoformat(r["ts"]) > now() - dt.timedelta(hours=24))
def log_msg(c, p, d, wid, body, status, eid=None, err=None, phone=None, mtype="text", unread=0):
    c.execute("insert or ignore into messages(person_id,phone,direction,wa_id,body,mtype,status,ts,event_id,error,unread) values(?,?,?,?,?,?,?,?,?,?,?)",
              (p["id"] if p else None, phone or p["phone"], d, wid, body, mtype, status, iso(now()), eid, err, unread))
def deliver(c, p, text, kind="notice", params=None, eid=None):
    try: wid = PROV.msg(c, p, text, kind, params, window_open(c, p["phone"]))
    except Exception as ex:
        log_msg(c, p, "out", None, text, "failed", eid, str(ex)); return False, str(ex)
    log_msg(c, p, "out", wid, text, "sent", eid); return True, None
def call_text(c, p, e):
    m = details(c, e)[0]
    return f"Hello, this is your Academic Calendar reminder. Your {(m['name'] if m else e['title'])} session is due to begin now. Please check your WhatsApp messages for the session details."

def tick(c):
    """One worker cycle: sync calendar changes, send due items, escalate reports. Runs server-side (browser not needed)."""
    sync(c); n = 0
    for r in rows(c, "select * from reminders where status='pending' and due<=? order by due", iso(now())): process(c, r); n += 1
    escalate(c); return n
def process(c, r):
    cf, n, p = cfg(c), now(), one(c, "select * from people where id=?", r["person_id"])
    def done(st, note=None): c.execute("update reminders set status=?,note=coalesce(?,note),last_try=? where id=?", (st, note, iso(n), r["id"]))
    def fail(err):
        a = r["attempts"] + 1
        if a <= cf["retries"]: c.execute("update reminders set attempts=?,due=?,last_try=?,note=? where id=?", (a, iso(n + dt.timedelta(minutes=cf["retry_gap_min"])), iso(n), err, r["id"]))
        else:
            done("failed", err); c.execute("insert into inapp(person_id,ts,text,ref) values(?,?,?,?)", (r["person_id"], iso(n), f"Undelivered {r['kind']}: {err}", f"reminder:{r['id']}"))
    if not p or p["deleted"]: return done("skipped", "no recipient")
    e = ev(c, r["event_id"]) if r["event_id"] else None
    if r["kind"] == "call":
        if not e or e["deleted"] or e["status"] == "cancelled": return done("cancelled")
        if not has_consent(c, p["id"], "phone_calls"): return done("skipped", "no call consent")
        if one(c, "select 1 x from acks where event_id=? and person_id=?", e["id"], p["id"]): return done("skipped", "already acknowledged")
        if not in_window(n, cf["call_start"], cf["call_end"]): return done("skipped", "outside calling hours")
        try: sid = PROV.call(c, p, call_text(c, p, e), r["attempts"] + 1)
        except Exception as ex: c.execute("insert into calls(person_id,event_id,provider,status,attempt,ts,note) values(?,?,?,?,?,?,?)", (p["id"], e["id"], "twilio", "failed", r["attempts"] + 1, iso(n), str(ex))); return fail(str(ex))
        c.execute("insert into calls(person_id,event_id,provider,call_id,status,attempt,ts) values(?,?,?,?,?,?,?)", (p["id"], e["id"], "twilio", sid, "initiated", r["attempts"] + 1, iso(n))); return done("sent")
    if not has_consent(c, p["id"], "whatsapp_messages"): return done("skipped", "no message consent")
    if e and r["kind"] == "remind" and (e["deleted"] or e["status"] == "cancelled"): return done("cancelled")
    if not r["emergency"] and in_window(n, cf["quiet_start"], cf["quiet_end"]):
        return done("expired", "quiet hours") if n - dt.datetime.fromisoformat(r["due"]) > dt.timedelta(hours=3) else None
    text = reminder_text(c, p, e, r["offset_min"]) if r["kind"] == "remind" else r["note"]
    ok, err = deliver(c, p, text, r["kind"], reminder_params(c, p, e) if r["kind"] == "remind" else None, r["event_id"])
    done("sent") if ok else fail(err)
def twilio_status(c, sid, status):
    m = {"queued": "initiated", "initiated": "initiated", "ringing": "ringing", "in-progress": "answered", "completed": "answered", "busy": "rejected", "no-answer": "unanswered", "failed": "failed", "canceled": "failed"}.get(status)
    cl = one(c, "select * from calls where call_id=?", sid)
    if not m or not cl or cl["status"] == "answered": return
    c.execute("update calls set status=? where id=?", (m, cl["id"])); cf = cfg(c)
    if m in ("unanswered", "rejected", "failed") and cl["attempt"] <= cf["retries"]:
        e = ev(c, cl["event_id"])
        if e and not e["deleted"] and e["status"] != "cancelled":
            add_rem(c, e["id"], cl["person_id"], "call", 0, now() + dt.timedelta(minutes=cf["retry_gap_min"]), sig_of(e), att=cl["attempt"])
            c.execute("update reminders set attempts=? where ikey=?", (cl["attempt"], f"{e['id']}:{cl['person_id']}:call:0:{sig_of(e)}:{cl['attempt']}"))
def verify_sig(raw, header, secret):
    return bool(secret and header and hmac.compare_digest("sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), header))
def verify_twilio(url, params, header, token):
    s = url + "".join(k + params[k] for k in sorted(params))
    return bool(token and header and hmac.compare_digest(__import__("base64").b64encode(hmac.new(token.encode(), s.encode(), hashlib.sha1).digest()).decode(), header))

# ---------- inbound WhatsApp ----------
def upcoming(c, p, limit=3):
    n = now(); out = []
    for e in rows(c, "select * from events where deleted=0 and start is not null and status!='cancelled' order by date,start"):
        if ev_start(e) > n and ((p["module_id"] and e["module_id"] == p["module_id"]) or (p["facilitator_id"] and e["facilitator_id"] == p["facilitator_id"])): out.append(e)
    return out[:limit]
def autoreply(c, p, text, bid=None):
    t = (text or "").lower().strip()
    if bid and bid.startswith("ack:"): t = "ack " + bid[4:]
    if re.search(r"\b(stop|unsubscribe|opt ?out)\b", t): withdraw_all(c, p["id"], "whatsapp-stop"); return "You have been opted out of academic WhatsApp messages and calls. Reply START to an administrator to opt in again."
    if t.startswith("ack"):
        ids = [int(x) for x in re.findall(r"\d+", t)] or [e["id"] for e in upcoming(c, p) if ev_start(e) < now() + dt.timedelta(hours=24)]
        for i in ids: c.execute("insert or ignore into acks values(?,?,?)", (i, p["id"], iso(now())))
        return "Thank you – your acknowledgement is recorded. (This does not record attendance.)"
    if re.search(r"exam", t):
        ex = [e for e in rows(c, "select * from events where deleted=0 and kind='exam' and status!='cancelled' order by date") if not p["module_id"] or e["module_id"] == p["module_id"]]
        return "\n".join(f"{e['title']}: {e['date']} – " + (f"{e['start']}–{e['end']}" if e["start"] else "time not yet confirmed") for e in ex[:5]) or None
    if re.search(r"venue|where", t):
        u = upcoming(c, p, 1); return (f"Next session “{u[0]['title']}” venue: {u[0]['venue'] or 'not yet recorded'}.") if u else None
    if re.search(r"session|schedule|next|today|class|timetable", t):
        u = upcoming(c, p); return "\n".join(f"{e['title']} – {ev_start(e):%a %d %b} {e['start']}–{e['end']}" + (f" ({e['venue']})" if e["venue"] else "") for e in u) or None
    return None
def handle_wa(c, payload):
    for en in payload.get("entry", []):
        for ch in en.get("changes", []):
            v = ch.get("value", {})
            for s in v.get("statuses", []):
                c.execute("update messages set status=?,error=? where wa_id=?", (s.get("status"), json.dumps(s.get("errors")) if s.get("errors") else None, s.get("id")))
            for m in v.get("messages", []):
                phone = "+" + m["from"]; p = person_by_phone(c, phone); t = m.get("type"); body, bid = "", None
                if t == "text": body = m["text"]["body"]
                elif t == "interactive":
                    i = m["interactive"]
                    if i.get("type") == "call_permission_reply":
                        r = i["call_permission_reply"]; exp = r.get("expiration_timestamp")
                        if p: set_consent(c, p["id"], "whatsapp_calls", "granted" if r.get("response") == "accept" else "withdrawn", "meta-call-permission",
                              None if r.get("is_permanent") or not exp else iso(dt.datetime.fromtimestamp(int(exp), TZ)))
                        body = f"[call permission {r.get('response')}]"
                    else: bid = (i.get("button_reply") or {}).get("id"); body = (i.get("button_reply") or {}).get("title", "")
                else: body = f"[{t}] media id {(m.get(t) or {}).get('id', '')}"
                before = c.execute("select count(*) from messages").fetchone()[0]
                log_msg(c, p, "in", m["id"], body, "received", phone=phone, mtype=t or "text", unread=1)
                if c.execute("select count(*) from messages").fetchone()[0] == before or not p: continue   # duplicate webhook delivery, or unknown sender
                rep = autoreply(c, p, body, bid) if t in ("text", "interactive") and "[call permission" not in body else None
                if rep:
                    c.execute("update messages set unread=0 where wa_id=?", (m["id"],)); deliver(c, p, rep, "reply")

# ---------- announcements ----------
def audience(c, f):
    out = []
    for p in rows(c, "select * from people where deleted=0"):
        if f.get("person_ids") and p["id"] not in f["person_ids"]: continue
        if f.get("role") and p["role"] != f["role"]: continue
        if f.get("module_id") and p["module_id"] != int(f["module_id"]): continue
        if f.get("cohort") and p["cohort"] != f["cohort"]: continue
        if has_consent(c, p["id"], "whatsapp_messages"): out.append(p)
    return out
def announce(c, actor, role, text, f, confirm, emergency):
    aud, cf = audience(c, f), cfg(c)
    if not text.strip(): raise ValueError("Message text required")
    if emergency and role not in ("admin", "dean"): raise PermissionError("Emergency override is limited to the administrator and Executive Dean.")
    if not confirm: return {"count": len(aud), "needs_confirm": True, "large": len(aud) > cf["max_bulk"]}
    if len(aud) > cf["max_bulk"] and role != "admin": raise PermissionError(f"Announcements to more than {cf['max_bulk']} recipients need administrator approval.")
    for p in aud: queue(c, p["id"], text, "announce", None, int(bool(emergency)))
    c.execute("insert into announcements(ts,actor,text,filt,count,emergency) values(?,?,?,?,?,?)", (iso(now()), actor, text, json.dumps(f), len(aud), int(bool(emergency))))
    audit(c, actor, "announce", f"{len(aud)} recipients"); return {"count": len(aud), "queued": True}

# ---------- class-rep reports & escalation ----------
def _notify(c, role, text):
    for p in rows(c, "select * from people where role=? and deleted=0", role):
        if has_consent(c, p["id"], "whatsapp_messages"): queue(c, p["id"], text)
def new_report(c, pid, module_id, kind, body):
    ref = f"MDR-{now().year}-{c.execute('select count(*) from reports').fetchone()[0] + 1:03d}"
    c.execute("insert into reports(ref,module_id,kind,body,person_id,status,created,updated) values(?,?,?,?,?,'pending',?,?)", (ref, module_id, kind, body, pid, iso(now()), iso(now())))
    m = one(c, "select code from modules where id=?", module_id) if module_id else None
    cr = one(c, "select * from people where id=?", pid)
    if cr and has_consent(c, pid, "whatsapp_messages"): queue(c, pid, f"Your report concerning {m['code'] if m else 'the programme'} has been received.\nReference: {ref}\nStatus: Pending administrative review.\nYou will be notified when the report is reviewed.")
    _notify(c, "coordinator", f"New class representative report {ref} ({kind}) for {m['code'] if m else 'the programme'}. Please review it in the Communications dashboard.")
    return ref
def set_report(c, rid, status, note, actor):
    if status not in ("verified", "rejected", "clarification", "corrected", "pending"): raise ValueError("Invalid status")
    r = one(c, "select * from reports where id=?", rid)
    c.execute("update reports set status=?,note=?,updated=? where id=?", (status, note, iso(now()), rid)); audit(c, actor, "report_" + status, r["ref"])
    if r["person_id"] and has_consent(c, r["person_id"], "whatsapp_messages"):
        queue(c, r["person_id"], f"Update on report {r['ref']}: {status.upper()}." + (f"\nNote: {note}" if note else ""))
def escalate(c):
    n = now(); cf = cfg(c)
    for r in rows(c, "select * from reports where status in ('pending','clarification')"):
        age = (n - dt.datetime.fromisoformat(r["created"])).total_seconds() / 3600
        if r["level"] == 0 and age >= cf["esc_hod_h"]: lvl, role = 1, "hod"
        elif r["level"] == 1 and age >= cf["esc_dean_h"]: lvl, role = 2, "dean"
        else: continue
        c.execute("update reports set level=? where id=?", (lvl, r["id"]))      # level guard = one escalation per tier
        _notify(c, role, f"Escalation: report {r['ref']} ({r['kind']}) is still unresolved after {int(age)} hours.")

# ---------- connection test / stats ----------
def test_connection(c):
    s, cf, out = load_secrets(), cfg(c), {}
    if not (s.get("wa_token") and s.get("wa_phone_id")): out["whatsapp"] = "Configuration incomplete"
    else:
        try:
            st, j = http(f"https://graph.facebook.com/{cf['graph']}/{s['wa_phone_id']}?fields=display_phone_number,verified_name,quality_rating", headers={"Authorization": "Bearer " + s["wa_token"]})
            out["whatsapp"] = f"Connected – {j.get('display_phone_number')} ({j.get('verified_name')})" if st == 200 else "Authentication expired / invalid token" if st in (401, 190) else f"API error {st}: {(j.get('error') or {}).get('message', '')}"
        except Exception as ex: out["whatsapp"] = f"Disconnected – {ex}"
    last = one(c, "select ts from messages where direction='in' order by id desc limit 1")
    out["webhook"] = f"Last inbound message {last['ts']}" if last else "No inbound webhook events received yet (verify the callback in Meta)"
    out["whatsapp_calling"] = "Not verified – business-initiated WhatsApp calls need a WebRTC media bridge (not included) and Meta calling eligibility"
    if not (s.get("tw_sid") and s.get("tw_token") and s.get("tw_from")): out["phone"] = "Configuration incomplete"
    else:
        try:
            st, j = http(f"https://api.twilio.com/2010-04-01/Accounts/{s['tw_sid']}.json", auth=(s["tw_sid"], s["tw_token"]))
            out["phone"] = "Connected – telephone calling available" if st == 200 else f"Twilio error {st}"
        except Exception as ex: out["phone"] = f"Disconnected – {ex}"
    c.execute("insert into csettings values('last_test',?) on conflict(k) do update set v=excluded.v", (json.dumps({"ts": iso(now()), **out}),)); return out
def stats(c):
    d = iso(now())[:10]; q = lambda s, *a: c.execute(s, a).fetchone()[0]
    return {"people": q("select count(*) from people where deleted=0"),
            "opt_msg": sum(has_consent(c, p["id"], "whatsapp_messages") for p in rows(c, "select id from people where deleted=0")),
            "opt_call": sum(has_consent(c, p["id"], "phone_calls") for p in rows(c, "select id from people where deleted=0")),
            "pending": q("select count(*) from reminders where status='pending'"), "failed_msgs": q("select count(*) from reminders where status='failed' and kind!='call'"),
            "failed_calls": q("select count(*) from calls where status in ('failed','unanswered','rejected')"),
            "sent_today": q("select count(*) from messages where direction='out' and ts like ?", d + "%"), "delivered": q("select count(*) from messages where direction='out' and status in ('delivered','read') and ts like ?", d + "%"),
            "failed_today": q("select count(*) from messages where direction='out' and status='failed' and ts like ?", d + "%"), "incoming": q("select count(*) from messages where direction='in' and ts like ?", d + "%"),
            "calls": q("select count(*) from calls where ts like ?", d + "%"), "answered": q("select count(*) from calls where status='answered' and ts like ?", d + "%"),
            "unanswered": q("select count(*) from calls where status='unanswered' and ts like ?", d + "%"), "unread": q("select count(*) from messages where direction='in' and unread=1"),
            "reports_open": q("select count(*) from reports where status in ('pending','clarification')")}
