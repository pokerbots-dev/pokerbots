import random

from pokerbots_cli import engine
from pokerbots_cli.agent import Agent
from pokerbots_cli.house import BOTS, Raiser


def shove(state):
    if "raise" in state["legal"]:
        return ("raise", state["max_raise"])
    return ("call",) if "call" in state["legal"] else ("check",)


def test_games_conserve_chips_and_rank_everyone():
    rng = random.Random(1)
    for _ in range(20):
        result = engine.play([Agent(Raiser(rng))] + [Agent(cls()) for cls in BOTS], rng)
        assert sum(result.stacks) == 6 * engine.STACK
        assert sorted(result.places) == list(range(6))
        assert result.hands <= engine.MAX_HANDS


def test_side_pots():
    stacks = [100, 300, 300]
    players = [engine.Player(seat, shove, stack) for seat, stack in enumerate(stacks)]
    dealt = "Ah Ad Kh Kd Qh Qd 2c 7d 9h Js 4c".split()
    engine.Hand(1, players, 0, dealt[::-1], 3).play()
    assert [p.stack for p in players] == [300, 400, 0]


def test_heads_up_button_posts_small_blind():
    seen = []
    players = [engine.Player(s, lambda st: seen.append(st) or ("fold",)) for s in range(2)]
    engine.Hand(3, players, 1, list(engine.DECK), 2).play()
    assert seen[0]["seat"] == 1 and seen[0]["bets"] == [6, 3]
    assert [p.stack for p in players] == [1003, 997]
