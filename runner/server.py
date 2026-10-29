import base64
import subprocess
import json
import random
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import TCPServer

from pokerbots_cli import engine
from pokerbots_cli.agent import Agent
from pokerbots_cli.house import HOUSE as STYLES
from pokerbots_cli.sandbox import ProcessBot, unpack

HOUSE = {**STYLES, "caller": STYLES["loose"], "raiser": STYLES["solid"]}  # old names for games queued before the change
FIRST_UID = 10000
STARTUP_ERROR_CHARS = 2000


def sandboxed(code, directory, uid):
    directory.mkdir()
    unpack(code, directory, uid)
    return ProcessBot(directory, uid, stderr=subprocess.PIPE)


def run_game(spec):
    rng = random.Random(spec["seed"])
    with tempfile.TemporaryDirectory() as root:
        Path(root).chmod(0o711)
        bots = [
            HOUSE[b["house"]]() if "house" in b
            else sandboxed(base64.b64decode(b["code"]), Path(root) / str(i), FIRST_UID + i)
            for i, b in enumerate(spec["bots"])
        ]
        agents = [Agent(b) for b in bots]
        try:
            result = engine.play(agents, rng, names=spec.get("names"))
        finally:
            for b in bots:
                if isinstance(b, ProcessBot):
                    b.close()
    return {
        "places": result.places,
        "hands": result.hands,
        "history": result.history,
        "stats": [{
            "decisions": a.decisions, "late": a.late, "errors": a.errors, "slowest_ms": round(a.slowest * 1000, 2),
            "startup_error": (getattr(a.bot, "startup_error", None) or "")[-STARTUP_ERROR_CHARS:] or None,
        } for a in agents],
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


class Server(HTTPServer):
    # HTTPServer resolves the FQDN on bind; Cloudflare's container hostnames are too long for that.
    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name, self.server_port = "runner", self.server_address[1]


if __name__ == "__main__":
    Server(("0.0.0.0", 8080), Handler).serve_forever()
