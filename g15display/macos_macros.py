"""Explicitly armed, listen-only keyboard recording and tagged playback on macOS."""

import threading
import time

import CoreFoundation as CF
import Quartz as Q

from .macros import Macro, MacroPlayer, MacroStore, MAX_EVENTS, MAX_SECONDS, Stroke, binding_key

EVENT_TAG = 0x4731354D


def post_stroke(stroke):
    if not Q.CGPreflightPostEventAccess():
        raise PermissionError("Wiedergabe braucht die Bedienungshilfen-Freigabe")
    event = Q.CGEventCreateKeyboardEvent(None, stroke.code, stroke.kind != "up")
    if stroke.kind == "flags":
        Q.CGEventSetType(event, Q.kCGEventFlagsChanged)
    Q.CGEventSetFlags(event, stroke.flags)
    Q.CGEventSetIntegerValueField(event, Q.kCGEventSourceUserData, EVENT_TAG)
    Q.CGEventPost(Q.kCGHIDEventTap, event)


class MacMacroService:
    def __init__(self, store=None, clock=time.monotonic):
        self.store = store or MacroStore()
        self.clock = clock
        self.player = MacroPlayer(post_stroke)
        self.mutex = threading.RLock()
        self.tap = self.source = None
        self.target = None
        self.events = []
        self.started = self.previous = 0
        self.countdown = None
        self.stop_requested = False
        self.failed = False
        self.message = self.store.error or "G-Taste wählen und Aufnahme starten."
        self.play_pending = None
        self.closed = False

    def arm(self, bank, key, name):
        binding_key(bank, key)
        with self.mutex:
            if self.closed or self.target or self.player.busy:
                return
            if self.store.error:
                self.message = self.store.error
                return
            if not Q.CGPreflightListenEventAccess():
                Q.CGRequestListenEventAccess()
                self.message = "G15 Display unter Eingabeüberwachung erlauben; dann erneut aufnehmen."
                return
            self.target = (bank, key, name[:100] or f"{bank}/{key}")
            self.player.error = ""
            self.events = []
            self.countdown = self.clock() + 3
            self.stop_requested = self.failed = False
            self.message = "Aufnahme beginnt in 3 Sekunden …"

    def _start(self):
        mask = sum(1 << kind for kind in (Q.kCGEventKeyDown, Q.kCGEventKeyUp, Q.kCGEventFlagsChanged))
        self.tap = Q.CGEventTapCreate(Q.kCGSessionEventTap, Q.kCGHeadInsertEventTap,
                                    Q.kCGEventTapOptionListenOnly, mask, self._callback, None)
        if self.tap is None:
            self.target = self.countdown = None
            self.message = "Tastaturaufnahme nicht verfügbar. Eingabeüberwachung prüfen."
            return
        self.source = CF.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        CF.CFRunLoopAddSource(CF.CFRunLoopGetMain(), self.source, CF.kCFRunLoopCommonModes)
        Q.CGEventTapEnable(self.tap, True)
        self.started = self.previous = self.clock()
        self.countdown = None
        self.message = "AUFNAHME AKTIV – mit Stoppen oder MR beenden."

    def _callback(self, proxy, kind, event, context):
        with self.mutex:
            if kind in (Q.kCGEventTapDisabledByTimeout, Q.kCGEventTapDisabledByUserInput):
                self.failed = self.stop_requested = True
                return event
            if self.target is None or self.countdown is not None or self.stop_requested:
                return event
            if Q.CGEventGetIntegerValueField(event, Q.kCGEventSourceUserData) == EVENT_TAG:
                return event
            now = self.clock()
            if now - self.started >= MAX_SECONDS or len(self.events) >= MAX_EVENTS:
                self.stop_requested = True
                return event
            kinds = {Q.kCGEventKeyDown: "down", Q.kCGEventKeyUp: "up", Q.kCGEventFlagsChanged: "flags"}
            if kind in kinds:
                code = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode)
                delay = 0 if not self.events else max(0, now - self.previous)
                self.events.append(Stroke(kinds[kind], int(code), int(Q.CGEventGetFlags(event)), delay))
                self.previous = now
                if len(self.events) >= MAX_EVENTS:
                    self.stop_requested = True
        return event

    def stop(self, save=True):
        # Called on the main run loop, including a stop requested by the USB thread.
        with self.mutex:
            if self.tap is not None:
                Q.CGEventTapEnable(self.tap, False)
                CF.CFRunLoopRemoveSource(CF.CFRunLoopGetMain(), self.source, CF.kCFRunLoopCommonModes)
                CF.CFMachPortInvalidate(self.tap)
            self.tap = self.source = None
            target, events = self.target, tuple(self.events)
            self.target = self.countdown = None
            self.stop_requested = False
            if self.failed:
                self.message = "Aufnahme unterbrochen. Das bisherige Makro bleibt erhalten."
            elif save and target and events:
                try:
                    bank, key, name = target
                    self.store.set(bank, key, Macro(name, events).validate())
                    self.message = f"{bank}/{key}: {len(events)} Ereignisse gespeichert."
                except (ValueError, OSError) as exc:
                    self.message = str(exc)
            elif target:
                self.message = "Aufnahme verworfen; das bisherige Makro bleibt erhalten."

    def request_stop(self):
        with self.mutex:
            if self.target:
                self.stop_requested = True
            self.player.cancel()
            self.play_pending = None

    def trigger(self, bank, key):
        with self.mutex:
            if self.closed or self.target or self.play_pending or self.player.busy:
                return
            macro = self.store.get(bank, key)
            if macro is None:
                return
            if not Q.CGPreflightPostEventAccess():
                self.message = "Für Makros die Bedienungshilfen-Freigabe für G15 Display erteilen."
                return
            try:
                self.player.play(macro)
                self.message = f"Wiedergabe {bank}/{key} gestartet."
            except ValueError as exc:
                self.message = str(exc)

    def test(self, bank, key):
        with self.mutex:
            if self.closed or self.target or self.player.busy:
                return
            if self.store.get(bank, key) is None:
                self.message = "Für diese G-Taste ist noch kein Makro gespeichert."
                return
            if not Q.CGPreflightPostEventAccess():
                Q.CGRequestPostEventAccess()
                self.message = "G15 Display unter Bedienungshilfen erlauben; dann erneut testen."
                return
            self.play_pending = (self.clock() + 3, bank, key)
            self.message = "Wiedergabe in 3 Sekunden – Zielprogramm auswählen."

    def tick(self):
        with self.mutex:
            if self.stop_requested:
                self.stop()
            if self.countdown is not None:
                remaining = self.countdown - self.clock()
                if remaining <= 0:
                    self._start()
                else:
                    self.message = f"Aufnahme in {int(remaining) + 1} Sekunden – Zielprogramm auswählen."
            if self.target and self.countdown is None and self.clock() - self.started >= MAX_SECONDS:
                self.stop()
            if self.play_pending and self.clock() >= self.play_pending[0]:
                _, bank, key = self.play_pending
                self.play_pending = None
                self.trigger(bank, key)
            if self.player.error:
                self.message = self.player.error

    def snapshot(self):
        with self.mutex:
            return dict(recording=self.target is not None, message=self.message,
                        playing=self.player.busy or self.play_pending is not None, count=len(self.events))

    def close(self):
        self.stop(save=False)
        self.player.cancel()
        self.play_pending = None
        if self.player.thread is not None:
            self.player.thread.join(timeout=0.5)

    def shutdown(self):
        with self.mutex:
            self.closed = True
        self.close()
