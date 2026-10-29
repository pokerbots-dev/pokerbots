import random
from dataclasses import dataclass

from .cards import DECK, best

STACK = 1000
MAX_HANDS = 100


@dataclass
class Player:
    seat: int
    agent: object
    stack: int = STACK
    hole: tuple = ()
    bet: int = 0
    committed: int = 0
    folded: bool = False

    @property
    def can_act(self):
        return not self.folded and self.stack > 0

    def put(self, chips):
        chips = min(chips, self.stack)
        self.stack -= chips
        self.bet += chips
        self.committed += chips


@dataclass
class Result:
    places: list
    hands: int
    stacks: list


class Hand:
    def __init__(self, number, players, button, deck, seats):
        self.number = number
        self.players = players
        self.button = button
        self.deck = deck
        self.seats = seats
        self.blinds = [number, 2 * number]
        self.board = []
        self.log = []

    def play(self):
        n = len(self.players)
        for p in self.players:
            p.hole = (self.deck.pop(), self.deck.pop())
            p.bet = p.committed = 0
            p.folded = False
        small = self.button if n == 2 else (self.button + 1) % n
        for i, blind in zip((small, (small + 1) % n), self.blinds):
            self.players[i].put(blind)
            self.record(self.players[i], "blind")
        self.betting((small + 2) % n, self.blinds[1])
        for count in (3, 1, 1):
            if sum(not p.folded for p in self.players) < 2:
                break
            for p in self.players:
                p.bet = 0
            self.board += [self.deck.pop() for _ in range(count)]
            self.betting((self.button + 1) % n, 0)
        self.award()

    def betting(self, start, current):
        order = self.players[start:] + self.players[:start]
        queue = [p for p in order if p.can_act]
        step = self.blinds[1]
        while queue and sum(not p.folded for p in self.players) > 1:
            p = queue.pop(0)
            others = any(q.can_act for q in self.players if q is not p)
            if not p.can_act or (p.bet >= current and not others):
                continue
            to_call = current - p.bet
            legal = ["fold", "call"] if to_call > 0 else ["check"]
            state = self.state(p, legal, to_call)
            if others and p.stack > to_call:
                legal.append("raise")
                state["max_raise"] = p.bet + p.stack
                state["min_raise"] = min(current + step, state["max_raise"])
            action = p.agent(state)
            if action[0] == "fold":
                p.folded = True
            elif action[0] == "call":
                p.put(to_call)
            elif action[0] == "raise":
                p.put(action[1] - p.bet)
                step = max(step, p.bet - current)
                current = max(current, p.bet)
                i = order.index(p)
                queue = [q for q in order[i + 1:] + order[:i] if q.can_act]
            self.record(p, action[0])

    def record(self, p, action):
        self.log.append([len(self.board), p.seat, action, p.bet])

    def state(self, p, legal, to_call):
        stacks, bets = [0] * self.seats, [0] * self.seats
        for q in self.players:
            stacks[q.seat], bets[q.seat] = q.stack, q.bet
        return {
            "hand": self.number,
            "seat": p.seat,
            "button": self.players[self.button].seat,
            "blinds": list(self.blinds),
            "hole": list(p.hole),
            "board": list(self.board),
            "stacks": stacks,
            "bets": bets,
            "pot": sum(q.committed for q in self.players),
            "to_call": to_call,
            "legal": legal,
            "live": [q.seat for q in self.players if not q.folded],
            "actions": [list(a) for a in self.log],
        }

    def award(self):
        live = [p for p in self.players if not p.folded]
        strength = {p.seat: best(p.hole + tuple(self.board)) for p in live} if len(live) > 1 else {}
        previous = 0
        for level in sorted({p.committed for p in self.players}):
            pot = sum(min(p.committed, level) - min(p.committed, previous) for p in self.players)
            previous = level
            eligible = [p for p in live if p.committed >= level]
            top = max(strength.get(p.seat, ()) for p in eligible)
            winners = [p for p in eligible if strength.get(p.seat, ()) == top]
            share, odd = divmod(pot, len(winners))
            for i, w in enumerate(winners):
                w.stack += share + (i < odd)


def play(agents, rng=None, max_hands=MAX_HANDS):
    rng = rng or random.Random()
    table = [Player(seat, agent) for seat, agent in enumerate(agents)]
    busted = []
    button = rng.randrange(len(table))
    hands = 0
    while hands < max_hands and sum(p.stack > 0 for p in table) > 1:
        hands += 1
        alive = [p for p in table if p.stack > 0]
        b = next((i for i, p in enumerate(alive) if p.seat >= button), 0)
        before = {p.seat: p.stack for p in alive}
        Hand(hands, alive, b, rng.sample(DECK, len(DECK)), len(table)).play()
        busted += sorted((p.seat for p in alive if p.stack == 0), key=before.get)
        button = alive[b].seat + 1
    standing = sorted((p for p in table if p.stack > 0), key=lambda p: -p.stack)
    return Result([p.seat for p in standing] + busted[::-1], hands, [p.stack for p in table])
