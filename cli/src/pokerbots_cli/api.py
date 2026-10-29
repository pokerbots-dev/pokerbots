import json
import os
import urllib.error
import urllib.request

from . import __version__, auth


class ApiError(Exception):
    pass


def base():
    return os.environ.get("PB_API", "https://api.pokerbots.dev").rstrip("/")


def call(method, path, body=None, data=None, headers=None):
    headers = {"User-Agent": f"pb/{__version__}", **(headers or {})}
    if "CF-Access-Client-Id" not in headers:
        credentials = auth.load()
        if not credentials:
            raise ApiError("not logged in: pb login")
        headers["Authorization"] = f"Bearer {credentials['github_token']}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base() + path, data, headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        try:
            message = json.load(e)["error"]
        except (ValueError, KeyError):
            message = f"{e.code} {e.reason}"
        raise ApiError(message) from None
    except urllib.error.URLError as e:
        raise ApiError(str(e.reason)) from None


def admin(method, path, body=None):
    headers = {
        "CF-Access-Client-Id": os.environ.get("CLOUDFLARE_ACCESS_CLIENT_ID", ""),
        "CF-Access-Client-Secret": os.environ.get("CLOUDFLARE_ACCESS_CLIENT_SECRET", ""),
    }
    if not all(headers.values()):
        raise ApiError("set CLOUDFLARE_ACCESS_CLIENT_ID and CLOUDFLARE_ACCESS_CLIENT_SECRET")
    return call(method, "/admin" + path, body, headers=headers)
