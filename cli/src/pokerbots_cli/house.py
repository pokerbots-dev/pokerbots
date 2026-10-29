import random


class Caller:
    def act(self, state):
        return ("call",) if "call" in state["legal"] else ("check",)


class Raiser:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()

    def act(self, state):
        if "raise" in state["legal"] and self.rng.random() < 0.3:
            return ("raise", min(state["max_raise"], state["min_raise"] + self.rng.randint(0, state["pot"])))
        return Caller().act(state)


BOTS = (Caller, Raiser, Caller, Raiser, Caller)
