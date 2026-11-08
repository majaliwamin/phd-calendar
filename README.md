# PhD Maternal and Neonatal Health – Academic Calendar

Offline-first academic calendar for the PhD programme. Backend: FastAPI + SQLite. Web interface: vanilla HTML/CSS/JavaScript. Flutter mobile/desktop wrapper: Flutter + `flutter_inappwebview`.

## 1. Run the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Data is stored in `backend/data/` and persists across restarts. Keep this folder private. The first start creates `backend/data/ADMIN_TOKEN.txt`. Do not publish, email, or commit this token. The administrator can create staff tokens under **WhatsApp & Communications → Access**.

### Local development sign-in bypass

Outside production the backend starts a local development session automatically: the browser opens straight into the dashboard and API requests are authorised as an admin-equivalent **Aminiology Ma** staff account. No token, staff credentials, or manual sign-in is needed locally. This only bypasses *authentication* — role checks, audit history and stored records behave exactly as before.

The mode is decided by the environment on every start:

- `CAL_ENV` unset, or `development` / `test` → bypass **on** (the bundled `run.bat` / `run.sh` set `CAL_ENV=development`).
- `CAL_ENV=production` (or `prod`, `staging`, `stage`) → bypass **off**; a valid Staff Bearer token is required exactly as in earlier releases. `APP_ENV`, `ENVIRONMENT` and `FASTAPI_ENV` are accepted as aliases.
- `CAL_DEV_AUTH=0` → force the bypass off even in development. Production always wins over `CAL_DEV_AUTH`.

The backend prints `[auth] Development login bypass ON` at startup when active, and the web header shows **Dev mode – no sign-in**. The Flutter shell makes the same tokenless probe, so it also skips its native sign-in screen while the backend is in development mode. Deployments must set `CAL_ENV=production` (and use HTTPS, firewalling, and an operational backup policy) before exposing the service.

For LAN access, bind to `0.0.0.0` only on a trusted network and use the host computer's LAN address from other devices. For public deployment, put the service behind HTTPS and a reverse proxy, restrict network access, and protect the data directory.

## 2. Staff access and permissions

The calendar and communications modules now use the same server-verified Bearer staff token. The browser-supplied editor name is no longer treated as authentication. The server records the authenticated staff member's name in Activity History.

- `admin`: full access, staff management, integration settings, backup and restore.
- `coordinator`: calendar viewing/editing and normal coordinator communications permissions.
- `hod` / `dean`: calendar viewing and their existing reporting/announcement permissions; no calendar editing.
- `class_rep`: calendar viewing, personal academic portal, acknowledgements and class-representative report submission.
- `student`: read-only calendar access plus a linked personal academic portal for assigned activities, academic notices and in-app acknowledgements.

Tokens are stored in the browser tab's `sessionStorage`; signing out or closing the tab clears the browser token. Use HTTPS outside a trusted local machine/network. Do not expose the service directly to the public internet without TLS, firewalling, and an operational backup policy.

## 3. Academic data policy

Seeded only: the four module codes/names supplied, the RMDA-8101 examination on 13 November 2026 (no time), and the recurring Tuesday 13:00–14:00 / Friday 10:00–12:00 slots titled “Recurring Activity – Edit Details”. No facilitators, venues, teaching allocations or other examination dates are invented. Week labels follow the supplied calendar (Week 11 = 9–15 Nov … Week 16 = 14 Dec onward), not ISO week numbering.

## 4. WhatsApp reminders

Start the backend and open **WhatsApp & Communications → Access**. The background worker checks the reminder queue every 30 seconds while the backend is running. For production, run the backend as a supervised service on an always-on server.

Required external setup:

1. A Meta Business account and WhatsApp Business Cloud API phone number.
2. Phone Number ID, WABA ID, permanent system-user access token, webhook verify token and Meta app secret.
3. A public HTTPS callback URL configured in Meta as `<URL>/webhooks/whatsapp`, subscribed to `messages`.
4. Approved Utility templates in Meta for `academic_reminder` and `academic_notice` (language `en`). Template messages are required outside the WhatsApp 24-hour service window.

Meta credentials are saved server-side in `backend/data/secrets.json`, never returned to the browser. They are not included in JSON backups.

## 5. Asterisk telephone fallback (Twilio removed)

Telephone fallback now uses **Asterisk AMI** and local `eSpeak NG`/`eSpeak` speech generation. No Twilio account, Twilio credentials, or paid telephony API is used. Asterisk and eSpeak are external system services and must be installed/configured by the operator; they are not Python package dependencies.

### Asterisk requirements

