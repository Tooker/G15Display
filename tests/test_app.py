from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock

from g15display.app_controller import AppController, Settings
from g15display.dashboard import PAGES
from g15display.device_lock import DeviceBusy, DeviceLease
from g15display.display import G15Error


class AppTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.source = SimpleNamespace(poll=Mock(), close=Mock(), snapshots={})
        self.device = MagicMock()
        self.device.read_keys.return_value = []
        self.factory = Mock(return_value=self.device)
        self.controller = AppController(sources=self.source, device_factory=self.factory,
                                        legacy_check=lambda: False, clock=lambda: self.now)

    def test_disconnect_preserves_live_preview_and_background_timer(self):
        self.controller.submit("page", "timer")
        self.controller.submit("key", "L4")
        self.controller.step()
        self.assertTrue(self.controller.snapshot()["connected"])
        self.controller.submit("enabled", False)
        self.now = 10
        self.controller.step()
        self.assertFalse(self.controller.snapshot()["connected"])
        self.assertEqual(self.controller.dashboard.timer.label, "04:50")
        self.assertEqual(self.controller.snapshot()["image"].size, (160, 43))
        self.device.close.assert_called_once()

    def test_unplug_and_reconnect_without_restarting_timers(self):
        self.controller.step()
        self.device.read_keys.side_effect = [G15Error("abgezogen"), []]
        self.now = 1
        self.controller.step()
        self.assertFalse(self.controller.snapshot()["connected"])
        self.now = 2
        self.controller.step()
        self.assertEqual(self.factory.call_count, 1)
        self.now = 3
        self.controller.step()
        self.assertTrue(self.controller.snapshot()["connected"])
        self.assertEqual(self.factory.call_count, 2)

    def test_legacy_cli_prevents_two_writers(self):
        self.controller.legacy_check = lambda: True
        self.controller.step()
        self.factory.assert_not_called()
        self.assertIn("Terminal", self.controller.snapshot()["error"])

    def test_settings_apply_and_navigation(self):
        self.controller.submit("settings", Settings(10, 50, 10, 3))
        self.controller.submit("page", "pomodoro")
        self.controller.step()
        self.assertEqual(self.controller.dashboard.pomodoro.label, "50:00")
        self.assertEqual(PAGES[self.controller.snapshot()["page"]], "pomodoro")
        self.controller.submit("key", "L5")
        self.controller.step()
        self.assertTrue(self.controller.snapshot()["menu"])

    def test_invalid_settings_rejected(self):
        for settings in (Settings(minutes=0), Settings(work=float("nan")),
                         Settings(rounds=1.5), Settings(rounds=51)):
            with self.assertRaises(ValueError):
                settings.validate()


class LeaseTests(unittest.TestCase):
    def test_only_one_writer_and_lease_can_be_reacquired(self):
        with tempfile.TemporaryDirectory() as root:
            one = DeviceLease(Path(root) / "display.lock")
            two = DeviceLease(one.path)
            one.acquire()
            try:
                with self.assertRaises(DeviceBusy):
                    two.acquire()
            finally:
                one.close()
            two.acquire()
            two.close()


if __name__ == "__main__":
    unittest.main()
