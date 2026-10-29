import io
from datetime import datetime, timezone
import pydoc
import shutil
import sys
import time
import zipfile
from pathlib import Path

from .. import auth
from ..api import ApiError, call
from ..fmt import INK, PAPER, colored, held, money, place, signed, table, when

MAX_UPLOAD = 5_000_000
WATCH_SECONDS = 5
SEATS = 6
RECENT = 10
SCREEN_LINES_USED = 18
BROKEN_AFTER_GAMES = 5
BROKEN_RATE = 0.05
ATTEST = "I am 18 or older, and paid skill competitions are allowed where I am. [y/N] "


def login(args):
    if current := auth.load():
        return print(f"already logged in as {current['user']}; pb logout to switch")
    try:
        print(f"logged in as {auth.login()}")
    except (RuntimeError, OSError) as e:
        sys.exit(f"login failed: {e}")


def logout(args):
    if not auth.load():
        return print("not logged in")
    try:
        call("DELETE", "/session")
    except ApiError:
        pass  # the local logout still matters if the server is unreachable
    auth.credentials_path().unlink()
    print(f"logged out; your wallet stays at {auth.credentials_path().with_name('wallet.json')}")


def whoami(args):
    current = auth.load()
    print(f"{current['user']}  github.com/{current['user']}  pokerbots.dev/{current['user']}" if current else "not logged in: pb login")


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
        sys.exit(f"bot is over {MAX_UPLOAD // 1_000_000} MB zipped")
    return buffer.getvalue()


def upload(args):
    reply = call("POST", "/versions", data=bundle(args.dir), headers={"Content-Type": "application/zip"})
    print(f"uploaded v{reply['version']}")


def deploy(args):
    mode = "live" if args.live else "paper"
    if mode == "live" and not call("GET", "/me")["attested"]:
        try:
            agreed = input(ATTEST).strip().lower() == "y"
        except EOFError:
            agreed = False
        if not agreed:
            sys.exit("not deployed")
        call("POST", "/attest")
    call("POST", "/deployments", {"mode": mode, "version": int(args.version.lstrip("v"))})
    print(f"{args.version} deployed {mode}")


def stop(args):
    mode = "live" if args.live else "paper"
    call("DELETE", f"/deployments/{mode}")
    print(f"stopped {mode}; games already queued will still play")


def rank(me, mode):
    st = me["stats"].get(mode)
    return f"#{st['rank']} of {st['ranked']}" if st and st["rank"] else "unranked until 20 games"


def note(me, mode, d):
    """Why a deployed bot might not be playing right now."""
    if mode == "paper" and d["today"] >= me.get("paper_limit", float("inf")):
        now = datetime.now(timezone.utc)
        hours = 24 - now.hour - (now.minute > 0)
        return f"  limit reached: {me['paper_limit']:,} today, resumes 00:00 UTC (in {hours}h)"
    if mode == "live" and "live" in me.get("paused", []):
        return "  paused for maintenance"
    if mode == "live" and me["balance"] < me["buy_in"]:
        return f"  paused: balance below {money(me['buy_in'])}"
    return ""


def playing(p):
    bots = lambda n: f"{n} bot{'' if n == 1 else 's'}"
    live = f"{bots(p['live'])} playing" if p["live"] >= p["needed"] else f"{bots(p['live'])}, {p['needed']} needed to start"
    text = f"paper {bots(p['paper'])}   live {live}"
    return text + ("\n" + "games are delayed on our side; nothing is wrong with your bot" if p["delayed"] else "")


def moving(entry):
    label = {"pending": "pending review", "approved": "sending", "sent": "confirming"}[entry["status"]]
    return f"{entry['kind']} {money(entry['amount'])} {label}"


def quality(d):
    """Late and error rates for the deployed version; flags a version that looks broken."""
    if not d.get("decisions"):
        return ""
    late, errors = d["late"] / d["decisions"], d["errors"] / d["decisions"]
    text = f"late {late:.1%}  errors {errors:.1%}"
    if d["version_games"] >= BROKEN_AFTER_GAMES and late + errors > BROKEN_RATE:
        text += f"  v{d['version']} looks broken: pb games"
    return text


def game_rows(games):
    live = any(g["mode"] == "live" for g in games)
    head = ["game", "mode", "place", "hands", "rating", "late", "errors"] + (["won"] if live else [])
    return table([head] + [
        [when(g["created_at"]), g["mode"], place(g["place"]), g["hands"] or "-", signed(g.get("rating_delta")),
         g.get("late") if g.get("late") is not None else "-", g.get("errors") if g.get("errors") is not None else "-"]
        + ([signed(g.get("net"), "money")] if live else [])
        for g in games
    ], header=True)


