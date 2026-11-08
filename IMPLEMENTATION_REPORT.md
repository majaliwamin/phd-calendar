# Implementation report – PhD MNH Academic Calendar

Implementation was applied to the supplied ZIP extract. The ZIP did not contain a Git repository, so no repository branch or existing working-tree changes could be inspected or preserved. The original extracted source was kept separately during this work.

## Phase 1 – Security and staff access

- Replaced the browser-controlled `X-Editor` identity with server-verified Bearer staff tokens from the existing staff table.
- Added calendar permissions: admin full access; coordinator edit; HOD/dean read/export; student/class representative read-only.
- Protected bootstrap, event/facilitator/module/settings edits, undo/redo, history restore, exports, ICS, backup and restore.
- Browser calendar sign-in uses the same staff token as Communications. Activity History records the authenticated staff account, not the local display name.
- Added server-side event validation for ISO dates, 24-hour times, title, time ordering and referenced module/facilitator records.

## Phase 2 – Calendar and data reliability

- Escaped ICS text values (backslash, commas, semicolons and line breaks).
- Added validation for backup table/record shapes and avatar payloads; restore runs calendar and communications record replacement in one SQLite transaction.
- Backups now include communications data, staff token hashes, consent, reminders, message/call history, reports and audit records, plus facilitator avatars. Provider secrets are deliberately excluded.
- Legacy calendar-only backups remain importable without deleting existing communications records.
- Added role-scoped calendar bootstrap for student/class-representative accounts.

## Phase 3 – Asterisk replacement

- Removed Twilio call creation and Twilio webhook integration.
- Retired Twilio credentials (`tw_sid`, `tw_token`, `tw_from`) are removed from the server secrets file during communications initialization.
- Added Asterisk AMI login/originate, reconnecting OriginateResponse event monitoring, failure retry handling, local eSpeak/eSpeak-NG prompt generation and 8 kHz mono PCM WAV conversion for Asterisk Playback.
- Added administrator settings for AMI host/port/user/secret, dialplan context, channel prefix/suffix, caller ID, sound directory and TTS voice/speed.
- Calls still require separately recorded telephone-call consent, respect calling hours and acknowledgement suppression, and use the configured retry policy.

## Phase 4 – Student experience

- Added a `student` staff-token role linked to a registered person record.
- Added a scoped personal agenda and academic notices endpoint.
- Added in-app event acknowledgement. It is explicitly described as acknowledgement of a notice, not attendance.
- Student and class-representative bootstrap data is limited to their linked module/facilitator assignments; export and editing permissions are not granted.

## Phase 5 – Flutter application

- Replaced the bare WebView-only Flutter home with a native sign-in, secure token storage, native staff calendar list, student/class-representative agenda, notices and acknowledgement actions.
- Kept the full web calendar/editor available inside an authenticated WebView for staff who need its complete editing features.
- Added configurable `SERVER_URL` via `--dart-define`.
- The Flutter app still requires a live backend connection; full offline-native editing and synchronization are not implemented.

## Changed files

1. `README.md`
2. `IMPLEMENTATION_REPORT.md`
3. `backend/comms.py`
4. `backend/comms_api.py`
5. `backend/main.py`
6. `backend/test_comms.py`
7. `backend/test_calendar_security.py`
8. `backend/test_asterisk.py`
9. `web/app.js`
10. `web/comms.js`
11. `flutter_app/lib/main.dart`
12. `flutter_app/pubspec.yaml`

## Verification performed

- Python compilation: passed (`python -m py_compile backend/*.py`).
- Communications regression suite: **41 passed, 0 failed** (`python backend/test_comms.py`).
- Calendar authorization tests: passed (`python backend/test_calendar_security.py`).
- Asterisk mock integration test: passed (`python backend/test_asterisk.py`); fake AMI accepted login/originate and a mono 8 kHz WAV prompt was produced.
- Real local eSpeak conversion smoke test: passed; generated 8 kHz mono PCM WAV.
- JavaScript syntax checks: passed (`node --check web/app.js` and `node --check web/comms.js`).
- Additional API smoke tests: authentication/role enforcement, malformed-event rejection, recurring-series update, ICS escaping, backup/restore and student-scoped agenda/acknowledgement passed.

## Not verified in this environment

- Asterisk itself is not installed here, so no real trunk call, ring/answer/hangup cycle or live AMI event stream was tested. Configure the actual PJSIP trunk and dialplan and test with an explicitly consenting test number before enabling calls.
- Meta WhatsApp credentials were not supplied; live message delivery and webhook operation were not tested.
- Flutter/Dart SDK is not installed here; the native Flutter code and plugin dependency resolution could not be compiled or device-tested in this environment.
- The supplied archive had no `.git` directory. This package is a modified source archive, not a commit pushed to a repository.
