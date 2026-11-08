"""SQLite persistence + audit logging."""
import sqlite3, os, datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("CAL_DATA", os.path.join(BASE, "data"))
UPLOADS = os.path.join(DATA, "uploads")
DB = os.path.join(DATA, "calendar.db")
START = dt.date(2026, 11, 9)

FIELDS = {
    "events": {"title", "module_id", "facilitator_id", "venue", "description", "date", "start", "end", "kind", "status", "stype", "deleted"},
    "facilitators": {"name", "designation", "module_id", "contact", "avatar", "deleted"},
    "modules": {"code", "name", "color"},
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS modules(id INTEGER PRIMARY KEY, code TEXT, name TEXT, color TEXT);
CREATE TABLE IF NOT EXISTS facilitators(id INTEGER PRIMARY KEY, name TEXT, designation TEXT, module_id INTEGER, contact TEXT, avatar TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, title TEXT, module_id INTEGER, facilitator_id INTEGER, venue TEXT, description TEXT,
  date TEXT, start TEXT, end TEXT, kind TEXT DEFAULT 'session', series_id INTEGER, overridden INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, ts TEXT, user TEXT, entity TEXT, eid INTEGER, label TEXT, field TEXT, old TEXT, new TEXT, undone INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
"""

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    os.makedirs(UPLOADS, exist_ok=True)
    with conn() as c:
        c.executescript(SCHEMA)
        for col in ("status TEXT DEFAULT 'scheduled'", "stype TEXT"):  # migration: existing data is kept
            try:
                c.execute(f"alter table events add column {col}")
            except sqlite3.OperationalError:
                pass
        if c.execute("select count(*) from modules").fetchone()[0] == 0:
            seed(c)

def seed(c):
    """Only confirmed information: module codes/names, the 13 Nov exam, and the two recurring slots.
    No facilitators, venues or exam times are invented."""
    mods = [("MPN 8100", "Medical Imaging in Pregnancy and Neonates", "#1f6f8b"),
            ("ARMN 8100", "Antimicrobial Resistance in Maternal and Neonatal Health", "#9b3d3d"),
            ("PMN 8100", "Pregnancy and Neonatal Immunology", "#5b4b8a"),
            ("RMDA-8101", "(module name not confirmed - edit)", "#2e7d4f")]
    for m in mods:
        c.execute("insert into modules(code,name,color) values(?,?,?)", m)
    c.execute("insert into settings values('title','PhD in Maternal and Neonatal Health')")
    c.execute("insert into events(title,module_id,date,kind) values('RMDA-8101 End of Module Examination',4,'2026-11-13','exam')")
    for sid, wd, s, e in ((1, 1, "13:00", "14:00"), (2, 4, "10:00", "12:00")):
        for i in range(36):
            d = START + dt.timedelta(days=i)
            if d.weekday() == wd:
                c.execute("insert into events(title,date,start,end,kind,series_id) values('Recurring Activity – Edit Details',?,?,?,'recurring',?)",
                          (d.isoformat(), s, e, sid))

def _norm(v):
    return None if v in ("", None) else str(v)

def label(c, ent, eid):
    if ent == "settings":
        return "Settings"
    r = c.execute(f"select * from {ent} where id=?", (eid,)).fetchone()
    return (r["title"] if ent == "events" else r["name"] if ent == "facilitators" else r["code"]) if r else str(eid)

def update(c, user, ent, eid, changes):
    for k, v in changes.items():
        v = _norm(v)
        if ent == "settings":
            r = c.execute("select v from settings where k=?", (k,)).fetchone()
            old = r[0] if r else None
        elif k in FIELDS[ent]:
            old = c.execute(f"select {k} from {ent} where id=?", (eid,)).fetchone()[0]
        else:
            continue
        if _norm(old) == v:
            continue
        c.execute("update history set undone=2 where undone=1")  # new edit clears redo stack
        c.execute("insert into history(ts,user,entity,eid,label,field,old,new) values(?,?,?,?,?,?,?,?)",
                  (dt.datetime.now().isoformat(timespec="seconds"), user, ent, eid, label(c, ent, eid), k, _norm(old), v))
        setraw(c, ent, eid, k, v)

def setraw(c, ent, eid, k, v):
    if ent == "settings":
        c.execute("insert into settings values(?,?) on conflict(k) do update set v=excluded.v", (k, v))
    else:
        c.execute(f"update {ent} set {k}=? where id=?", (v, eid))

def undo(c):
    h = c.execute("select * from history where undone=0 order by id desc limit 1").fetchone()
    if h:
        setraw(c, h["entity"], h["eid"], h["field"], h["old"])
        c.execute("update history set undone=1 where id=?", (h["id"],))
    return bool(h)

def redo(c):
    h = c.execute("select * from history where undone=1 order by id asc limit 1").fetchone()
    if h:
        setraw(c, h["entity"], h["eid"], h["field"], h["new"])
        c.execute("update history set undone=0 where id=?", (h["id"],))
    return bool(h)
