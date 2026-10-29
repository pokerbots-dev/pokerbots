import base64
import io
import zipfile

from server import run_game


def bot(body):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("bot.py", "import time\nclass Bot:\n    def act(self, state):\n" + body)
    return {"code": base64.b64encode(buffer.getvalue()).decode()}


def test_game_with_sandboxed_bots():
    result = run_game({"seed": 1, "bots": [
        bot("        return ('call',) if 'call' in state['legal'] else ('check',)\n"),
        bot("        time.sleep(0.05)\n"),
        bot("        1 / 0\n"),
        {"house": "caller"}, {"house": "raiser"}, {"house": "caller"},
    ]})
    assert sorted(result["places"]) == list(range(6))
    fast, slow, broken = result["stats"][:3]
    assert fast["late"] == fast["errors"] == 0
    assert slow["late"] > 0 and broken["errors"] > 0
