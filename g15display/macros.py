"""Local, platform-tagged keyboard macros. No global listener in this module."""

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading

MAX_EVENTS, MAX_SECONDS = 500, 60


@dataclass(frozen=True)
class Stroke:
    kind: str
    code: int
    flags: int = 0
    delay: float = 0

    def validate(self):
        if self.kind not in ("down", "up", "flags"):
            raise ValueError("Unbekanntes Tastenereignis")
        if type(self.code) is not int or not 0 <= self.code <= 255:
            raise ValueError("Ungültiger Tastencode")
        if type(self.flags) is not int or not 0 <= self.flags < 2**64:
            raise ValueError("Ungültige Zusatztasten")
        if not isinstance(self.delay, (int, float)) or not math.isfinite(self.delay) or not 0 <= self.delay <= MAX_SECONDS:
            raise ValueError("Ungültige Verzögerung")
        return self


@dataclass(frozen=True)
class Macro:
    name: str
    events: tuple[Stroke, ...]
    platform: str = sys.platform

    def validate(self):
        if not isinstance(self.name, str) or len(self.name) > 100:
            raise ValueError("Ungültiger Makroname")
        if not 1 <= len(self.events) <= MAX_EVENTS:
            raise ValueError("Ein Makro braucht 1 bis 500 Tastenereignisse")
        for event in self.events:
            event.validate()
        if sum(event.delay for event in self.events) > MAX_SECONDS:
            raise ValueError("Ein Makro darf höchstens 60 Sekunden dauern")
        if self.platform not in ("darwin", "win32", "linux"):
            raise ValueError("Unbekanntes Makroformat")
        return self


def binding_key(bank, key):
    if bank not in ("M1", "M2", "M3") or key not in {f"G{i}" for i in range(1, 19)}:
        raise ValueError("Bitte M1–M3 und G1–G18 auswählen")
    return f"{bank}:{key}"


class MacroStore:
    def __init__(self, path=None):
        if path is None:
            base = Path(os.environ.get("APPDATA", Path.home())) if sys.platform == "win32" else Path.home() / "Library" / "Application Support"
            path = base / "G15 Display" / "macros.json"
        self.path = Path(path)
        self.mutex = threading.RLock()
        self.bindings = {}
        self.error = ""
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                if data.get("version") != 1:
                    raise ValueError("Unbekannte Profilversion")
                for key, item in data["bindings"].items():
                    bank, button = key.split(":")
                    binding_key(bank, button)
                    self.bindings[key] = Macro(item["name"], tuple(Stroke(**e) for e in item["events"]), item["platform"]).validate()
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            self.bindings = {}
            self.error = "Die Makrodatei lässt sich nicht lesen. Sie wird nicht überschrieben."

    def get(self, bank, key):
        with self.mutex:
            return self.bindings.get(binding_key(bank, key))

    def set(self, bank, key, macro):
        target = binding_key(bank, key)
        if macro is not None:
            macro.validate()
        with self.mutex:
            if self.error:
                raise ValueError(self.error)
            updated = dict(self.bindings)
            if macro is None:
                updated.pop(target, None)
            else:
                updated[target] = macro
            data = {"version": 1, "bindings": {k: {"name": m.name, "platform": m.platform,
                    "events": [asdict(event) for event in m.events]} for k, m in updated.items()}}
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                                 prefix=".macro-", delete=False) as stream:
                    temporary = stream.name
                    json.dump(data, stream, ensure_ascii=False, indent=2)
                os.replace(temporary, self.path)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
            self.bindings = updated


class MacroPlayer:
    def __init__(self, post):
        self.post = post
        self.cancel_event = threading.Event()
        self.thread = None
        self.error = ""
        self.mutex = threading.Lock()

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def play(self, macro):
        macro.validate()
        if macro.platform != sys.platform:
            raise ValueError("Dieses Makro wurde für ein anderes Betriebssystem aufgenommen")
        with self.mutex:
            if self.busy:
                return False
            self.cancel_event.clear()
            self.error = ""
            self.thread = threading.Thread(target=self._run, args=(macro,), name="g15-macro", daemon=True)
            self.thread.start()
            return True

    def cancel(self):
        self.cancel_event.set()

    def _run(self, macro):
        held = {}
        try:
            for event in macro.events:
                if self.cancel_event.wait(event.delay):
                    break
                self.post(event)
                if event.kind == "down":
                    held[event.code] = event
                elif event.kind == "up":
                    held.pop(event.code, None)
                elif event.code in held:
                    held.pop(event.code)
                else:
                    held[event.code] = event
        except Exception:
            self.error = "Makro-Wiedergabe fehlgeschlagen"
        finally:
            for code, previous in reversed(list(held.items())):
                try:
                    self.post(Stroke("flags" if previous.kind == "flags" else "up", code, 0))
                except Exception:
                    self.error = "Makro-Wiedergabe unterbrochen"
