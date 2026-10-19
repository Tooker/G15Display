"""Explicit, device-specific G15 typing-key test. No text or event log is saved."""

from dataclasses import dataclass
import threading
import time

from .display import G15Error, _hid
from .i18n import Message

# Read from the attached 046d:c221 interface 0. The exact known descriptor
# prevents an unrelated/changed report layout from producing false diagnoses.
G15_TYPING_DESCRIPTOR = bytes.fromhex(
    "05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 "
    "81 02 95 01 75 08 81 01 95 05 75 01 05 08 19 01 29 05 91 02 "
    "95 01 75 03 91 01 95 06 75 08 15 00 26 97 00 05 07 19 00 "
    "29 97 81 00 c0"
)

# USB usages identify physical key positions, not generated characters.
KEYS = [(0x2a, "Rücktaste ⌫"), (0x4c, "Entf ⌦"), (0x28, "Enter"),
        (0x2c, "Leertaste"), (0x29, "Esc"), (0x2b, "Tab")]
KEYS += [(4 + i, char if char not in "YZ" else {"Y": "Y (US) / Z (DE)", "Z": "Z (US) / Y (DE)"}[char])
         for i, char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")]
KEYS += [(0x1e + i, char) for i, char in enumerate("1234567890")]
KEYS += [(0x3a + i, f"F{i + 1}") for i in range(12)]
KEYS += [(0x4f, "→"), (0x50, "←"), (0x51, "↓"), (0x52, "↑"),
         (0xe0, "Ctrl L"), (0xe1, "Shift L"), (0xe2, "Alt L"), (0xe3, "GUI L"),
         (0xe4, "Ctrl R"), (0xe5, "Shift R"), (0xe6, "Alt R"), (0xe7, "GUI R")]


class ReportProblem(ValueError):
    pass


def decode_typing_report(report):
    """Unnumbered eight-byte boot report: modifiers, reserved, six usages."""
    if len(report) != 8 or report[1] != 0:
        raise ReportProblem("Ungültige Tastaturmeldung; bitte Test wiederholen.")
    if any(code in (1, 2, 3) for code in report[2:]):
        raise ReportProblem("Tastatur meldet Rollover/Fehler; bitte einzeln testen.")
    if any(code > 0x97 for code in report[2:]):
        raise ReportProblem("Ungültige Tastaturmeldung; bitte Test wiederholen.")
    keys = {code for code in report[2:] if code}
    keys.update(0xe0 + bit for bit in range(8) if report[0] & (1 << bit))
    return frozenset(keys)


@dataclass
class KeyMetrics:
    target: int = 0x2a
    presses: int = 0
    releases: int = 0
    rapid_represses: int = 0
    max_hold: float = 0
    held_since: float | None = None
    last_release: float | None = None
    reports: int = 0
    problems: int = 0
    resync: bool = False
    seen: bool = False

    def update(self, report, now):
        try:
            keys = decode_typing_report(report)
        except ReportProblem:
            self.problems += 1
            self.resync = True
            self.held_since = self.last_release = None
            raise
        self.reports += 1
        self.seen = True
        down = self.target in keys
        if self.resync:
            # Discard edges across a gap; otherwise rollover would look like
            # a release/repress and manufacture a bounce or missing-release fault.
            self.held_since = now if down else None
            self.last_release = None
            self.resync = False
            return
        if down and self.held_since is None:
            self.presses += 1
            if self.last_release is not None and 0 <= now - self.last_release <= 0.05:
                self.rapid_represses += 1
            self.held_since = now
        elif not down and self.held_since is not None:
            self.releases += 1
            self.max_hold = max(self.max_hold, now - self.held_since)
            self.held_since = None
            self.last_release = now

    def snapshot(self, now):
        duration = max(0, now - self.held_since) if self.held_since is not None else 0
        return dict(target=self.target, presses=self.presses, releases=self.releases,
                    rapid=self.rapid_represses, held=self.held_since is not None,
                    duration=duration, max_hold=max(self.max_hold, duration),
                    seen=self.seen, problems=self.problems, uncertain=self.resync)


class TypingKeyboard:
    """Shared, read-only access to the physical G15 typing interface only."""
    def __init__(self):
        self.device = None

    def __enter__(self):
        hid = _hid()  # Includes hid_darwin_set_open_exclusive(0).
        devices = {d["path"]: d for d in hid.enumerate(0x046d, 0xc221)
                   if d.get("vendor_id") == 0x046d and d.get("product_id") == 0xc221
                   and d.get("interface_number") == 0 and d.get("usage_page") == 1 and d.get("usage") == 6}
        if len(devices) != 1:
            raise G15Error("Bitte genau eine G15-v1-Tastatur anschließen (046d:c221).")
        self.device = hid.device()
        try:
            self.device.open_path(next(iter(devices)))
            if bytes(self.device.get_report_descriptor()) != G15_TYPING_DESCRIPTOR:
                raise G15Error("Unbekanntes Tastaturformat; keine verlässliche Messung möglich.")
        except OSError as exc:
            self.close()
            raise G15Error("Tastaturzugriff verweigert. Eingabeüberwachung prüfen und App neu starten.") from exc
        except Exception:
            self.close()
            raise
        return self

    def read(self):
        return bytes(self.device.read(64, 50))

    def close(self):
        if self.device is not None:
            device, self.device = self.device, None
            device.close()

    def __exit__(self, *_):
        self.close()


class KeyboardTest:
    def __init__(self, *, device_factory=TypingKeyboard, clock=time.monotonic):
        self.device_factory, self.clock = device_factory, clock
        self.mutex = threading.RLock()
        self.thread = None
        self.stop_event = threading.Event()
        self.metrics = KeyMetrics()
        self.status = "Test bereit. Alle Tasten loslassen und Start drücken."
        self.stopped_at = clock()
        self.connected = False
        self.expected = None
        self.session_problem = False

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def reset(self, target=0x2a):
        self.stop()
        if self.busy:
            return
        with self.mutex:
            self.metrics = KeyMetrics(target=target)
            self.expected = None
            self.session_problem = False
            self.stopped_at = self.clock()
            self.status = "Test bereit. Alle Tasten loslassen und Start drücken."

    def start(self, target=0x2a):
        if self.busy:
            return
        self.reset(target)
        self.stop_event.clear()
        self.status = "Normale G15-Tastatur wird geöffnet …"
        self.thread = threading.Thread(target=self._run, name="g15-keyboard-test", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=1)

    def finish(self, expected=10):
        self.stop()
        with self.mutex:
            self.expected = expected

    def _run(self):
        timed_out = False
        started = self.clock()
        try:
            with self.device_factory() as device:
                with self.mutex:
                    self.connected = True
                    self.status = "Messung aktiv. Prüftaste zehnmal einzeln drücken und loslassen."
                while not self.stop_event.is_set():
                    if self.clock() - started >= 120:
                        with self.mutex:
                            self.status = "Messung nach zwei Minuten automatisch gestoppt."
                        timed_out = True
                        break
                    report = device.read()
                    if not report:  # A timeout is not a release.
                        continue
                    with self.mutex:
                        try:
                            self.metrics.update(report, self.clock())
                        except ReportProblem as exc:
                            self.status = str(exc)
                            self.session_problem = True
        except Exception as exc:
            with self.mutex:
                self.session_problem = True
                self.status = exc if isinstance(exc, G15Error) else "Tastaturverbindung unterbrochen; bitte Test wiederholen."
                self.metrics.resync = True
        finally:
            with self.mutex:
                self.connected = False
                self.stopped_at = self.clock()
                if not self.session_problem and not timed_out:
                    self.status = "Messung gestoppt. Angezeigt wird der letzte empfangene Zustand."

    def snapshot(self):
        with self.mutex:
            running = self.busy
            data = self.metrics.snapshot(self.clock() if running else self.stopped_at)
            data.update(running=running, connected=self.connected, status=self.status,
                        expected=self.expected, session_problem=self.session_problem)
            return data


def result_message(data):
    """An expected count is a human reference, never inferred from silence."""
    if data["session_problem"] or data["problems"] or data["uncertain"]:
        return "Messung unvollständig; daraus lässt sich kein Tastendefekt ableiten."
    if data["expected"] is None:
        return "Erst zehnmal drücken, dann mit der Schaltfläche auswerten."
    if not data["seen"]:
        return "Keine Tastaturmeldung empfangen. Ursache noch unklar; Zugriff/Verbindung prüfen."
    expected, presses = data["expected"], data["presses"]
    if data["held"] or data["releases"] != presses:
        return "Loslassen fehlt. Falls die Taste physisch losgelassen ist, wurde kein passender USB-Zustand empfangen."
    if presses == expected:
        return "Zehn vollständige Betätigungen empfangen. Das schließt sporadische Aussetzer nicht aus."
    return Message("Soll: {expected}, empfangen: {presses}. Bei genau zehn Betätigungen besteht eine Abweichung; Ursache noch offen.", dict(expected=expected, presses=presses))
