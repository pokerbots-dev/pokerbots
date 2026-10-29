import traceback
from time import perf_counter

LIMIT = 0.020


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
    """Runs an untrusted bot: enforces the time limit and returns only legal actions."""

    def __init__(self, bot, limit=LIMIT):
        self.bot = bot
        self.limit = limit
        self.decisions = self.late = self.errors = 0
        self.slowest = 0.0
        self.error = None

    def __call__(self, state):
        self.decisions += 1
        start = perf_counter()
        try:
            action = self.bot.act(state)
        except Exception:
            return self.fail(state, traceback.format_exc())
        elapsed = perf_counter() - start
        self.slowest = max(self.slowest, elapsed)
        if elapsed > self.limit:
            self.late += 1
            return fallback(state)
        return normalize(action, state) or self.fail(state, f"invalid action {action!r}, legal {state['legal']}")

    def fail(self, state, error):
        self.errors += 1
        self.error = self.error or error
        return fallback(state)
