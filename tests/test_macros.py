from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from g15display.macros import Macro, MacroPlayer, MacroStore, Stroke
from g15display.app_controller import AppController
from g15display.keys import KeyEvent
from types import SimpleNamespace


class MacroTests(unittest.TestCase):
    def test_profiles_keep_banks_separate_and_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "macros.json"
            store = MacroStore(path)
            one = Macro("Beispiel", (Stroke("down", 0), Stroke("up", 0, delay=0.1)))
            two = Macro("Andere Bank", (Stroke("down", 1), Stroke("up", 1)))
            store.set("M1", "G1", one)
            store.set("M2", "G1", two)
            loaded = MacroStore(path)
            self.assertEqual(loaded.get("M1", "G1"), one)
            self.assertEqual(loaded.get("M2", "G1"), two)
            loaded.set("M1", "G1", None)
            self.assertEqual(MacroStore(path).get("M2", "G1"), two)
            self.assertIsNone(MacroStore(path).get("M1", "G1"))

    def test_corrupt_profile_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "macros.json"
            path.write_text("broken profile")
            store = MacroStore(path)
            with self.assertRaises(ValueError):
                store.set("M1", "G1", Macro("Test", (Stroke("down", 0),)))
            self.assertEqual(path.read_text(), "broken profile")

    def test_cancel_releases_keys_that_were_already_pressed(self):
        posted = []
        def post(event):
            posted.append(event)
            if event.kind == "down":
                player.cancel()
        player = MacroPlayer(post)
        player.play(Macro("Cancel", (Stroke("down", 0), Stroke("up", 0, delay=10))))
        player.thread.join(timeout=1)
        self.assertFalse(player.busy)
        self.assertEqual([(e.kind, e.code) for e in posted], [("down", 0), ("up", 0)])

    def test_unfinished_modifiers_are_released(self):
        posted = []
        player = MacroPlayer(posted.append)
        player.play(Macro("Cmd", (Stroke("flags", 55, flags=1 << 20), Stroke("down", 0))))
        player.thread.join(timeout=1)
        self.assertEqual([(e.kind, e.code) for e in posted],
                         [("flags", 55), ("down", 0), ("up", 0), ("flags", 55)])
        self.assertEqual(posted[-1].flags, 0)

    def test_invalid_and_other_platform_macros_are_rejected(self):
        for event in (Stroke("unknown", 0), Stroke("down", 256), Stroke("up", 0, delay=float("nan"))):
            with self.assertRaises(ValueError):
                Macro("Bad", (event,)).validate()
        other = "win32" if sys.platform == "darwin" else "darwin"
        with self.assertRaises(ValueError):
            MacroPlayer(Mock()).play(Macro("Other", (Stroke("down", 0),), other))

    def test_bank_and_g_keys_dispatch_only_on_press_and_mr_stops(self):
        service = Mock()
        sources = SimpleNamespace(poll=Mock(), close=Mock(), snapshots={})
        controller = AppController(sources=sources, macros=service)
        controller.handle_key(KeyEvent("M2", True))
        controller.handle_key(KeyEvent("G18", True))
        controller.handle_key(KeyEvent("G18", False))
        service.trigger.assert_called_once_with("M2", "G18")
        controller.handle_key(KeyEvent("MR", True))
        service.request_stop.assert_called_once()


@unittest.skipUnless(sys.platform == "darwin", "macOS event tap adapter")
class RecorderTests(unittest.TestCase):
    def setUp(self):
        from g15display.macos_macros import MacMacroService
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = 0
        self.service = MacMacroService(MacroStore(Path(self.directory.name) / "macros.json"), clock=lambda: self.now)

    @patch("g15display.macos_macros.Q.CGRequestListenEventAccess")
    @patch("g15display.macos_macros.Q.CGPreflightListenEventAccess", return_value=False)
    @patch("g15display.macos_macros.Q.CGEventTapCreate")
    def test_no_permission_means_no_recording(self, create, preflight, request):
        self.service.arm("M1", "G1", "Test")
        self.assertIsNone(self.service.target)
        create.assert_not_called()
        request.assert_called_once()

    @patch("g15display.macos_macros.Q.CGEventGetFlags", return_value=0)
    @patch("g15display.macos_macros.Q.CGEventGetIntegerValueField", return_value=0)
    def test_recording_is_explicit_and_saved_on_stop(self, field, flags):
        import Quartz as Q
        # Unarmed: keyboard input is not collected.
        self.service._callback(None, Q.kCGEventKeyDown, None, None)
        self.assertEqual(self.service.events, [])
        self.service.target = ("M1", "G1", "A")
        self.now = 1
        self.service._callback(None, Q.kCGEventKeyDown, None, None)
        self.now = 1.2
        self.service._callback(None, Q.kCGEventKeyUp, None, None)
        self.service.stop()
        macro = self.service.store.get("M1", "G1")
        self.assertEqual([e.kind for e in macro.events], ["down", "up"])
        self.assertAlmostEqual(macro.events[1].delay, 0.2)
        self.assertIsNone(self.service.target)

    @patch("g15display.macos_macros.Q.CGEventGetIntegerValueField")
    def test_own_playback_is_not_recorded_again(self, field):
        import Quartz as Q
        from g15display.macos_macros import EVENT_TAG
        field.return_value = EVENT_TAG
        self.service.target = ("M1", "G1", "Test")
        self.service._callback(None, Q.kCGEventKeyDown, None, None)
        self.assertEqual(self.service.events, [])

    def test_interrupted_recording_preserves_previous_macro(self):
        original = Macro("Old", (Stroke("down", 1), Stroke("up", 1)))
        self.service.store.set("M1", "G1", original)
        self.service.target = ("M1", "G1", "New")
        self.service.events = [Stroke("down", 0)]
        self.service.failed = True
        self.service.stop()
        self.assertEqual(self.service.store.get("M1", "G1"), original)


if __name__ == "__main__":
    unittest.main()
