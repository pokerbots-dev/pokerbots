import traceback
from time import perf_counter, thread_time

LIMIT = 0.020  # CPU seconds per decision
WALL = 0.100  # backstop so a bot cannot stall the table


def fallback(state):
    return ("check",) if "check" in state["legal"] else ("fold",)


def normalize(action, state):
    if not isinstance(action, (tuple, list)) or not action or action[0] not in state["legal"]:
        return None
    if action[0] != "raise":
        return (action[0],)
    if len(action) < 2 or not isinstance(action[1], int) or isinstance(action[1], bool):
        return None
    return ("raise", min(max(action[1], state["min_raise"]), state["max_raise"]))


class Agent:
    """Runs an untrusted bot: enforces the CPU and wall limits and returns only legal actions.

    CPU time comes from bot.cpu() when the bot runs elsewhere (a sandboxed process), else this thread.
    """

    def __init__(self, bot, limit=LIMIT):
        self.bot = bot
        self.limit = limit
        self.decisions = self.late = self.errors = 0
        self.slowest = 0.0
        self.error = None

    def __call__(self, state):
        self.decisions += 1
        clock = getattr(self.bot, "cpu", thread_time)
        wall, cpu = perf_counter(), clock()
        try:
            action = self.bot.act(state)
        except Exception:
            return self.fail(state, traceback.format_exc())
        wall, cpu = perf_counter() - wall, clock() - cpu
        self.slowest = max(self.slowest, cpu)
        if cpu > self.limit or wall > WALL:
            self.late += 1
            return fallback(state)
        return normalize(action, state) or self.fail(state, f"invalid action {action!r}, legal {state['legal']}")

    def fail(self, state, error):
        self.errors += 1
        self.error = self.error or error
        return fallback(state)