def report(limit=RECENT):
    me = call("GET", "/me")
    rows = [["user", me["login"] + ("  suspended: you can still withdraw; hello@pokerbots.dev" if me.get("suspended") else "")], ["profile", f"pokerbots.dev/{me['login']}"], ["versions", " ".join(f"v{v}" for v in me["versions"]) or "-"]]
    for mode in ("paper", "live"):
        d = me["deployments"].get(mode)
        if not d:
            rows.append([mode, "-"])
            continue
        rows.append([mode, f"v{d['version']}  rating {d['rating']:.0f}  games {d['games']}  {rank(me, mode)}{note(me, mode, d)}"])
        st = me["stats"].get(mode)
        today = f"today {signed(d['rating_today'])} over {d['today']} games" + (f"   best {st['best']}" if st else "")
        if mode == "live":
            today += f"   won today {signed(d['won_today'], 'money')}" + (f", all time {signed(st['won'], 'money')}" if st and st["won"] is not None else "")
        broken = d.get("startup_error") and f"v{d['version']} fails to start on the servers: {d['startup_error'].splitlines()[-1]}"
        rows += [["", line] for line in (today, quality(d), broken) if line]
    lines = playing(me["players"]).split("\n") if me.get("players") else []
    rows += [["players" if i == 0 else "", line] for i, line in enumerate(lines)]
    rows += [["balance", f"{money(me['balance'])} on pokerbots, for live buy-ins"]] + [["", moving(m)] for m in me.get("moving", [])]
    rows += [["wallet", held(me)]]
    text = table(rows, labels=True)
    games = call("GET", f"/games?limit={limit}")
    return text + ("\n\n" + game_rows(games) if games else "")


def leaderboard(mode):
    board = call("GET", f"/leaderboard/{mode}")
    live = mode == "live"
    head = ["rank", "user", "rating", "games"] + (["won"] if live else [])
    rows = [[i + 1, r["login"], f"{r['rating']:.0f}", r["games"]] + ([signed(r["won"], "money")] if live else [])
            for i, r in enumerate(board["rows"])]
    text = f"{mode} leaderboard\n\n" + (table([head] + rows, header=True) if rows else f"no bots with {board['min_games']} games yet")
    you = f"#{board['you']} of {board['ranked']}" if board["you"] else f"unranked until {board['min_games']} games"
    return text + "\n\n" + table([["you", you]], labels=True)


def screen(render):
    """Full-screen, flicker-free view in the homepage colours, redrawn until ctrl-c."""
    if not sys.stdout.isatty():
        return print(render())
    paint = f"\x1b[48;2;{INK}m\x1b[38;2;{PAPER}m" if colored() else ""
    sys.stdout.write("\x1b[?1049h\x1b[?25l" + paint + "\x1b[2J")
    try:
        while True:
            lines = ["", *("  " + line for line in render().split("\n")), "", "  ctrl-c to quit"]
            sys.stdout.write("\x1b[H" + "".join(line + "\x1b[K\n" for line in lines) + "\x1b[J")
            sys.stdout.flush()
            time.sleep(WATCH_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")


def status(args):
    print(report())


def watch(args):
    screen(lambda: report(max(RECENT, shutil.get_terminal_size().lines - SCREEN_LINES_USED)))


def games(args):
    mode = "&mode=live" if args.live else "&mode=paper" if args.paper else ""
    rows = call("GET", f"/games?limit={args.n}{mode}")
    text = game_rows(rows) if rows else "no games yet"
    if sys.stdout.isatty():
        pydoc.pager(text)
    else:
        print(text)


def top(args):
    screen(lambda: leaderboard("live" if args.live else "paper"))


def register(sub):
    sub.add_parser("login", help="sign in with GitHub").set_defaults(run=login)
    sub.add_parser("logout", help="sign out; keeps your wallet").set_defaults(run=logout)
    sub.add_parser("whoami", help="who you are logged in as").set_defaults(run=whoami)
    sub.add_parser("watch", help="status, live").set_defaults(run=watch)
    p = sub.add_parser("top", help="leaderboard, live")
    p.add_argument("--live", action="store_true", help="live play instead of paper")
    p.set_defaults(run=top)

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

    p = sub.add_parser("games", help="your past games, scrollable")
    p.add_argument("-n", type=int, default=100, help="how many, default 100")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--paper", action="store_true")
    mode.add_argument("--live", action="store_true")
    p.set_defaults(run=games)
