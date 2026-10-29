import base64
import os
import io
import zipfile

import pytest

from server import run_game


def bot(body):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("bot.py", "import time\nclass Bot:\n    def act(self, state):\n" + body)
    return {"code": base64.b64encode(buffer.getvalue()).decode()}


def test_game_with_sandboxed_bots():
    result = run_game({"seed": 1, "bots": [
        bot("        return ('call',) if 'call' in state['legal'] else ('check',)\n"),
        bot("        end = time.process_time() + 0.03\n        while time.process_time() < end: pass\n"),
        bot("        1 / 0\n"),
        {"house": "tight"}, {"house": "loose"}, {"house": "solid"},
    ]})
    assert sorted(result["places"]) == list(range(6))
    fast, slow, broken = result["stats"][:3]
    assert fast["late"] == fast["errors"] == 0
    assert slow["late"] > 0 and broken["errors"] > 0


@pytest.mark.skipif(os.getuid() != 0, reason="the sandbox applies only as root, as in the runner container")
def test_bots_cannot_reach_each_other():
    probe = """import os, socket, fcntl
tries = [lambda: socket.socket(), lambda: open('/tmp/x', 'w'), lambda: os.mkdir('/tmp/d'),
         lambda: os.mkfifo('/tmp/f'), lambda: fcntl.flock(open('/etc/hostname'), fcntl.LOCK_EX),
         lambda: open('/proc/self/comm', 'w')]
def blocked(f):
    try:
        f()
    except OSError:
        return True
    return False
OK = all(blocked(f) for f in tries)
class Bot:
    def act(self, state):
        assert OK, [blocked(f) for f in tries]
        return ('call',) if 'call' in state['legal'] else ('check',)
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("bot.py", probe)
    result = run_game({"seed": 2, "bots": [{"code": base64.b64encode(buffer.getvalue()).decode()}] + [{"house": "tight"}] * 5})
    assert result["stats"][0]["errors"] == 0 and result["stats"][0]["decisions"] > 0
