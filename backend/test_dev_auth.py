"""Offline tests for the local-development login bypass and production enforcement.

Development (default) auto-signs an admin-equivalent local session when no valid
staff token is presented. Production/staging always requires a real staff token.
No network access and no real backend records are touched (CAL_DATA is a scratch dir).
"""
import os, tempfile
os.environ["CAL_DATA"] = tempfile.mkdtemp(prefix="mnh-dev-auth-")
for _k in ("CAL_ENV", "APP_ENV", "ENVIRONMENT", "FASTAPI_ENV", "CAL_DEV_AUTH"):
    os.environ.pop(_k, None)
import db, comms, main
from comms_api import who as comms_who
from starlette.requests import Request
from fastapi import HTTPException

db.init()
with db.conn() as c:
    comms.init(c)


def request(token=None):
    headers = [] if token is None else [(b"authorization", ("Bearer " + token).encode())]
    return Request({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                    "method": "GET", "scheme": "http", "path": "/api/bootstrap",
                    "raw_path": b"/api/bootstrap", "query_string": b"", "headers": headers,
                    "server": ("test", 80), "client": ("test", 1234)})


def expect(code, fn):
    try:
        fn()
    except HTTPException as exc:
        assert exc.status_code == code, f"expected {code}, got {exc.status_code}"
    else:
        raise AssertionError(f"expected HTTP {code}, request succeeded")


# ---------- development (no CAL_ENV) ----------
assert comms.dev_auth_enabled(), "development should enable the login bypass"
dev = main.calendar_staff(request(), "calendar_edit")
assert dev["role"] == "admin", "dev session must be admin-equivalent"
assert dev["name"] == comms.DEV_NAME
assert main.calendar_staff(request("not-a-real-token"), "calendar_edit")["id"] == dev["id"], \
    "an invalid token must fall back to the same dev session"
assert comms_who(request(), "*")["id"] == dev["id"], "communications gate must accept the dev session"
assert isinstance(main.bootstrap(request()), dict) and "events" in main.bootstrap(request())
assert main.calendar_user(request(), "calendar_edit") == comms.DEV_NAME

# a real token still keeps its own (lower) role in development
with db.conn() as c:
    hod = comms.new_staff(c, "Dev HOD", "hod")
assert main.calendar_staff(request(hod), "calendar_view")["role"] == "hod"
expect(403, lambda: main.calendar_staff(request(hod), "calendar_edit"))

# explicit local opt-out restores token enforcement
os.environ["CAL_DEV_AUTH"] = "0"
assert not comms.dev_auth_enabled()
expect(401, lambda: main.calendar_staff(request()))
expect(401, lambda: comms_who(request(), "view"))
os.environ.pop("CAL_DEV_AUTH")

# ---------- production ----------
os.environ["CAL_ENV"] = "production"
assert not comms.dev_auth_enabled()
os.environ["CAL_DEV_AUTH"] = "1"                     # a stray flag must not open production
assert not comms.dev_auth_enabled(), "production must always win over CAL_DEV_AUTH"
expect(401, lambda: main.calendar_staff(request()))
expect(401, lambda: comms_who(request(), "view"))
expect(401, lambda: main.bootstrap(request()))

with db.conn() as c:
    admin = comms.new_staff(c, "Production Admin", "admin")
    prod_hod = comms.new_staff(c, "Production HOD", "hod")
assert main.calendar_staff(request(admin), "calendar_edit")["name"] == "Production Admin"
assert comms_who(request(admin), "*")["name"] == "Production Admin"
expect(403, lambda: main.calendar_staff(request(prod_hod), "calendar_edit"))
expect(403, lambda: comms_who(request(prod_hod), "*"))
expect(401, lambda: main.calendar_staff(request("not-a-real-token")))

# ---------- staging is treated as production too ----------
os.environ["CAL_ENV"] = "staging"
assert not comms.dev_auth_enabled()
expect(401, lambda: main.calendar_staff(request()))

# ---------- back to development ----------
for _k in ("CAL_ENV", "CAL_DEV_AUTH"):
    os.environ.pop(_k, None)
assert comms.dev_auth_enabled()
assert main.calendar_staff(request())["id"] == dev["id"]

print("Dev auth tests passed: local bypass auto-signs in as admin; CAL_DEV_AUTH=0 disables it; "
      "production/staging reject anonymous requests and still enforce roles and tokens.")
