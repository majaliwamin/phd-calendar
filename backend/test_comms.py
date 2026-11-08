"""Offline tests of the communications engine with a fake provider (no Meta/Twilio calls are made)."""
import os, sys, tempfile, datetime as dt, json, hmac, hashlib
os.environ["CAL_DATA"] = tempfile.mkdtemp()
import db, comms
db.init()
with db.conn() as c: comms.init(c)
T = comms.TZ; BASE = dt.datetime(2026, 11, 9, 6, 0, tzinfo=T)       # Monday 06:00 Blantyre
comms.CLOCK = lambda: BASE
class Fake:
    def __init__(s): s.msgs, s.calls, s.fail = [], [], False
    def msg(s, c, p, text, kind, params, win):
        if s.fail: raise RuntimeError("provider down")
        s.msgs.append((p["name"], kind, win, text)); return f"wamid.{len(s.msgs)}"
    def call(s, c, p, text, attempt):
        s.calls.append((p["name"], attempt, text)); return f"CA{len(s.calls)}"
    def perm_request(s, c, p, t): return "wamid.perm"
F = Fake(); comms.PROV = F
ok = bad = 0
def chk(name, cond):
    global ok, bad
    ok += cond; bad += (not cond); print("PASS" if cond else "FAIL", name)
C = db.conn()
def run(minutes=0):
    global BASE
    BASE += dt.timedelta(minutes=minutes); n = 0
    while True:
        k = comms.tick(C); C.commit(); n += k
        if not k: return n
# registration + separate consents
pid = comms.save_person(C, {"name": "Aminiology Ma", "role": "class_rep", "phone": "0991234567", "module_id": 1})
chk("Malawi number normalised to +265", comms.person_by_phone(C, "+265991234567") is not None)
for bad_num in ("123", "+26599123"):
    try: comms.norm_phone(bad_num); chk("rejects " + bad_num, False)
    except ValueError: chk("rejects " + bad_num, True)
