import time

from pokerbots_cli.agent import Agent

STATE = {"legal": ["fold", "call", "raise"], "min_raise": 40, "max_raise": 500}


class Fixed:
    def __init__(self, reply):
        self.reply = reply

    def act(self, state):
        return self.reply(state)


def run(reply):
    agent = Agent(Fixed(reply))
    return agent(dict(STATE)), agent


def test_legal_actions_pass_and_raises_clamp():
    assert run(lambda s: ("call",))[0] == ("call",)
    assert run(lambda s: ("raise", 10_000))[0] == ("raise", 500)
    assert run(lambda s: ("raise", 1))[0] == ("raise", 40)


def test_bad_bots_fold():
    action, agent = run(lambda s: time.sleep(0.03))
    assert action == ("fold",) and agent.late == 1
    action, agent = run(lambda s: 1 / 0)
    assert action == ("fold",) and "ZeroDivisionError" in agent.error
    action, agent = run(lambda s: ("check",))
    assert action == ("fold",) and agent.errors == 1
