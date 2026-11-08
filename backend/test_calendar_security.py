"""Offline authorization tests for the calendar API policy helper."""
import os, tempfile
os.environ["CAL_DATA"] = tempfile.mkdtemp(prefix="mnh-calendar-auth-")
os.environ["CAL_DEV_AUTH"] = "0"          # test the real token policy, not the local bypass
import db, comms, main
from starlette.requests import Request
from fastapi import HTTPException

db.init()
with db.conn() as c:
    comms.init(c)
    admin = comms.new_staff(c, "Test Admin", "admin")
    coordinator = comms.new_staff(c, "Test Coordinator", "coordinator")
    hod = comms.new_staff(c, "Test HOD", "hod")
    student_person = comms.save_person(c, {"name": "Test Student", "role": "student", "phone": "0991234567", "module_id": 1})
    student = comms.new_staff(c, "Test Student", "student", student_person)

def request(token=None):
    headers = [] if token is None else [(b"authorization", ("Bearer " + token).encode())]
    return Request({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                    "method": "GET", "scheme": "http", "path": "/api/bootstrap",
                    "raw_path": b"/api/bootstrap", "query_string": b"", "headers": headers,
                    "server": ("test", 80), "client": ("test", 1234)})

assert main.calendar_user(request(admin), "calendar_edit") == "Test Admin"
assert main.calendar_user(request(coordinator), "calendar_edit") == "Test Coordinator"
assert main.calendar_user(request(hod), "calendar_view") == "Test HOD"
assert main.calendar_user(request(student), "calendar_view") == "Test Student"
for token, permission, expected in ((None, "calendar_view", 401), (hod, "calendar_edit", 403), (student, "calendar_edit", 403)):
    try:
        main.calendar_user(request(token), permission)
        raise AssertionError(f"Expected HTTP {expected}")
    except HTTPException as exc:
        assert exc.status_code == expected
print("Calendar authorization tests passed: unauthenticated blocked; student/HOD read-only; coordinator/admin edit allowed.")
