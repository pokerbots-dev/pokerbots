from pokerbots_cli.cards import best


def hand(text):
    return best(text.split())


def test_categories_ordered():
    ladder = [
        "2c 7d 9h Js Kc 3d 4h",  # high card
        "2c 2d 9h Js Kc 3d 4h",  # pair
        "2c 2d 9h 9s Kc 3d 4h",  # two pair
        "2c 2d 2h Js Kc 3d 4h",  # trips
        "Ac 2d 3h 4s 5c 9d Jh",  # wheel
        "6c 2d 3h 4s 5c 9d Jh",  # six-high straight
        "2c 7c 9c Jc Kc 3d 4h",  # flush
        "2c 2d 2h Js Jc 3d 4h",  # full house
        "2c 2d 2h 2s Kc 3d 4h",  # quads
        "Ac 2c 3c 4c 5c 9d Jh",  # steel wheel
    ]
    ranks = [hand(h) for h in ladder]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)


def test_kicker_and_board_play():
    assert hand("As Kd 7c 7d 9h Js 2c") > hand("As Qd 7c 7d 9h Js 2c")
    assert hand("2s 3d Ac Kc Qc Jc Tc") == hand("4s 5d Ac Kc Qc Jc Tc")
