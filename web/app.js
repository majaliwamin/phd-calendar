const $ = (s) => document.querySelector(s);
const S = { w: 0, view: "weekly", edit: false, d: null };
const PX = 60, T0 = 480, T1 = 1080, SNAP = 15;
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&", "<": "<", ">": ">", '"': '"' })[c]);
const dayN = (i) => new Date(Date.UTC(2026, 10, 9 + i));
const iso = (d) => d.toISOString().slice(0, 10);
const F = (d, o) => d.toLocaleDateString("en-GB", { timeZone: "UTC", ...o });
const mins = (t) => (t ? +t.slice(0, 2) * 60 + +t.slice(3, 5) : null);
const hhmm = (m) => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function range(w) {
  const a = dayN(w * 7), b = dayN(w * 7 + 6), Y = b.getUTCFullYear(), A = a.getUTCMonth(), B = b.getUTCMonth();
  return A == B ? `${a.getUTCDate()}–${b.getUTCDate()} ${MON[B]} ${Y}` : `${a.getUTCDate()} ${MON[A]}–${b.getUTCDate()} ${MON[B]} ${Y}`;
}
const wkName = (w) => S.d.settings["wk" + w] || `Week ${11 + w}`;

/* ---------- Official weekday timetable intervals ---------- */
const TM = {
  morning: "Morning session",
  pre: "Pre-afternoon period",
  weekly: "Weekly academic session",
  afternoon: "Afternoon session",
  final: "Final afternoon session",
  lunch: "Lunch break",
};

const STD_DAY = [
  per("08:00", "10:00", TM.morning, "session"),
  per("10:00", "12:00", TM.morning, "session"),
  per("12:00", "13:00", TM.pre, "lunch"),
  per("13:00", "14:00", TM.weekly, "weekly"),
  per("14:00", "16:00", TM.afternoon, "session"),
  per("16:00", "17:30", TM.final, "session"),
];

const TUE_DAY = [
  per("08:00", "10:00", TM.morning, "session"),
  per("10:00", "12:00", TM.morning, "session"),
  per("12:00", "13:30", TM.lunch, "lunch"),
  per("13:30", "15:30", TM.afternoon, "session"),
  per("15:30", "17:30", TM.afternoon, "session"),
];

const WEEK_PERIODS = {
  0: STD_DAY,
  1: TUE_DAY,
  2: STD_DAY,
  3: STD_DAY,
  4: STD_DAY,
  5: [],
  6: [],
};

const dow = (ds) => (new Date(ds + "T00:00:00Z").getUTCDay() + 6) % 7;
const periodsFor = (ds) => WEEK_PERIODS[dow(ds)] || [];
const protectedFor = (ds) => periodsFor(ds).filter((p) => p.kind == "lunch" || p.kind == "weekly");

/* Helper: create period object */
function per(s, e, label, kind) { return { s: mins(s), e: mins(e), label, kind }; }

/* ==== Timetable rendering ==== */

const TODAY = () => iso(new Date());

function evHTML(ev) {
  const kind = ev.kind || "session";
  const cl = kind === "lunch" ? "k-lunch" : kind === "exam" ? "k-exam" : kind === "recurring" ? "k-recurring" : "";
  const bgC = kind === "morning" ? "#1a2a4a" : kind === "afternoon" ? "#b8892b" : kind === "lunch" ? "#ff3d3d" : kind === "weekly" ? "#26406b" : "#3a5a7c";
  const txtC = kind === "lunch" || kind === "exam" ? "#fff" : "#171b22";
  return `<div class="ev ${cl}" style="background:${bgC};color:${txtC}" data-id="${ev.id}"
    title="${esc(ev.title || "")} ${hhmm(ev.start)}–${hhmm(ev.end)}">
    <b>${esc(ev.title || "")}</b><small>${hhmm(ev.start)}–${hhmm(ev.end)}</small>
  </div>`;
}

function legendHTML() {
  return `<div class="legend">
    <span class="sw"></span>Morning session (2-hr)<br>
    <span style="background:#b8892b;color:#171b22"></span>Afternoon session<br>
    <span style="background:#ff3d3d;color:#fff"></span>Lunch break<br>
    <span style="background:#26406b;color:#e8e2d0"></span>Weekly session
  </div>`;
}

/* ==== Weekly timetable HTML ==== */
function weeklyHTML() {
  const evs = inWeek(S.w);
  let h = weekNotes(evs) + '<div class="calwrap"><div class="cal"><div class="corner"></div>';

  /* Day headers Mon-Fri */
  for (let i = 0; i < 5; i++) {
    const d = dayN(S.w * 7 + i);
    h += `<div class="hd">${DAYS[i]}<small>${F(d, { day: "numeric", month: "short" })}</small></div>`;
  }

  /* Empty cells for Sat/Sun */
  for (let i = 5; i < 7; i++) {
    h += `<div class="un"></div>`;
  }

  h += '<div class="un corner-un"></div>';

  /* Time interval rows */
  h += '<div class="tl">';
  const numRows = Math.ceil((T1 - T0) / 60);
  for (let i = 0; i < numRows; i++) {
    const t = T0 + i * 60;
    h += `<span style="top:${t * PX / 60}px">${hhmm(t)}</span>`;
  }
  h += "</div>";

  /* Day columns with periods and events */
  for (let i = 0; i < 7; i++) {
    const ds = iso(dayN(S.w * 7 + i));
    const bands = periodsFor(ds).map((p) => {
      const top = ((p.s - T0) * PX) / 60;
      const hgt = ((p.e - p.s) * PX) / 60;
      if (p.kind == "lunch") {
        return `<div class="pd lunch" style="top:${top}px;height:${hgt}px" title="${esc(p.label)} ${hhmm(p.s)}–${hhmm(p.e)}"><span>LUNCH<br>BREAK</span></div>`;
      }
      return `<div class="pd ${p.kind}" style="top:${top}px;height:${hgt}px"><em>${esc(p.label)}</em><small>${hhmm(p.s)}–${hhmm(p.e)}</small></div>`;
    }).join("");

    /* Events in this day column */
    const dayEvts = evs.filter((e) => e.date == ds && e.start).sort((a, b) => (a.start || "").localeCompare(b.start || ""));
    const lanes = dayEvts.map(evHTML).join("");

    h += `<div class="col ${i > 4 ? "we" : ""}" data-date="${ds}">
      <div class="pdl">${bands}</div>${lanes}</div>`;
  }

  return (
    h + "</div></div>" + legendHTML() + '<p class="hint">One row per hour. Click an empty slot to create.</p>'
  );
}

