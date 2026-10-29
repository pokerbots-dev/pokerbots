import importlib.util
import pydoc
import random
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

from .. import engine
from ..agent import Agent
from ..fmt import table
from ..house import BOTS

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


def load_bot(directory):
    path = Path(directory) / "bot.py"
    if not path.exists():
        sys.exit(f"no bot.py in {directory}")
    sys.path.insert(0, str(path.parent.resolve()))
    spec = importlib.util.spec_from_file_location("bot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Bot


def test(args):
    Bot = load_bot(args.dir)
    rng = random.Random(args.seed)
    mine = Agent(None)
    places = []
    for _ in range(args.games):
        mine.bot = Bot()
        agents = [mine] + [Agent(cls()) for cls in BOTS]
        rng.shuffle(agents)
        places.append(engine.play(agents, rng).places.index(agents.index(mine)) + 1)
    print(table([
        ["games", args.games],
        ["1st", places.count(1)],
        ["2nd", places.count(2)],
        ["avg place", f"{sum(places) / len(places):.1f}"],
        ["decisions", mine.decisions],
        ["late", mine.late],
        ["errors", mine.errors],
        ["slowest", f"{mine.slowest * 1000:.2f} ms cpu"],
    ]))
    if mine.error:
        print(f"\nfirst error\n{mine.error}")
        return 1


def upgrade(args):
    """Upgrade with whichever installer pb came from; --refresh skips uv's stale package index."""
    if shutil.which("uv"):
        command = ["uv", "tool", "upgrade", "--refresh", "pokerbots-dev"]
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
