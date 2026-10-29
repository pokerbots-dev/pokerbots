import io
import json
import os
import resource
import select
import subprocess
import sys
import zipfile
from pathlib import Path
from time import monotonic

from pokerbots_cli.agent import WALL

HOST = Path(__file__).with_name("host.py")
STARTUP = 5.0
MAX_UNZIPPED = 10 << 20
MEMORY = 512 << 20
CPU_SECONDS = 120


def unpack(code, directory, uid):
    archive = zipfile.ZipFile(io.BytesIO(code))
    if sum(i.file_size for i in archive.infolist()) > MAX_UNZIPPED:
        raise ValueError("bot too large")
    archive.extractall(directory)
    if os.getuid() == 0:
        for path in [directory, *directory.rglob("*")]:
            os.chown(path, uid, uid)
        directory.chmod(0o700)


def confine(uid):
    def apply():
        os.setsid()
        if os.getuid() == 0:
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
            resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
            resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
            resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
            os.setgroups([])
            os.setgid(uid)
            os.setuid(uid)
    return apply


class ProcessBot:
    """A bot in its own process and user; act() never waits longer than the wall limit."""

    def __init__(self, code, directory, uid, limit=WALL):
        directory.mkdir()
        unpack(code, directory, uid)
        self.limit = limit
        self.id = 0
        self.buffer = b""
        self.proc = subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", str(HOST)], cwd=directory, env={},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            preexec_fn=confine(uid),
        )
        os.set_blocking(self.proc.stdin.fileno(), False)
        self.alive = self.read(monotonic() + STARTUP) == b"ready"

    def act(self, state):
        if not self.alive:
            raise RuntimeError("bot did not start or has exited")
        self.id += 1
        line = (json.dumps({"id": self.id, "state": state}) + "\n").encode()
        deadline = monotonic() + self.limit
        if not self.write(line, deadline):
            return self.close()
        while (raw := self.read(deadline)) is not None:
            reply = json.loads(raw)
            if reply.get("id") == self.id:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply["action"]
        return None

    def cpu(self):
        """Seconds of CPU the bot process has used, read by the kernel so the bot cannot fake it."""
        try:
            return int(Path(f"/proc/{self.proc.pid}/schedstat").read_text().split()[0]) / 1e9
        except (OSError, ValueError):
            return monotonic()

    def write(self, data, deadline):
        fd = self.proc.stdin.fileno()
        while data:
            left = deadline - monotonic()
            if left <= 0 or not select.select([], [fd], [], left)[1]:
                return False
            try:
                data = data[os.write(fd, data):]
            except (BlockingIOError, BrokenPipeError):
                return False
        return True

    def read(self, deadline):
        fd = self.proc.stdout.fileno()
        while b"\n" not in self.buffer:
            left = deadline - monotonic()
            if left <= 0 or not select.select([fd], [], [], left)[0]:
                return None
            chunk = os.read(fd, 65536)
            if not chunk:
                self.alive = False
                return None
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line

    def close(self):
        self.alive = False
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, 9)
        self.proc.wait()
