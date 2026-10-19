import json
from concurrent.futures import Future
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from g15display.sources import ActivitySource, CodexClient, MusicSource, NetworkSource, Sources


class ActivityTests(unittest.TestCase):
    def test_incremental_events_partial_lines_and_stale_active_status(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            log = root / "session.jsonl"
            def event(kind, stamp="2099-01-01T00:00:00Z"):
                return json.dumps(dict(timestamp=stamp, type="event_msg", payload=dict(type=kind))) + "\n"
            log.write_text(event("task_started"))
            with sqlite3.connect(root / "state_5.sqlite") as conn:
                conn.execute("CREATE TABLE threads (id,title,name,rollout_path,updated_at,archived)")
                conn.execute("INSERT INTO threads VALUES (?,?,?,?,?,?)", ("one", "Title", "Explicit name", str(log), int(time.time()), 0))
            conn.close()
            source = ActivitySource(root)
            self.assertEqual(source()["active"][0]["name"], "Explicit name")
            with log.open("a") as stream:
                stream.write(event("task_complete")[:-1])
            self.assertEqual(len(source()["active"]), 1)
            with log.open("a") as stream:
                stream.write("\n")
            self.assertEqual(len(source()["complete"]), 1)
            # Truncation/rotation and a stale start must never be called active.
            log.write_text(event("task_started", "2000-01-01T00:00:00Z"))
            state = source()
            self.assertEqual(state["active"], [])
            self.assertEqual(len(state["unknown"]), 1)


class NetworkTests(unittest.TestCase):
    @patch("g15display.sources.time.monotonic", side_effect=[10, 12])
    @patch("g15display.sources.psutil.net_if_addrs", return_value={})
    @patch("g15display.sources.psutil.net_io_counters")
    @patch("g15display.sources.subprocess.run")
    def test_counter_differences_and_initial_sample(self, run, counters, addresses, clock):
        run.return_value.stdout = " interface: en0\n"
        counters.side_effect = [{"en0": SimpleNamespace(bytes_recv=100, bytes_sent=100)},
                                {"en0": SimpleNamespace(bytes_recv=500, bytes_sent=200)}]
        source = NetworkSource()
        self.assertIsNone(source()["down"])
        result = source()
        self.assertEqual((result["down"], result["up"]), (200, 50))


class MusicTests(unittest.TestCase):
    @patch("g15display.sources.subprocess.run")
    def test_no_player_is_not_launched(self, run):
        source = MusicSource()
        with patch.object(source, "_running", return_value=[]):
            self.assertEqual(source()["state"], "stopped")
        run.assert_not_called()

    @patch("g15display.sources.subprocess.run")
    def test_playing_player_wins_over_paused_and_duration_units(self, run):
        run.side_effect = [SimpleNamespace(returncode=0, stdout="paused\x1fSong\x1fArtist\x1f10\x1f200000"),
                           SimpleNamespace(returncode=0, stdout="playing\x1fOther\x1fOther artist\x1f20\x1f180")]
        source = MusicSource()
        with patch.object(source, "_running", return_value=list(source.APPS)):
            result = source()
        self.assertEqual((result["player"], result["duration"]), ("Music", 180))

    @patch("g15display.sources.subprocess.run")
    def test_one_unresponsive_player_does_not_hide_the_other(self, run):
        run.side_effect = [subprocess.TimeoutExpired("osascript", 10),
                           SimpleNamespace(returncode=0, stdout="playing\x1fTrack\x1fArtist\x1f1\x1f60")]
        source = MusicSource()
        with patch.object(source, "_running", return_value=list(source.APPS)):
            result = source()
        self.assertEqual(result["player"], "Music")
        self.assertIn("com.spotify.client", source.blocked_until)


class CodexTests(unittest.TestCase):
    def test_prefers_account_bucket_and_does_not_write_to_chats(self):
        source = CodexClient()
        source.process = SimpleNamespace(poll=lambda: None)
        with patch.object(source, "_call", return_value={"rateLimitsByLimitId": {
            "codex": {"primary": {"usedPercent": 20}},
            "other": {"primary": {"usedPercent": 90}}}}) as call:
            self.assertEqual(source.limits(), [{"usedPercent": 20}])
        call.assert_called_once_with("account/rateLimits/read")


class PollingTests(unittest.TestCase):
    def test_button_action_waits_for_player_poll_instead_of_being_lost(self):
        sources = Sources()
        try:
            sources.jobs = {"music": (sources.music, 3)}
            sources.music.toggle = Mock()
            pending = Future()
            sources.futures["music"] = pending
            sources.toggle_music()
            sources.poll()
            self.assertTrue(sources.action_requested)
            sources.music.toggle.assert_not_called()
            pending.set_result({"state": "playing"})
            sources.poll()
            sources.action.result(timeout=1)
            sources.music.toggle.assert_called_once()
        finally:
            sources.close()


if __name__ == "__main__":
    unittest.main()
