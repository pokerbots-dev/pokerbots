import json
import sys
import traceback

sys.path.insert(0, ".")
out, sys.stdout = sys.stdout, sys.stderr

from bot import Bot  # noqa: E402

bot = Bot()
out.write("ready\n")
out.flush()
for line in sys.stdin:
    request = json.loads(line)
    try:
        reply = {"id": request["id"], "action": bot.act(request["state"])}
    except Exception:
        reply = {"id": request["id"], "error": traceback.format_exc(limit=5)}
    out.write(json.dumps(reply) + "\n")
    out.flush()