- Asterisk with a working outbound SIP/PJSIP trunk capable of calling the target numbers (including Malawi `+265`).
- AMI enabled on a trusted/private interface, with a dedicated AMI user allowed to issue `Originate` and receive call events. Do not expose AMI port 5038 to the public internet.
- `espeak-ng` (preferred) or `espeak` installed on the same host as the FastAPI backend.
- The backend process must be able to write WAV files to the configured Asterisk `sounds/custom` directory. If Asterisk is on a separate host, mount/share that directory securely or implement a separate audio transfer service before enabling calls.

### Example Asterisk dialplan

Add a dedicated context to your Asterisk dialplan (for example in `extensions_custom.conf`):

```ini
[mnh-announcement]
exten => s,1,Answer()
 same => n,Wait(1)
 same => n,Playback(${MNHSOUND})
 same => n,Hangup()
```

Reload the dialplan after validating it. Configure the outbound channel in the application to match your trunk, for example:

- Channel prefix: `PJSIP/`
- Channel suffix: `@mnh-trunk`
- Context: `mnh-announcement`

This produces a channel such as `PJSIP/265991234567@mnh-trunk`. Your actual endpoint/trunk name and channel syntax may differ; verify it with your Asterisk administrator before enabling automatic calls.

In **WhatsApp & Communications → Integration**, enter:

- AMI host (prefer `127.0.0.1` when Asterisk and FastAPI share a host)
- AMI username and secret
- Dialplan context, channel prefix/suffix, caller ID
- Absolute Asterisk `sounds/custom` directory path
- eSpeak voice (default `en-gb`) and speech speed

Save and use **Run connection test**. The test checks AMI reachability; it does not prove that the trunk can complete a call. The AMI event monitor records originate success/failure and feeds failed attempts into the retry queue. Calls are still subject to explicit telephone-call consent, calling hours, acknowledgement suppression, and configured retry limits. Never treat WhatsApp message consent as telephone-call consent.

The application generates a unique WAV prompt for each call and leaves it in the Asterisk sounds directory so Asterisk can play it. Set up an operational retention/cleanup policy for old `mnh_*.wav` files. The default English voice is not a Malawian/Chichewa voice; verify available eSpeak voices on your host before selecting another language.

## 6. Backup and restore

Administrators can export a JSON backup and restore it from **Editor → Share and backup**. Backups include calendar records, communications records, activity/audit history and facilitator avatar images. They deliberately exclude API credentials in `secrets.json` and the raw administrator token file. Staff token hashes are included, but raw tokens cannot be recovered from a backup; on a new installation, issue new staff tokens and distribute them securely. Keep backup files encrypted and access-controlled because they contain personal contact information, staff token hashes, and communication history. Keep a separate secure copy of integration credentials. Restore is admin-only and validates table/record shapes and avatar payloads before replacing records. A legacy calendar-only backup can still be restored without deleting communications records.

## 7. Flutter application

The student portal is available to student/class-representative tokens linked to a registered person record. It shows assigned module/facilitator events, in-app notices and event acknowledgements. Acknowledgement is not attendance.

The Flutter application now has a native sign-in screen, secure token storage, staff calendar view, student/class-representative agenda, in-app notices and student acknowledgements. Coordinators/admins can open the full web calendar/editor inside the app; the token is injected into that WebView session and is not placed in the URL. The native screens require a live backend connection; full offline editing/synchronization is not implemented.

```powershell
cd flutter_app
flutter create .   # one-time: generate Android/iOS/web platform folders
flutter pub get
flutter run --dart-define=SERVER_URL=http://127.0.0.1:8000
```

For a phone/tablet, replace `127.0.0.1` with the backend computer's reachable LAN address (Android emulator host loopback is commonly `10.0.2.2`). The backend must be reachable from that device. If testing over plain HTTP, configure Android cleartext traffic for development only; use HTTPS for production. Android/iOS release builds still need platform-specific network/security configuration and device testing.

## 8. Tests and honest integration status

Run the offline regression suites:

```powershell
cd backend
python test_comms.py
python test_calendar_security.py
python test_dev_auth.py
python test_asterisk.py
```

The communications suite uses a fake provider; the calendar security suite tests role enforcement; the dev-auth suite verifies the local bypass works without a token and that production/staging still reject anonymous requests and enforce roles; the Asterisk suite uses a fake AMI server and fake eSpeak process. None sends real WhatsApp messages or places a real telephone call. A successful Asterisk connection test confirms AMI reachability only; verify actual outbound calling, audio playback, call completion and Malawi trunk routing with a test number and explicit consent before enabling automatic calls. Flutter builds and live Meta/Asterisk integration tests must be run in the target deployment environment.

## 9. Known boundaries

- WhatsApp voice calling is not implemented; the fallback channel is ordinary telephone calling through Asterisk.
- Chichewa TTS is not guaranteed by eSpeak; the configured default is English.
- The Flutter app is a WebView shell, not a full native offline-first rewrite.
- Backups exclude provider secrets and must be stored securely.
- Run the application behind HTTPS and restrict AMI/database access for any non-local deployment.
