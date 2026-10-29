import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

from ..api import call

DEFAULT_DAYS = 7


def known_ids(directory):
    return {json.loads(line)["id"] for f in directory.glob("*.jsonl") for line in f.read_text().splitlines() if line}


def history(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    have = known_ids(out)
    params = {
        "since": args.since or (date.today() - timedelta(days=DEFAULT_DAYS)).isoformat(),
        "until": args.until or date.today().isoformat(),
    }
    if args.live or args.paper:
        params["mode"] = "live" if args.live else "paper"
    if args.all:
        params["all"] = "1"
    saved = skipped = 0
    after = None
    while True:
        page = call("GET", "/history?" + urlencode({**params, **({"after": after} if after else {})}))
        for game in page["games"]:
            if game["id"] in have:
                skipped += 1
                continue
            with open(out / f"{game['finished_at'][:10]}.jsonl", "a") as f:
                f.write(json.dumps(game) + "\n")
            saved += 1
        after = page["next"]
        if not after:
            break
    print(f"saved {saved} games to {out}/" + (f", {skipped} already there" if skipped else ""))


def register(sub):
    p = sub.add_parser("history", help="download finished games as JSON lines")
    p.add_argument("--since", metavar="YYYY-MM-DD", help=f"default {DEFAULT_DAYS} days ago")
    p.add_argument("--until", metavar="YYYY-MM-DD", help="default today")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--paper", action="store_true")
    mode.add_argument("--live", action="store_true")
    p.add_argument("--all", action="store_true", help="every player's games, not just yours")
    p.add_argument("-o", "--out", default="history", help="directory, default ./history")
    p.set_defaults(run=history)
