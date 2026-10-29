import json
import os
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

CLIENT_ID = "Ov23li6ejCOkXTqOb0SW"
DEVICE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"


def credentials_path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "pokerbots" / "credentials.json"


def save(credentials):
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.write_text(json.dumps(credentials))


def load():
    path = credentials_path()
    return json.loads(path.read_text()) if path.exists() else None


def request(url, data=None, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = urllib.parse.urlencode(data).encode() if data else None
    with urllib.request.urlopen(urllib.request.Request(url, body, headers)) as response:
        return json.load(response)


def login(out=print):
    device = request(DEVICE_URL, {"client_id": CLIENT_ID})
    out(f"open  {device['verification_uri']}\ncode  {device['user_code']}")
    webbrowser.open(device["verification_uri"])
    interval = device["interval"]
    deadline = time.monotonic() + device["expires_in"]
    while time.monotonic() < deadline:
        time.sleep(interval)
        reply = request(TOKEN_URL, {
            "client_id": CLIENT_ID,
            "device_code": device["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        if "access_token" in reply:
            user = request(USER_URL, token=reply["access_token"])["login"]
            save({"github_token": reply["access_token"], "user": user})
            return user
        if reply.get("error") == "slow_down":
            interval = reply.get("interval", interval + 5)
        elif reply.get("error") != "authorization_pending":
            raise RuntimeError(reply.get("error_description") or reply.get("error"))
    raise RuntimeError("code expired")
