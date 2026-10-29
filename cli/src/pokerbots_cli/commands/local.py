import pydoc
import random
import shutil
import subprocess
import sys
import tempfile
from importlib import resources
from pathlib import Path

from .. import engine
from ..agent import Agent
from ..fmt import table
from ..house import BOTS
from ..sandbox import ProcessBot, read_only_copy
from .account import MAX_UPLOAD, bundle

SAFE_MS = 10

PACKAGE = resources.files("pokerbots_cli")


def docs(args):
    text = PACKAGE.joinpath("docs.md").read_text()
    if args.plain or not sys.stdout.isatty():
        print(text, end="")
    else:
        pydoc.pager(text)


def init(args):
    path = Path(args.name)
    if path.exists():
        sys.exit(f"{path} already exists")
    path.mkdir(parents=True)
    shutil.copy(PACKAGE.joinpath("template", "bot.py"), path / "bot.py")
    print(f"created {path / 'bot.py'}")


def play(args, directory, mine, places):
    rng = random.Random(args.seed)
    for _ in range(args.games):
        mine.bot = ProcessBot(directory, stderr=subprocess.PIPE)
        if not mine.bot.alive:
            sys.exit(f"bot.py did not start (servers allow the Python standard library only):\n\n{mine.bot.startup_error}")
        agents = [mine] + [Agent(cls()) for cls in BOTS]
        rng.shuffle(agents)
        try:
            places.append(engine.play(agents, rng).places.index(agents.index(mine)) + 1)
        finally:
            mine.bot.close()


def test(args):
    """Plays local games with the bot run as on the servers: own process, standard library only, no file writes."""
    directory = Path(args.dir)
    size = len(bundle(directory))
    mine, places = Agent(None), []
    with tempfile.TemporaryDirectory() as root:
        copy = Path(root) / "bot"
        read_only_copy(directory, copy)
        try:
            play(args, copy, mine, places)
        finally:
            for path in [copy, *copy.rglob("*")]:
                path.chmod(0o755 if path.is_dir() else 0o644)
    slowest = mine.slowest * 1000
    print(table([
        ["games", args.games],
        ["1st", places.count(1)],
        ["2nd", places.count(2)],
        ["avg place", f"{sum(places) / len(places):.1f}"],
        ["decisions", mine.decisions],
        ["late", mine.late],
        ["errors", mine.errors],
        ["slowest", f"{slowest:.2f} ms" + ("  servers are slower: aim under 10 ms" if slowest > SAFE_MS else "")],
        ["size", f"{size / 1e6:.2f} MB of {MAX_UPLOAD / 1e6:.0f} MB"],
    ], labels=True))
    if mine.error:
        print(f"\nfirst error\n{mine.error}")
        return 1


def upgrade(args):
    """Upgrade with whichever installer pb came from; --refresh skips uv's stale package index."""
    if shutil.which("uv"):
        command = ["uv", "tool", "install", "--refresh", "pokerbots-dev@latest"]
    elif shutil.which("pipx"):
        command = ["pipx", "upgrade", "pokerbots-dev"]
    else:
        command = [sys.executable, "-m", "pip", "install", "--upgrade", "pokerbots-dev"]
    return subprocess.call(command)


def register(sub):
    p = sub.add_parser("docs", help="show the docs")
    p.add_argument("--plain", action="store_true", help="no pager, for agents")
    p.set_defaults(run=docs)

    p = sub.add_parser("init", help="create a bot")
    p.add_argument("name")
    p.set_defaults(run=init)

    p = sub.add_parser("test", help="play local games against house bots")
    p.add_argument("dir", nargs="?", default=".")
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--seed", type=int)
    p.set_defaults(run=test)

    sub.add_parser("upgrade", help="upgrade pb to the latest version").set_defaults(run=upgrade)
