import io
import json
import os
import resource
import select
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from time import monotonic

from .agent import WALL

HOST = Path(__file__).with_name("host.py")
STARTUP = 5.0
MAX_UNZIPPED = 50 << 20
MEMORY = 512 << 20
CPU_SECONDS = 120


def unpack(code, directory, uid):
    archive = zipfile.ZipFile(io.BytesIO(code))
    if sum(i.file_size for i in archive.infolist()) > MAX_UNZIPPED:
        raise ValueError("bot too large")
    archive.extractall(directory)
    if os.getuid() == 0:
        # Root owns the files; the bot's group may read them; nobody else, and the bot cannot write.
        for path in [directory, *directory.rglob("*")]:
            os.chown(path, 0, uid)
            path.chmod(0o750 if path.is_dir() else 0o640)


def read_only_copy(source, directory):
    """The bot's folder as pb test runs it: a copy the bot cannot write to, as on the servers."""
    shutil.copytree(source, directory, ignore=shutil.ignore_patterns(".*", "__pycache__"))
    for path in sorted(directory.rglob("*"), reverse=True) + [directory]:
        path.chmod(0o555 if path.is_dir() else 0o444)


def confine(uid):
    """Server (root): own user, memory/CPU/process limits, no file writes. Locally: no file writes."""
    def apply():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        if os.getuid() == 0 and uid is not None:
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
            resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
            resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
            os.setgroups([])
            os.setgid(uid)
            os.setuid(uid)
    return apply


class ProcessBot:
    """A bot in its own process and user; act() never waits longer than the wall limit."""

    def __init__(self, directory, uid=None, limit=WALL, stderr=subprocess.DEVNULL):
        self.limit = limit
        self.id = 0
        self.buffer = b""
        self.proc = subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", str(HOST)], cwd=directory, env={},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            preexec_fn=confine(uid),
        )
        os.set_blocking(self.proc.stdin.fileno(), False)
        self.alive = self.read(monotonic() + STARTUP) == b"ready"
        self.startup_error = None if self.alive else self.stderr_text()

    def stderr_text(self):
        """What the bot printed before failing to start (only when stderr is a pipe)."""
        if not self.proc.stderr:
            return None
        if self.proc.poll() is None:  # still loading after STARTUP: stop it
            os.killpg(self.proc.pid, 9)
        self.proc.wait()
        return self.proc.stderr.read().decode(errors="replace").strip() or f"bot.py did not start within {STARTUP:.0f} s"

    def act(self, state):
        if not self.alive:
            raise RuntimeError(self.startup_error or "bot did not start or has exited")
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
