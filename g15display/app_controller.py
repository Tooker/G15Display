"""GUI-independent controller. All device and dashboard state stays on one thread."""

from dataclasses import dataclass
import logging
import os
import queue
import threading
import time

import psutil

from .dashboard import Dashboard, PAGES
from .display import G15, G15Error
from .keys import KeyEvent
from .sources import Sources
from .timers import Timer
from .i18n import normalize_language


@dataclass(frozen=True)
class Settings:
    minutes: float = 5
    work: float = 25
    rest: float = 5
    rounds: int = 4

    def validate(self):
        Timer(self.minutes, work=self.work, rest=self.rest, rounds=self.rounds)
        if any(value > 1440 for value in (self.minutes, self.work, self.rest)) or self.rounds > 50:
            raise ValueError("Maximal 1440 Minuten und 50 Runden sind möglich.")
        return self


def legacy_menu_running():
    """Older, already-running CLIs do not yet own the new device lock."""
    try:
        for process in psutil.process_iter(["pid", "name"]):
            if process.pid == os.getpid() or "python" not in (process.info["name"] or "").lower():
                continue
            try:
                args = process.cmdline()
                for index, arg in enumerate(args[:-2]):
                    if arg == "-m" and args[index + 1:index + 3] == ["g15display", "menu"]:
                        return True
            except (psutil.Error, OSError):
                continue
    except (psutil.Error, OSError):
        pass
    return False


class AppController:
    def __init__(self, settings=None, *, page="clock", sources=None, device_factory=G15,
                 legacy_check=legacy_menu_running, clock=time.monotonic, macros=None, language="de"):
        self.settings = (settings or Settings()).validate()
        self.sources = sources or Sources()
        self.dashboard = Dashboard(self.sources, page=page, minutes=self.settings.minutes,
                                   work=self.settings.work, rest=self.settings.rest,
                                   rounds=self.settings.rounds, clock=clock, language=language)
        self.device_factory, self.legacy_check, self.clock = device_factory, legacy_check, clock
        self.device = None
        self.enabled = True
        self.retry_at = 0
        self.commands = queue.Queue()
        self.stop_event = threading.Event()
        self.mutex = threading.Lock()
        self.thread = None
        self.error = "G15 wird gesucht …"
        self.revision = 0
        self.last_frame = None
        self.state = {}
        self.macros = macros
        self.bank = "M1"
        self.last_g_key = None

    def handle_key(self, event):
        if event.name in ("M1", "M2", "M3") and event.pressed:
            self.bank = event.name
        if event.name in {f"G{i}" for i in range(1, 19)}:
            if event.pressed:
                self.last_g_key = event.name
                if self.macros is not None:
                    self.macros.trigger(self.bank, event.name)
        elif event.name == "MR" and event.pressed and self.macros is not None:
            self.macros.request_stop()
        self.dashboard.handle(event)

    def start(self):
        self.thread = threading.Thread(target=self._run, name="g15-display", daemon=True)
        self.thread.start()

    def submit(self, action, value=None):
        self.commands.put((action, value))

    def snapshot(self):
        with self.mutex:
            return self.state.copy()

    def stop(self):
        self.stop_event.set()

    @property
    def alive(self):
        return self.thread is not None and self.thread.is_alive()

    def _disconnect(self):
        if self.device is not None:
            self.device.close()
            self.device = None
        self.last_frame = None

    def step(self):
        while True:
            try:
                action, value = self.commands.get_nowait()
            except queue.Empty:
                break
            if action == "enabled":
                self.enabled = bool(value)
                self.retry_at = 0
                if not self.enabled:
                    self._disconnect()
            elif action == "page" and value in PAGES:
                self.dashboard.page = PAGES.index(value)
                self.dashboard.menu = False
                self.dashboard.page_started = self.clock()
            elif action == "key":
                self.handle_key(KeyEvent(value, True))
                self.handle_key(KeyEvent(value, False))
            elif action == "language":
                self.dashboard.tr.language = normalize_language(value)
            elif action == "bank" and value in ("M1", "M2", "M3"):
                self.bank = value
            elif action == "settings":
                settings = value.validate()
                self.settings = settings
                self.dashboard.timer = Timer(settings.minutes, clock=self.clock)
                self.dashboard.pomodoro = Timer(work=settings.work, rest=settings.rest,
                                                rounds=settings.rounds, clock=self.clock)
                self.dashboard.notice_until = 0
        self.sources.poll()
        self.dashboard.tick()
        if self.enabled and self.device is None and self.clock() >= self.retry_at:
            try:
                if self.legacy_check():
                    raise G15Error("Das Terminal-Menü läuft noch. Dort mit Strg+C beenden; die App verbindet sich danach automatisch.")
                device = self.device_factory()
                device.__enter__()
                self.device = device
                self.error = ""
            except (G15Error, OSError) as exc:
                self.error = exc
                self.retry_at = self.clock() + 2
        if self.device is not None:
            try:
                for event in self.device.read_keys(timeout_ms=25):
                    self.handle_key(event)
            except (G15Error, OSError) as exc:
                self.error = exc
                self._disconnect()
                self.retry_at = self.clock() + 2
        image = self.dashboard.render()
        frame = image.tobytes()
        if self.device is not None and frame != self.last_frame:
            try:
                self.device.show(image)
                self.last_frame = frame
            except (G15Error, OSError) as exc:
                self.error = exc
                self._disconnect()
                self.retry_at = self.clock() + 2
        with self.mutex:
            if not self.state or self.state["image"].tobytes() != frame:
                self.revision += 1
            self.state = dict(image=image, revision=self.revision, connected=self.device is not None,
                              enabled=self.enabled, error=self.dashboard.tr(self.error), page=self.dashboard.page,
                              menu=self.dashboard.menu,
                              bank=self.bank, last_g_key=self.last_g_key, language=self.dashboard.tr.language,
                              health={name: snapshot.error for name, snapshot in self.sources.snapshots.items()})

    def _run(self):
        try:
            while not self.stop_event.is_set():
                self.step()
                self.stop_event.wait(0.1)
        except Exception:
            logging.exception("G15 controller stopped unexpectedly")
            with self.mutex:
                self.state.update(connected=False, error="Die Display-Verbindung wurde beendet. Bitte die App neu starten.")
        finally:
            try:
                self._disconnect()
            finally:
                self.sources.close()
