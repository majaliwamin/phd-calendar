# PhD Maternal and Neonatal Health – Academic Calendar (9 Nov – 14 Dec 2026)

Offline-first: FastAPI + SQLite backend, vanilla HTML/CSS/JS web UI (no CDN, no internet needed), Flutter shell.

## Run
```
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000        # or run.bat / run.sh
```
Open http://127.0.0.1:8000. Data lives in `backend/data/` (SQLite + uploaded photos) and survives restarts.
Flutter shell: `cd flutter_app && flutter create . && flutter pub get && flutter run` (set `serverUrl` in `lib/main.dart`).

## Layout
- `backend/db.py` schema, seed, audit log, undo/redo · `main.py` REST API · `export.py` PDF/DOCX
- `web/` interface (`index.html`, `style.css`, `app.js`) · `flutter_app/` shell

## Data policy
Seeded only: the four modules (codes/names supplied), the RMDA-8101 exam on Fri 13 Nov (no time), and the recurring Tue 13:00–14:00 / Fri 10:00–12:00 slots titled "Recurring Activity – Edit Details". No facilitators, venues, teaching allocations or other exam dates were invented; the source timetable's other exam dates were not in the brief, so add them via the editor.
The Fri 13 Nov exam is flagged as a possible conflict with the Friday 10:00–12:00 activity until a time is entered.
Week labels follow your brief (Week 11 = 9–15 Nov … Week 16 = 14 Dec onward), not ISO numbering.

## Notes
Editor name is required before the first change (stored locally, recorded in Activity History). Undo/redo reverts one field change at a time.

# WhatsApp & Communications (setup)

Start the backend and open **WhatsApp & Communications → Access**. First run writes the admin token to `backend/data/ADMIN_TOKEN.txt`.
The background worker (inside `uvicorn`) runs every 30 s and keeps sending reminders with no browser open – **but only while `uvicorn` is running**. For real use, run it as a Windows service/scheduled task on an always-on machine.
Credentials are saved server-side in `backend/data/secrets.json` (never returned by the API; keep this folder private and out of backups you share).

## What you must provide (cannot be built into the code)
1. **Meta WhatsApp Cloud API**: a Meta Business account, a verified WhatsApp Business phone number, the Phone Number ID, WABA ID and a *permanent* system-user access token, and the app secret. Enter them under Integration.
2. **Public HTTPS URL** for webhooks (a hosted server, or a tunnel such as Cloudflare Tunnel/ngrok while testing). Put it in "Public URL", then in Meta set the callback to `<URL>/webhooks/whatsapp`, use your verify token, and subscribe to `messages`.
3. **Approved message templates** (needed for any message sent outside the 24-hour reply window – i.e. almost all reminders). Create in Meta Business Manager, language `en`:
   - `academic_reminder` (Utility), body with 7 variables:
     `Good day {{1}}. Academic reminder – Module {{2}}: {{3}} on {{4}}, {{5}}. Facilitator: {{6}}. Venue: {{7}}. Reply ACK to acknowledge or STOP to opt out.`
   - `academic_notice` (Utility), body: `Academic update: {{1}}`
4. **Telephone fallback (Twilio)**: Account SID, auth token and a Twilio voice number. Check that Twilio supports outbound calls to Malawi (+265) on your account/credit. Calls use text-to-speech in English (`en-GB`). Chichewa speech is **not** provided (no Twilio TTS voice for it) – the Chichewa preference is stored for messages only.

## Honest status of each channel
- **WhatsApp text/template messages, inbound webhook, auto-replies, ACK, STOP, delivery statuses, call-permission request/reply:** implemented per Meta's documented Cloud API; **not exercised against live Meta here** (no credentials/network). Use "Run connection test" and send yourself a test.
- **Telephone calls with spoken announcement (Twilio):** implemented (TwiML `<Say>`, status callbacks, retries); **not exercised against live Twilio here**.
- **WhatsApp voice calls:** **NOT implemented.** Meta's business-initiated calling needs a WebRTC media connection (SDP offer/answer), eligibility (high messaging tier) and regional availability, and cannot play an automated announcement through a simple REST call. The system records WhatsApp call permission when users accept Meta's request, but placing the call is not done; the reminder escalation uses the telephone fallback instead.
- Not built: sending/downloading media attachments (inbound images/documents/audio are logged as `[type] media id …`), per-user quiet hours (policy is global), Executive-Dean analytics beyond the overview counts, wiring to a separate "Class Representative system" (none existed – a minimal report workflow is included).

## Security notes
All `/api/comms/*` routes check the staff token and role on the server; HOD/Dean cannot read private conversations. **The existing calendar API (`/api/events` etc.) still has no login** – do not expose this server to the internet until that is secured.
Tests: `cd backend && python test_comms.py` (offline, fake provider).
