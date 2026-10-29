import io
import sys
import zipfile
from pathlib import Path

from .. import auth
from ..api import call
from ..fmt import money, place, table

MAX_UPLOAD = 1 << 20
ATTEST = "I am 18 or older, and paid skill competitions are allowed where I am. [y/N] "


def login(args):
    try:
        print(f"logged in as {auth.login()}")
    except (RuntimeError, OSError) as e:
        sys.exit(f"login failed: {e}")


def bundle(directory):
    root = Path(directory)
    if not (root / "bot.py").exists():
        sys.exit(f"no bot.py in {directory}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if path.is_file() and not any(p.startswith(".") or p == "__pycache__" for p in relative.parts):
                z.write(path, relative.as_posix())
    if buffer.tell() > MAX_UPLOAD:
        sys.exit("bot is over 1 MB zipped")
    return buffer.getvalue()


def upload(args):
    reply = call("POST", "/versions", data=bundle(args.dir), headers={"Content-Type": "application/zip"})
    print(f"uploaded v{reply['version']}")


def deploy(args):
    mode = "live" if args.live else "paper"
    if mode == "live" and not call("GET", "/me")["attested"]:
        if input(ATTEST).strip().lower() != "y":
            sys.exit("not deployed")
        call("POST", "/attest")
    call("POST", "/deployments", {"mode": mode, "version": int(args.version.lstrip("v"))})
    print(f"{args.version} deployed {mode}")


def stop(args):
    mode = "live" if args.live else "paper"
    call("DELETE", f"/deployments/{mode}")
    print(f"stopped {mode}")


def status(args):
    me = call("GET", "/me")
    rows = [["user", me["login"]], ["versions", " ".join(f"v{v}" for v in me["versions"]) or "-"]]
    for mode in ("paper", "live"):
        d = me["deployments"].get(mode)
        rows.append([mode, f"v{d['version']}  rating {d['rating']:.0f}  games {d['games']}  today {d['today']}" if d else "-"])
    rows += [["balance", money(me["balance"])], ["wallet", me["wallet"] or "-"]]
    print(table(rows))
    games = call("GET", "/games")
    if games:
        print()
        print(table([["game", "mode", "place", "hands"]] + [
            [g["created_at"], g["mode"], place(g["place"]), g["hands"] or "-"] for g in games
        ]))


def register(sub):
    sub.add_parser("login", help="sign in with GitHub").set_defaults(run=login)

    p = sub.add_parser("upload", help="upload a new version")
    p.add_argument("dir", nargs="?", default=".")
    p.set_defaults(run=upload)

    for name, run, help in (("deploy", deploy, "play a version"), ("stop", stop, "stop playing")):
        p = sub.add_parser(name, help=help)
        if name == "deploy":
            p.add_argument("version", help="e.g. v1")
        mode = p.add_mutually_exclusive_group(required=True)
        mode.add_argument("--paper", action="store_true")
        mode.add_argument("--live", action="store_true")
        p.set_defaults(run=run)

    sub.add_parser("status", help="your bot, rating, balance and recent games").set_defaults(run=status)
