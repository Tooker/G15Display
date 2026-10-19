"""Countdown and Pomodoro, independent of wall-clock changes and UI pages."""

import math
import time


class Timer:
    def __init__(self, minutes=5, *, work=None, rest=5, rounds=4, clock=time.monotonic):
        if any(not math.isfinite(v) or v <= 0 for v in (minutes, rest, work if work is not None else minutes)):
            raise ValueError("Timerzeiten muessen positiv und endlich sein.")
        if not isinstance(rounds, int) or rounds <= 0:
            raise ValueError("Pomodoro braucht eine positive ganze Rundenzahl.")
        self.clock = clock
        self.work = work
        self.rest = rest * 60
        self.rounds = rounds
        self.duration = (work if work is not None else minutes) * 60
        self.phase = "Arbeit" if work is not None else "Timer"
        self.round = 1
        self.remaining = self.duration
        self.deadline = None
        self.finished = False
        self.transitions = 0

    @property
    def running(self):
        return self.deadline is not None

    def tick(self):
        if self.deadline is None:
            return
        now = self.clock()
        while now >= self.deadline:
            self.transitions += 1
            if self.work is None or (self.phase == "Arbeit" and self.round >= self.rounds):
                self.remaining, self.deadline, self.finished = 0, None, True
                return
            if self.phase == "Arbeit":
                self.phase, duration = "Pause", self.rest
            else:
                self.round += 1
                self.phase, duration = "Arbeit", self.work * 60
            self.deadline += duration
        self.remaining = max(0, self.deadline - now)

    def toggle(self):
        self.tick()
        if self.finished:
            self.reset()
        if self.deadline is None:
            self.deadline = self.clock() + self.remaining
        else:
            self.deadline = None

    def reset(self):
        self.phase = "Arbeit" if self.work is not None else "Timer"
        self.round, self.remaining = 1, self.duration
        self.deadline, self.finished = None, False

    @property
    def label(self):
        self.tick()
        seconds = math.ceil(self.remaining)
        return f"{seconds // 60:02}:{seconds % 60:02}"
