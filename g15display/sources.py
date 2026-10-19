"""Read-only data sources. Slow calls run outside the display's event loop."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import sqlite3
import subprocess
import threading
import time

import psutil


class SourceError(RuntimeError):
    pass


class CodexClient:
    """Own local stdio connection, exclusively account/rateLimits/read.

    Uses the existing Codex login. Does not start/resume/modify any chat.
    This process cannot observe another app-server's in-memory task states.
    """

    def __init__(self):
        self.process = None
        self.reader = None
        self.messages = queue.Queue()
        self.sequence = 0

    def _read(self, process, messages):
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                continue
        messages.put(None)

    def _call(self, method, params=None):
        self.sequence += 1
        request_id = self.sequence
        try:
            self.process.stdin.write(json.dumps({"id": request_id, "method": method,
                                                "params": params or {}}) + "\n")
            self.process.stdin.flush()
            deadline = time.monotonic() + 8
            while True:
                msg = self.messages.get(timeout=max(0.001, deadline - time.monotonic()))
                if msg is None:
                    raise SourceError("Codex-Verbindung beendet")
                if msg.get("id") == request_id:
                    if "error" in msg:
                        raise SourceError("Codex-Abfrage nicht verfuegbar")
                    return msg.get("result", {})
                if time.monotonic() >= deadline:
                    raise SourceError("Codex antwortet nicht")
        except (queue.Empty, BrokenPipeError, OSError, ValueError) as exc:
            raise SourceError("Codex nicht erreichbar") from exc

    def limits(self):
        try:
            if self.process is None or self.process.poll() is not None:
                executable = shutil.which("codex")
                if not executable:
                    bundled = (
                        Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"),
                        Path("/Applications/Codex.app/Contents/Resources/codex"),
                    )
                    executable = next((str(p) for p in bundled if p.is_file() and os.access(p, os.X_OK)), None)
                if not executable:
                    raise SourceError("Codex CLI fehlt")
                self.messages = queue.Queue()
                self.process = subprocess.Popen(
                    [executable, "app-server", "--stdio"], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                self.reader = threading.Thread(target=self._read, args=(self.process, self.messages), daemon=True)
                self.reader.start()
                self._call("initialize", {"clientInfo": {"name": "g15display", "version": "1.1.0"}})
                self.process.stdin.write('{"method":"initialized","params":{}}\n')
                self.process.stdin.flush()
            result = self._call("account/rateLimits/read")
            buckets = result.get("rateLimitsByLimitId") or {}
            bucket = buckets.get("codex") or result.get("rateLimits") or {}
            windows = [bucket[k] for k in ("primary", "secondary") if bucket.get(k)]
            if not windows:
                raise SourceError("Keine Limitdaten verfuegbar")
            return windows
        except Exception:
            self.close()
            raise

    def close(self):
        if self.process is not None:
            process, self.process = self.process, None
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            if self.reader is not None:
                self.reader.join(timeout=1)
                self.reader = None
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()


class ActivitySource:
    """Local log-based task status; read-only, best effort, not a server subscription."""

    def __init__(self, home=None):
        self.home = Path(home or os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.sessions = {}

    def __call__(self):
        databases = list(self.home.glob("state_*.sqlite"))
        if not databases:
            raise SourceError("Keine lokalen Codex-Chats")
        database = max(databases, key=lambda p: p.stat().st_mtime)
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)) as conn:
            columns = {r[1] for r in conn.execute("pragma table_info(threads)")}
            name = "COALESCE(NULLIF(name, ''), title)" if "name" in columns else "title"
            rows = conn.execute(
                f"SELECT id, {name}, rollout_path FROM threads WHERE archived=0 "
                "AND updated_at >= ? ORDER BY updated_at DESC LIMIT 32",
                (int(time.time()) - 86400,)).fetchall()
        current_ids = {row[0] for row in rows}
        self.sessions = {k: v for k, v in self.sessions.items() if k in current_ids}
        active, unknown, complete = [], [], []
        for thread_id, title, path in rows:
            if not path:
                continue
            file = Path(path)
            try:
                stat = file.stat()
                state = self.sessions.setdefault(thread_id, dict(offset=0, active=None, stamp=0))
                if stat.st_size < state["offset"]:
                    state.update(offset=0, active=None, stamp=0)
                with file.open("rb") as stream:
                    stream.seek(state["offset"])
                    while True:
                        position = stream.tell()
                        line = stream.readline()
                        if not line or not line.endswith(b"\n"):
                            state["offset"] = position
                            break
                        state["offset"] = stream.tell()
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if event.get("timestamp"):
                            try:
                                state["stamp"] = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).timestamp()
                            except ValueError:
                                pass
                        if event.get("type") != "event_msg":
                            continue
                        kind = event.get("payload", {}).get("type")
                        if kind == "task_started":
                            state["active"] = True
                        elif kind in ("task_complete", "turn_aborted"):
                            state["active"] = False
                item = {"name": title or "", "stamp": state["stamp"]}
                if state["active"] is True:
                    (active if time.time() - state["stamp"] < 600 else unknown).append(item)
                elif state["active"] is False:
                    complete.append(item)
            except OSError:
                continue
        return {"active": active, "unknown": unknown, "complete": complete, "scope": "Lokal / letzte 24h"}


class NetworkSource:
    def __init__(self):
        self.previous = None

    def __call__(self):
        result = subprocess.run(["/sbin/route", "-n", "get", "default"], capture_output=True,
                                text=True, timeout=2)
        interface = next((line.split(":", 1)[1].strip() for line in result.stdout.splitlines()
                          if line.strip().startswith("interface:")), None)
        if not interface:
            self.previous = None
            raise SourceError("Keine Standardverbindung")
        counters = psutil.net_io_counters(pernic=True).get(interface)
        if counters is None:
            raise SourceError("Keine Netzwerkzaehler")
        now = time.monotonic()
        down = up = None
        if self.previous and self.previous[0] == interface:
            _, stamp, received, sent = self.previous
            elapsed = now - stamp
            if elapsed > 0 and counters.bytes_recv >= received and counters.bytes_sent >= sent:
                down = (counters.bytes_recv - received) / elapsed
                up = (counters.bytes_sent - sent) / elapsed
        self.previous = (interface, now, counters.bytes_recv, counters.bytes_sent)
        ip = next((a.address for a in psutil.net_if_addrs().get(interface, []) if a.family == socket.AF_INET), "Keine IPv4")
        return {"interface": interface, "ip": ip, "down": down, "up": up}


class MusicSource:
    APPS = (("Spotify", "com.spotify.client"), ("Music", "com.apple.Music"))

    def __init__(self):
        self.selected = None
        self.blocked_until = {}
        self.problems = {}

    def _running(self):
        names = {p.info["name"] for p in psutil.process_iter(["name"])}
        return [(name, app_id) for name, app_id in self.APPS if name in names]

    def __call__(self):
        available = []
        problems = []
        for name, app_id in self._running():
            if time.monotonic() < self.blocked_until.get(app_id, 0):
                problems.append(self.problems.get(app_id, "Player nicht erreichbar"))
                continue
            # Unit separator avoids ambiguity in titles/artists containing newlines.
            script = f'''tell application id "{app_id}"
if player state is stopped then return "stopped"
return (player state as text) & (character id 31) & (name of current track) & (character id 31) & (artist of current track) & (character id 31) & (player position as text) & (character id 31) & (duration of current track as text)
end tell'''
            try:
                result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=10)
            except subprocess.TimeoutExpired:
                self.blocked_until[app_id] = time.monotonic() + 30
                self.problems[app_id] = "Player antwortet nicht"
                problems.append(self.problems[app_id])
                continue
            if result.returncode:
                self.blocked_until[app_id] = time.monotonic() + 30
                self.problems[app_id] = "Musik-Zugriff erlauben" if "-1743" in result.stderr else "Player-Abfrage fehlgeschlagen"
                problems.append(self.problems[app_id])
                continue
            self.problems.pop(app_id, None)
            parts = result.stdout.strip().split("\x1f")
            if len(parts) != 5:
                continue
            state, title, artist, position, duration = parts
            try:
                position = float(position.replace(",", "."))
                duration = float(duration.replace(",", ".")) / (1000 if name == "Spotify" else 1)
            except ValueError:
                continue
            available.append(dict(player=name, app_id=app_id, state=state, title=title,
                                  artist=artist, position=position, duration=duration))
        available.sort(key=lambda item: item["state"] != "playing")
        if not available:
            self.selected = None
            if problems:
                raise SourceError(problems[0])
            return {"state": "stopped", "title": "Keine Wiedergabe", "artist": "Spotify / Apple Music"}
        self.selected = available[0]["app_id"]
        return available[0]

    def toggle(self):
        if self.selected is None:
            return
        # Called only by a deliberate physical button press, never while polling.
        result = subprocess.run(["/usr/bin/osascript", "-e",
                                 f'tell application id "{self.selected}" to playpause'],
                                capture_output=True, text=True, timeout=3)
        if result.returncode:
            raise SourceError("Player-Steuerung verweigert")


@dataclass
class Snapshot:
    value: object = None
    error: str = "Wird geladen ..."
    stamp: float = 0


class Sources:
    def __init__(self):
        self.codex = CodexClient()
        self.music = MusicSource()
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="g15-data")
        self.jobs = {"limits": (self.codex.limits, 60), "activity": (ActivitySource(), 3),
                     "network": (NetworkSource(), 1), "music": (self.music, 3)}
        self.snapshots = {name: Snapshot() for name in self.jobs}
        self.futures = {}
        self.next = {name: 0 for name in self.jobs}
        self.action = None
        self.action_requested = False

    def poll(self):
        now = time.monotonic()
        if self.action is not None and self.action.done():
            try:
                self.action.result()
            except Exception:
                self.snapshots["music"] = Snapshot(error="Player-Steuerung fehlgeschlagen")
            self.action = None
            self.next["music"] = now + 1
        for name, (function, interval) in self.jobs.items():
            future = self.futures.get(name)
            if future is not None and future.done():
                try:
                    self.snapshots[name] = Snapshot(value=future.result(), error="", stamp=time.time())
                except Exception as exc:
                    message = str(exc) if isinstance(exc, SourceError) else "Datenquelle nicht verfuegbar"
                    self.snapshots[name] = Snapshot(error=message)
                del self.futures[name]
                self.next[name] = now + interval
            # Music polling and playback controls share one selected player.
            if name == "music":
                if self.action_requested and self.action is None and name not in self.futures:
                    self.action_requested = False
                    self.action = self.pool.submit(self.music.toggle)
                if self.action is not None:
                    continue
            if name not in self.futures and now >= self.next[name]:
                self.futures[name] = self.pool.submit(function)

    def toggle_music(self):
        self.action_requested = True

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.codex.close()
