import random

from .cards import RANKS, best


def strength(state):
    """Rough 0-1 hand strength: hole cards preflop, then the made hand."""
    hole = state["hole"]
    if not state["board"]:
        high, low = sorted((RANKS.index(c[0]) for c in hole), reverse=True)
        suited = hole[0][1] == hole[1][1]
        return min(1, (high + low) / 24 + 0.35 * (high == low) + 0.05 * suited)
    return min(1, best(hole + state["board"])[0] / 4)


class Style:
    """A simple, sensible bot: calls with enough strength or pot odds, raises its strong hands."""

    call_at = raise_at = aggression = 0.0

    def __init__(self, rng=None):
        self.rng = rng or random.Random()

    def act(self, s):
        hand = strength(s)
        if "raise" in s["legal"] and hand >= self.raise_at and self.rng.random() < self.aggression:
            return ("raise", min(s["max_raise"], max(s["min_raise"], s["current_bet"] + s["pot"] // 2)))
        if "check" in s["legal"]:
            return ("check",)
        odds = s["to_call"] / (s["pot"] + s["to_call"])
        return ("call",) if hand >= max(self.call_at, odds) else ("fold",)


class Tight(Style):
    call_at, raise_at, aggression = 0.6, 0.75, 0.7


class Loose(Style):
    call_at, raise_at, aggression = 0.3, 0.5, 0.5


class Solid(Style):
    call_at, raise_at, aggression = 0.45, 0.65, 0.5


HOUSE = {"tight": Tight, "loose": Loose, "solid": Solid}
BOTS = (Tight, Loose, Solid, Tight, Loose)
