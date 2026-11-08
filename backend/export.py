"""PDF and DOCX exports for one week (full text wrapped, never truncated)."""
import io, os, datetime as dt
import db

def week_days(w):
    out = []
    with db.conn() as c:
        for i in range(7):
            d = db.START + dt.timedelta(days=7 * w + i)
            rows = c.execute("""select e.*, m.code mcode, m.name mname, m.color color, f.name fname, f.designation fdes, f.avatar favatar
                from events e left join modules m on m.id=e.module_id left join facilitators f on f.id=e.facilitator_id
                where e.deleted=0 and e.date=? order by e.start is null, e.start""", (d.isoformat(),)).fetchall()
            out.append((d, [dict(r) for r in rows]))
    return out

def week_title(w):
    a = db.START + dt.timedelta(days=7 * w); b = a + dt.timedelta(days=6)
    with db.conn() as c:
        r = c.execute("select v from settings where k=?", (f"wk{w}",)).fetchone()
        t = c.execute("select v from settings where k='title'").fetchone()
    name = r[0] if r else f"Week {11 + w}"
    M = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    rng = (f"{a.day}–{b.day} {M[b.month-1]} {b.year}" if a.month == b.month else f"{a.day} {M[a.month-1]}–{b.day} {M[b.month-1]} {b.year}")
    return (t[0] if t else "PhD in Maternal and Neonatal Health"), f"{name}: {rng}"

def _time(e):
    return f"{e['start']}–{e['end']}" if e["start"] else "Time not confirmed"

def _avatar(e):
    p = os.path.join(db.UPLOADS, e["favatar"]) if e.get("favatar") else None
    return p if p and os.path.exists(p) else None

def pdf(w):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
    buf = io.BytesIO(); st = getSampleStyleSheet(); sm = st["BodyText"]; sm.fontSize = 8; sm.leading = 10
    prog, wk = week_title(w)
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    el = [Paragraph(f"<font color='#b8892b'>{prog}</font>", st["Title"]), Paragraph(wk, st["Heading2"])]
    for d, evs in week_days(w):
        el.append(Paragraph(f"<b>{d:%A %d %B %Y}</b>", st["Heading4"]))
        if not evs:
            el += [Paragraph("No sessions scheduled.", sm), Spacer(1, 4)]; continue
        data = [["Time", "Activity", "Module", "Facilitator", "Venue / Details"]]
        for e in evs:
            fa = _avatar(e); fc = []
            if fa:
                try: fc.append(Image(fa, 18, 18))
                except Exception: pass
            fc.append(Paragraph(f"{e['fname'] or '—'}<br/>{e['fdes'] or ''}", sm))
            data.append([Paragraph(_time(e), sm), Paragraph(f"<b>{e['title']}</b>", sm),
                         Paragraph(f"{e['mcode'] or '—'} {e['mname'] or ''}", sm), fc,
                         Paragraph(f"{e['venue'] or ''}<br/>{e['description'] or ''}", sm)])
        t = Table(data, colWidths=[80, 190, 170, 150, 170], repeatRows=1)
        sty = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14213d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#c9b27a")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        for i, e in enumerate(evs, 1):
            sty.append(("LINEBEFORE", (0, i), (0, i), 4, colors.HexColor(e["color"] or "#8a7a55")))
        t.setStyle(TableStyle(sty)); el += [t, Spacer(1, 6)]
    doc.build(el); return buf.getvalue()

def docx(w):
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.section import WD_ORIENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    d = Document(); s = d.sections[0]; s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = s.page_height, s.page_width
    prog, wk = week_title(w)
    d.add_heading(prog, 0); d.add_heading(wk, 2)
    for day, evs in week_days(w):
        d.add_heading(f"{day:%A %d %B %Y}", 3)
        if not evs:
            d.add_paragraph("No sessions scheduled."); continue
        t = d.add_table(rows=1, cols=5); t.style = "Table Grid"
        for i, h in enumerate(["Time", "Activity", "Module", "Facilitator", "Venue / Details"]):
            t.rows[0].cells[i].text = h
        for e in evs:
            r = t.add_row().cells
            r[0].text = _time(e); r[1].text = e["title"]; r[2].text = f"{e['mcode'] or '—'} {e['mname'] or ''}"
            p = r[3].paragraphs[0]; fa = _avatar(e)
            if fa:
                try: p.add_run().add_picture(fa, width=Cm(0.8))
                except Exception: pass
            p.add_run(f" {e['fname'] or '—'}" + (f", {e['fdes']}" if e["fdes"] else ""))
            r[4].text = " ".join(x for x in (e["venue"], e["description"]) if x)
            sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), (e["color"] or "#8a7a55")[1:])
            r[2]._tc.get_or_add_tcPr().append(sh)
            for run in r[2].paragraphs[0].runs: run.font.color.rgb = RGBColor(255, 255, 255)
    b = io.BytesIO(); d.save(b); return b.getvalue()
