import random
from dataclasses import dataclass, field

from .cards import DECK, best

STACK = 1000
MAX_HANDS = 100
STREETS = ("preflop", "flop", "turn", "river")


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
class Game:
    """What every hand of one game shares: names, finished hands, eliminations."""
    names: list
    max_hands: int = MAX_HANDS
    past: list = field(default_factory=list)  # public summaries, as bots see them
    hands: list = field(default_factory=list)  # full records, every hole card
    out: list = field(default_factory=list)


@dataclass
class Result:
    places: list
    hands: int
    stacks: list
    history: list


def per_seat(n, values=None, default=None):
    out = [default] * n
    for seat, value in (values or {}).items():
        out[seat] = value
    return out


class Hand:
    def __init__(self, number, players, button, deck, game):
        self.number = number
        self.players = players
        self.button = button
        self.deck = deck
        self.game = game
        self.seats = len(game.names)
        self.blinds = [number, 2 * number]
        self.board = []
        self.log = []

    def play(self):
        n = len(self.players)
        self.stacks_start = per_seat(self.seats, {p.seat: p.stack for p in self.players}, 0)
        for p in self.players:
            p.hole = (self.deck.pop(), self.deck.pop())
            p.bet = p.committed = 0
            p.folded = False
        small = self.button if n == 2 else (self.button + 1) % n
        self.blind_seats = [self.players[small].seat, self.players[(small + 1) % n].seat]
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
        self.finish(self.award())

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
            state = self.state(p, legal, to_call, current)
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

    def state(self, p, legal, to_call, current):
        stacks, bets = [0] * self.seats, [0] * self.seats
        for q in self.players:
            stacks[q.seat], bets[q.seat] = q.stack, q.bet
        return {
            "hand": self.number,
            "hands_left": self.game.max_hands - self.number,
            "street": STREETS[max(0, len(self.board) - 2)],
            "seat": p.seat,
            "players": list(self.game.names),
            "button": self.players[self.button].seat,
            "small_blind": self.blind_seats[0],
            "big_blind": self.blind_seats[1],
            "blinds": list(self.blinds),
            "hole": list(p.hole),
            "board": list(self.board),
            "stacks_start": list(self.stacks_start),
            "stacks": stacks,
            "bets": bets,
            "current_bet": current,
            "pot": sum(q.committed for q in self.players),
            "to_call": to_call,
            "legal": legal,
            "live": [q.seat for q in self.players if not q.folded],
            "all_in": [q.seat for q in self.players if not q.folded and q.stack == 0],
            "out": list(self.game.out),
            "actions": [list(a) for a in self.log],
            "past": list(self.game.past),
        }

    def award(self):
        live = [p for p in self.players if not p.folded]
        strength = {p.seat: best(p.hole + tuple(self.board)) for p in live} if len(live) > 1 else {}
        won = {}
        previous = 0
        for level in sorted({p.committed for p in self.players}):
            pot = sum(min(p.committed, level) - min(p.committed, previous) for p in self.players)
            previous = level
            # nobody live matched this level: the chips were uncalled and go back to whoever bet them
            eligible = [p for p in live if p.committed >= level] or [p for p in self.players if p.committed >= level]
            top = max(strength.get(p.seat, ()) for p in eligible)
            winners = [p for p in eligible if strength.get(p.seat, ()) == top]
            share, odd = divmod(pot, len(winners))
            for i, w in enumerate(winners):
                w.stack += share + (i < odd)
                won[w.seat] = won.get(w.seat, 0) + share + (i < odd)
        return won

    def finish(self, won):
        shown = {p.seat: list(p.hole) for p in self.players if not p.folded} if sum(not p.folded for p in self.players) > 1 else {}
        summary = {
            "hand": self.number,
            "board": list(self.board),
            "shown": per_seat(self.seats, shown),
            "won": per_seat(self.seats, won, 0),
        }
        self.game.past.append(summary)
        self.game.hands.append({
            **summary,
            "button": self.players[self.button].seat,
            "small_blind": self.blind_seats[0],
            "big_blind": self.blind_seats[1],
            "blinds": list(self.blinds),
            "stacks_start": list(self.stacks_start),
            "hole": per_seat(self.seats, {p.seat: list(p.hole) for p in self.players}),
            "actions": [list(a) for a in self.log],
        })


def play(agents, rng=None, max_hands=MAX_HANDS, names=None):
    rng = rng or random.Random()
    table = [Player(seat, agent) for seat, agent in enumerate(agents)]
    game = Game(list(names or [f"seat {i}" for i in range(len(table))]), max_hands)
    button = rng.randrange(len(table))
    hands = 0
    while hands < max_hands and sum(p.stack > 0 for p in table) > 1:
        hands += 1
        alive = [p for p in table if p.stack > 0]
        b = next((i for i, p in enumerate(alive) if p.seat >= button), 0)
        before = {p.seat: p.stack for p in alive}
        Hand(hands, alive, b, rng.sample(DECK, len(DECK)), game).play()
        game.out += sorted((p.seat for p in alive if p.stack == 0), key=before.get)
        button = alive[b].seat + 1
    standing = sorted((p for p in table if p.stack > 0), key=lambda p: -p.stack)
    return Result([p.seat for p in standing] + game.out[::-1], hands, [p.stack for p in table], game.hands)
