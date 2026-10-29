from collections import Counter
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
DECK = tuple(r + s for r in RANKS for s in SUITS)


def rank5(cards):
    values = sorted((RANKS.index(c[0]) for c in cards), reverse=True)
    counts = Counter(values)
    ordered = sorted(counts, key=lambda v: (counts[v], v), reverse=True)
    shape = sorted(counts.values(), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    straight = None
    if len(counts) == 5:
        if values[0] - values[4] == 4:
            straight = values[0]
        elif values == [12, 3, 2, 1, 0]:
            straight = 3
    if straight is not None and flush:
        return (8, straight)
    if shape[0] == 4:
        return (7, *ordered)
    if shape == [3, 2]:
        return (6, *ordered)
    if flush:
        return (5, *values)
    if straight is not None:
        return (4, straight)
    if shape[0] == 3:
        return (3, *ordered)
    if shape == [2, 2, 1]:
        return (2, *ordered)
    if shape[0] == 2:
        return (1, *ordered)
    return (0, *values)


def best(cards):
    return max(rank5(five) for five in combinations(cards, 5))
