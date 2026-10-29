import base64
import json
import random
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from pokerbots_cli import engine
from pokerbots_cli.agent import Agent
from pokerbots_cli.house import Caller, Raiser
from sandbox import ProcessBot

HOUSE = {"caller": Caller, "raiser": Raiser}
FIRST_UID = 10000


def run_game(spec):
    rng = random.Random(spec["seed"])
    with tempfile.TemporaryDirectory() as root:
        Path(root).chmod(0o711)
        bots = [
            HOUSE[b["house"]]() if "house" in b
            else ProcessBot(base64.b64decode(b["code"]), Path(root) / str(i), FIRST_UID + i)
            for i, b in enumerate(spec["bots"])
        ]
        agents = [Agent(b) for b in bots]
        try:
            result = engine.play(agents, rng)
        finally:
            for b in bots:
                if isinstance(b, ProcessBot):
                    b.close()
    return {
        "places": result.places,
        "hands": result.hands,
        "stats": [{"late": a.late, "errors": a.errors, "slowest_ms": round(a.slowest * 1000, 2)} for a in agents],
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        spec = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body = json.dumps(run_game(spec)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