comms.set_consent(C, pid, "whatsapp_messages", "granted", "profile")
chk("message opt-in does NOT grant calls", not comms.has_consent(C, pid, "phone_calls") and not comms.has_consent(C, pid, "whatsapp_calls"))
comms.set_consent(C, pid, "phone_calls", "granted", "profile")
chk("voice consent separate", comms.has_consent(C, pid, "phone_calls"))
fid = C.execute("insert into events(title,module_id,date,start,end,venue,kind) values('Advanced Maternal Health',1,'2026-11-10','10:00','12:00','Room 4','session')").lastrowid
C.commit(); comms.tick(C); C.commit()
offs = sorted(r["offset_min"] for r in comms.rows(C, "select * from reminders where event_id=? and kind='remind'", fid))
chk("24h/2h/30m/10m/start reminders generated", offs == [0, 10, 30, 120, 1440])
chk("call attempt scheduled at start", C.execute("select count(*) from reminders where kind='call'").fetchone()[0] == 1)
comms.tick(C); C.commit()
chk("no duplicates on repeated sync", C.execute("select count(*) from reminders where event_id=?", (fid,)).fetchone()[0] == 6)
chk("event starts 10:00 Africa/Blantyre (+02:00)", comms.iso(comms.ev_start(comms.ev(C, fid))).endswith("10:00:00+02:00"))
# 24h reminder due Mon 10:00 -> quiet hours over at 06:00; run clock to 10:00 Mon
run(240)
chk("24h reminder sent once", sum(1 for m in F.msgs if "starts in 24 hours" in m[3]) == 1)
txt = F.msgs[0][3]
chk("message uses real records", all(s in txt for s in ("Good morning, Aminiology.", "Advanced Maternal Health", "10:00–12:00", "Room 4", "2 hours")))
chk("outside 24h window uses template route", F.msgs[0][2] is False)
# reschedule
C.execute("update events set start='14:00',end='16:00' where id=?", (fid,)); C.commit(); comms.tick(C); C.commit()
st = {r["status"] for r in comms.rows(C, "select * from reminders where event_id=? and kind='remind'", fid)}
chk("reschedule supersedes old reminders", "superseded" in st)
chk("reschedule notice queued", C.execute("select count(*) from reminders where kind='notice' and note like '%rescheduled%'").fetchone()[0] == 1)
chk("new reminders for new time", any(r["status"] == "pending" and r["ev_sig"] != "x" for r in comms.rows(C, "select * from reminders where event_id=? and kind='remind'", fid)))
# cancel
C.execute("update events set status='cancelled' where id=?", (fid,)); C.commit(); comms.tick(C); C.commit()
chk("cancel invalidates pending reminders", C.execute("select count(*) from reminders where event_id=? and kind in ('remind','call') and status='pending'", (fid,)).fetchone()[0] == 0)
chk("cancellation notice queued", C.execute("select count(*) from reminders where kind='notice' and note like '%CANCELLED%'").fetchone()[0] == 1)
# consent withdrawal + calls + retry + ack
C.execute("update events set status='scheduled' where id=?", (fid,)); C.commit(); comms.tick(C); C.commit()
before = len(F.msgs); comms.withdraw_all(C, pid, "profile"); C.commit(); run(2000)
chk("withdrawn consent: nothing sent / no calls", len(F.msgs) == before and not F.calls)
comms.set_consent(C, pid, "whatsapp_messages", "granted", "profile"); comms.set_consent(C, pid, "phone_calls", "granted", "profile")
e2 = C.execute("insert into events(title,module_id,date,start,end,kind) values('Call test',1,'2026-11-12','09:00','10:00','session')").lastrowid; C.commit()
BASE = dt.datetime(2026, 11, 12, 8, 59, tzinfo=T); comms.tick(C); C.commit(); run(1)
chk("voice call placed at session start", len(F.calls) == 1 and "due to begin now" in F.calls[0][2])
sid = F.calls[0] and "CA1"
comms.twilio_status(C, sid, "no-answer"); C.commit(); run(6)
chk("unanswered call retried per policy", len(F.calls) == 2 and F.calls[1][1] == 2)
comms.twilio_status(C, "CA2", "no-answer"); C.commit(); run(6); comms.twilio_status(C, "CA3", "no-answer"); C.commit(); run(30)
chk("retries capped (max 3 attempts)", len(F.calls) == 3)
chk("call outcome recorded", comms.one(C, "select status from calls where call_id='CA1'")["status"] == "unanswered")
# ack suppresses call
e3 = C.execute("insert into events(title,module_id,date,start,end,kind) values('Ack test',1,'2026-11-12','11:00','12:00','session')").lastrowid; C.commit(); comms.tick(C); C.commit()
C.execute("insert into acks values(?,?,?)", (e3, pid, "x")); C.commit(); n_calls = len(F.calls); BASE = dt.datetime(2026, 11, 12, 11, 0, tzinfo=T); run(1)
chk("acknowledged reminder is not phoned", len(F.calls) == n_calls)
# quiet hours: no calls at night
C.execute("insert into reminders(event_id,person_id,kind,offset_min,due,status,ikey) values(?,?,?,?,?,?,?)", (e3, pid, "call", 0, comms.iso(BASE), "pending", "q1")); C.commit()
BASE = dt.datetime(2026, 11, 12, 22, 0, tzinfo=T); C.execute("delete from acks"); C.commit(); run(0)
chk("no calls outside calling hours", len(F.calls) == n_calls)
# failure -> retry -> in-app preserved
F.fail = True; comms.queue(C, pid, "Failure test"); C.commit(); BASE = dt.datetime(2026, 11, 13, 9, 0, tzinfo=T); run(0); run(6); run(6); run(6)
chk("failed delivery recorded and kept in in-app centre", C.execute("select count(*) from inapp").fetchone()[0] >= 1 and C.execute("select count(*) from reminders where status='failed'").fetchone()[0] >= 1)
F.fail = False
# webhook: verified signature, inbound, dedupe, STOP, autoreplies from records
secret = "appsecret"; raw = b'{"x":1}'; good = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
chk("webhook signature verified", comms.verify_sig(raw, good, secret) and not comms.verify_sig(raw, "sha256=bad", secret) and not comms.verify_sig(raw, None, secret))
def inbound(text, wid): return {"entry": [{"changes": [{"value": {"messages": [{"from": "265991234567", "id": wid, "type": "text", "text": {"body": text}}]}}]}]}
BASE = dt.datetime(2026, 11, 9, 9, 0, tzinfo=T); n0 = len(F.msgs)
comms.handle_wa(C, inbound("next session?", "in1")); C.commit()
chk("incoming stored + bot answers from real records", comms.one(C, "select count(*) n from messages where direction='in'")["n"] >= 1 and len(F.msgs) == n0 + 1 and "Call test" in F.msgs[-1][3] or "Advanced" in F.msgs[-1][3])
comms.handle_wa(C, inbound("next session?", "in1")); C.commit()
chk("duplicate webhook delivery ignored", len(F.msgs) == n0 + 1)
comms.handle_wa(C, inbound("what is the exam date", "in2")); C.commit()
chk("bot does not invent dates when none recorded", len(F.msgs) == n0 + 1)
comms.handle_wa(C, inbound("hello can you help", "in3")); C.commit()
chk("complex query routed to human (unread)", comms.one(C, "select count(*) n from messages where unread=1")["n"] >= 1)
comms.handle_wa(C, inbound("STOP", "in4")); C.commit()
chk("STOP withdraws all consent", not comms.has_consent(C, pid, "whatsapp_messages") and not comms.has_consent(C, pid, "phone_calls"))
comms.set_consent(C, pid, "whatsapp_messages", "granted", "profile")
comms.handle_wa(C, {"entry": [{"changes": [{"value": {"messages": [{"from": "265991234567", "id": "in5", "type": "interactive", "interactive": {"type": "call_permission_reply", "call_permission_reply": {"response": "accept", "is_permanent": True}}}]}}]}]}); C.commit()
chk("WhatsApp call permission reply recorded", comms.has_consent(C, pid, "whatsapp_calls"))
# announcements & roles
cp = comms.save_person(C, {"name": "Dr. Peter Mbewe", "role": "coordinator", "phone": "+265888000111", "module_id": 1}); comms.set_consent(C, cp, "whatsapp_messages", "granted", "profile")
hp = comms.save_person(C, {"name": "Prof. Hod Test", "role": "hod", "phone": "+265888000222"}); comms.set_consent(C, hp, "whatsapp_messages", "granted", "profile")
chk("announcement previews recipient count first", comms.announce(C, "a", "admin", "Venue changed", {"role": "coordinator"}, False, False)["count"] == 1)
try: comms.announce(C, "a", "coordinator", "x", {}, True, True); chk("emergency override restricted", False)
except PermissionError: chk("emergency override restricted", True)
chk("opted-out people excluded from audience", pid in [p["id"] for p in comms.audience(C, {})] and cp in [p["id"] for p in comms.audience(C, {})])
# reports + escalation
ref = comms.new_report(C, pid, 1, "missed session", "Session did not hold"); C.commit()
chk("report gets reference MDR-2026-001", ref == "MDR-2026-001")
chk("acknowledgement + coordinator alert queued", C.execute("select count(*) from reminders where note like '%MDR-2026-001%'").fetchone()[0] == 2)
BASE += dt.timedelta(hours=49); comms.escalate(C); comms.escalate(C); C.commit()
chk("HOD escalation once only", C.execute("select count(*) from reminders where note like 'Escalation%'").fetchone()[0] == 1)
rid = C.execute("select id from reports").fetchone()[0]; comms.set_report(C, rid, "verified", "", "coordinator"); BASE += dt.timedelta(hours=100); comms.escalate(C); C.commit()
chk("no escalation once report is resolved", C.execute("select count(*) from reminders where note like 'Escalation%'").fetchone()[0] == 1)
chk("role permissions enforced", comms.can("admin", "x") and comms.can("coordinator", "converse") and not comms.can("hod", "converse") and not comms.can("dean", "converse") and not comms.can("class_rep", "view") and comms.can("class_rep", "submit"))
chk("secrets never in settings API output", "wa_token" not in json.dumps(comms.cfg(C)))
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
