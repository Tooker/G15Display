from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from g15display.dashboard import Dashboard, PAGES, window_label
from g15display.keys import KeyEvent
from g15display.sources import Snapshot
from g15display.timers import Timer


class TimerTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.clock = lambda: self.now

    def test_pause_resume_finish_and_restart(self):
        timer = Timer(1, clock=self.clock)
        timer.toggle()
        self.now = 20
        timer.toggle()
        self.assertEqual(timer.label, "00:40")
        self.now = 300
        self.assertEqual(timer.label, "00:40")
        timer.toggle()
        self.now = 340
        timer.tick()
        self.assertTrue(timer.finished)
        self.assertFalse(timer.running)
        self.assertEqual(timer.label, "00:00")
        timer.toggle()
        self.assertTrue(timer.running)
        self.assertEqual(timer.label, "01:00")

    def test_pomodoro_moves_to_break_and_next_work_round(self):
        timer = Timer(work=1, rest=0.5, rounds=2, clock=self.clock)
        timer.toggle()
        self.now = 65
        self.assertEqual(timer.label, "00:25")
        self.assertEqual(timer.phase, "Pause")
        self.now = 100
        self.assertEqual(timer.label, "00:50")
        self.assertEqual((timer.phase, timer.round), ("Arbeit", 2))
        self.now = 151
        timer.tick()
        self.assertTrue(timer.finished)
        self.assertEqual(timer.transitions, 3)

    def test_large_time_jump_does_not_restart_phase_at_now(self):
        timer = Timer(work=1, rest=0.5, rounds=4, clock=self.clock)
        timer.toggle()
        self.now = 1000
        timer.tick()
        self.assertTrue(timer.finished)
        self.assertEqual(timer.round, 4)

    def test_invalid_configuration(self):
        for options in (dict(minutes=0), dict(work=-1), dict(rest=0), dict(rounds=0), dict(minutes=float("inf"))):
            with self.assertRaises(ValueError):
                Timer(**options)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.sources = SimpleNamespace(snapshots={name: Snapshot() for name in ("limits", "activity", "music", "network")},
                                       toggle_music=Mock())
        self.ui = Dashboard(self.sources, clock=lambda: self.now)

    def press(self, name, hold=0):
        self.ui.handle(KeyEvent(name, True))
        self.now += hold
        self.ui.handle(KeyEvent(name, False))

    def test_navigation_menu_select_and_home(self):
        self.press("L2")
        self.assertEqual(PAGES[self.ui.page], "network")
        self.press("L5")
        self.assertTrue(self.ui.menu)
        self.press("L3")
        self.press("L4")
        self.assertFalse(self.ui.menu)
        self.assertEqual(PAGES[self.ui.page], "clock")
        self.press("L5")
        self.press("L3")
        self.press("L5")
        self.assertEqual(self.ui.page, 0)

    def test_timer_continues_on_another_page_and_long_press_resets(self):
        self.ui.page = PAGES.index("timer")
        self.press("L4")
        self.press("L3")
        self.now = 90
        self.ui.tick()
        self.assertEqual(self.ui.timer.label, "03:30")
        self.press("L2")
        self.press("L4", hold=1.1)
        self.assertFalse(self.ui.timer.running)
        self.assertEqual(self.ui.timer.label, "05:00")

    def test_changing_page_cancels_pending_action(self):
        self.ui.page = PAGES.index("timer")
        self.ui.handle(KeyEvent("L4", True))
        self.press("L3")
        self.ui.handle(KeyEvent("L4", False))
        self.assertFalse(self.ui.timer.running)
        self.assertFalse(self.ui.pomodoro.running)

    def test_music_controls_only_after_explicit_button_action(self):
        self.ui.page = PAGES.index("music")
        self.ui.render()
        self.sources.toggle_music.assert_not_called()
        self.press("L4")
        self.sources.toggle_music.assert_called_once()

    def test_no_quota_reset_action(self):
        self.ui.page = PAGES.index("limits")
        self.press("L4")
        self.assertTrue(self.ui.show_reset)
        self.sources.toggle_music.assert_not_called()

    def test_every_page_and_menu_render_with_loading_and_real_fixtures(self):
        for i in range(len(PAGES)):
            self.ui.page = i
            image = self.ui.render()
            self.assertEqual((image.mode, image.size), ("1", (160, 43)))
            self.assertIsNotNone(image.getbbox())
        self.sources.snapshots.update({
            "limits": Snapshot(value=[dict(usedPercent=32, windowDurationMins=300, resetsAt=1792423330),
                                      dict(usedPercent=23, windowDurationMins=10080, resetsAt=1792912097)], error=""),
            "activity": Snapshot(value={"active": [{"name": "G15-Menue bauen"}], "unknown": [], "complete": []}, error=""),
            "music": Snapshot(value={"state": "playing", "title": "Ein sehr langer Musiktitel als Laufschrift", "artist": "Artist", "duration": 100, "position": 25}, error=""),
            "network": Snapshot(value={"interface": "en0", "ip": "192.0.2.1", "down": 2048, "up": 1024}, error=""),
        })
        for self.ui.show_reset in (False, True):
            for i in range(len(PAGES)):
                self.ui.page = i
                self.now += 5
                for self.ui.menu in (False, True):
                    image = self.ui.render(datetime(2026, 10, 19, 15, 0, 0))
                    self.assertEqual(len(image.tobytes()), 860)

    def test_unknown_window_is_not_falsely_labelled_five_hours(self):
        self.assertEqual(window_label(dict(windowDurationMins=60)), "60m")
        self.assertEqual(window_label(dict(windowDurationMins=300)), "5h")


if __name__ == "__main__":
    unittest.main()