function weekNotes(evs) {
  const start = dayN(S.w * 7), end = dayN(S.w * 7 + 6);
  const Y = end.getUTCFullYear(), A = start.getUTCMonth(), B = end.getUTCMonth();
  const rangeTxt = A == B ? `${start.getUTCDate()}–${end.getUTCDate()} ${MON[B]} ${Y}` : `${start.getUTCDate()} ${MON[A]}–${end.getUTCDate()} ${MON[B]} ${Y}`;
  return `<div class="week-h">Block Three · 9 Nov – 20 Dec 2026</div>`;
}

function inWeek(w) {
  const start = "2026-11-09", end = dayN(w * 7 + 6);
  const after = new Date(end);
  after.setUTCDate(after.getUTCDate() + 1);
  return (S.d && S.d.events || [])
    .filter((e) => new Date(e.date) >= new Date(start) && new Date(e.date) < after);
}

/* ==== Chrome / UI ==== */
function chrome() {
  /* Set week navigation */
  const pw = document.querySelector("#pw");
  const nwBtn = document.querySelector("#nw");
  const todayBtn = document.querySelector("#today");
  if (pw) pw.onclick = () => { S.w = S.w - 1; render(); };
  if (nwBtn) nwBtn.onclick = () => { S.w = S.w + 1; render(); };
  if (todayBtn) todayBtn.onclick = () => { S.w = 0; render(); };

  /* Set subtitle */
  const sub = document.querySelector("#sub");
  if (sub) sub.textContent = `${wkName(S.w)} · ${range(S.w)}`;

  /* Set mode */
  const mode = document.querySelector("#mode");
  if (mode) mode.textContent = S.edit ? "Editor ON" : "";

  /* Edit mode: enable event editing */
  if (S.edit) {
    document.querySelectorAll(".ev").forEach((el) => {
      el.addEventListener("click", () => editEvent(el));
    });
    document.querySelectorAll(".col").forEach((col) => {
      col.addEventListener("click", (e) => { if (e.target.className === "col") createEventAt(col); });
    });
  }
}

/* ==== Create event at click position ==== */
function createEventAt(col) {
  if (!S.edit) return;
  const top = parseFloat(col.dataset.top || "0");
  const startH = Math.round((top / PX) * 60 + T0) / 60;
  const endH = startH + 2;
  const date = col.dataset.date;
  if (!date) return;
  const id = Date.now() + Math.random();
  const newEv = { id, title: "New activity", kind: "session", start: `${startH}:00`, end: `${endH}:00`, date };
  if (!S.d) S.d = { events: [] };
  S.d.events.push(newEv);
  saveData();
  render();
}

/* ==== Edit existing event ==== */
function editEvent(el) {
  if (!S.edit || !S.d) return;
  const ev = S.d.events.find((e) => e.id == el.dataset.id);
  if (!ev) return;
  const newTitle = prompt("Edit activity title:", ev.title);
  if (newTitle !== null) {
    ev.title = newTitle;
    saveData();
    render();
  }
}

/* ==== Save data ==== */
function saveData() {
  try { localStorage.setItem("timetable", JSON.stringify(S.d)); } catch (_) {}
}

/* ==== Render function ==== */
function render() {
  document.body.classList.remove("so");
  $(\"#view\").innerHTML = `<p class=\"loading\">Loading timetable…</p>`;
  $(\"#view\").innerHTML = weeklyHTML();
  chrome();
  scrollCalToToday();
}

/* ==== Scroll to today ==== */
function scrollCalToToday() {
  if (innerWidth > 900) return;
  const wrap = document.querySelector(\".calwrap\");
  if (!wrap) return;
  const cols = [...wrap.querySelectorAll(\".col\")];
  if (!cols.length) return;
  const target = cols.find((c) => c.dataset.date == TODAY()) || cols[0];
  if (!target) return;
  const wb = wrap.getBoundingClientRect();
  const tb = target.getBoundingClientRect();
  wrap.scrollLeft = Math.max(0, wrap.scrollLeft + tb.left - wb.left - 56);
}

/* ==== Initialization - simplified ==== */
S.d = { events: [], settings: { wk11: "Week 11", wk12: "Week 12", wk13: "Week 13", wk14: "Week 14", wk15: "Week 15", wk16: "Week 16" } };
render();