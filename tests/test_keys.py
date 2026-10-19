import unittest
from unittest.mock import patch

from g15display import G15
from g15display.display import G15Error
from g15display.keys import KeyEvent, KeyTracker, decode_keys


class KeyDecodeTests(unittest.TestCase):
    def test_known_g1_m1_and_l2_combination(self):
        # Independent nine-byte fixture for three different groups of keys.
        report = bytes([2, 1, 128, 0, 0, 0, 1, 0, 0])
        self.assertEqual(decode_keys(report), {"G1", "M1", "L2"})

    def test_all_18_g_keys_and_other_special_keys(self):
        # Per-byte OR of documented active bits. Also contains unused bits,
        # which must not create extra keys or affect decoding.
        state = decode_keys(bytes([2] + [255] * 8))
        expected = {f"G{i}" for i in range(1, 19)}
        expected |= {"M1", "M2", "M3", "MR", "LIGHT"}
        expected |= {f"L{i}" for i in range(1, 6)}
        self.assertEqual(state, expected)

    def test_each_display_key_has_a_distinct_bit(self):
        fixtures = {
            "L1": [2, 0, 0, 0, 0, 0, 0, 0, 128],
            "L2": [2, 0, 128, 0, 0, 0, 0, 0, 0],
            "L3": [2, 0, 0, 128, 0, 0, 0, 0, 0],
            "L4": [2, 0, 0, 0, 128, 0, 0, 0, 0],
            "L5": [2, 0, 0, 0, 0, 128, 0, 0, 0],
        }
        for name, report in fixtures.items():
            with self.subTest(name=name):
                self.assertEqual(decode_keys(bytes(report)), {name})

    def test_irregular_g_key_wiring(self):
        self.assertEqual(decode_keys(bytes([2, 4, 0, 0, 0, 0, 0, 32, 64])),
                         {"G13", "G12", "G18"})

    def test_non_key_and_incomplete_reports_ignored(self):
        for report in [b"", bytes([1] + [0] * 8), b"\x03", b"\x02\x01", bytes([2] * 10)]:
            with self.subTest(report=report):
                self.assertIsNone(decode_keys(report))
        self.assertEqual(decode_keys(bytes([2] + [0] * 8)), frozenset())

    def test_edges_duplicates_timeouts_and_chords(self):
        tracker = KeyTracker()
        g1 = bytes([2, 1, 0, 0, 0, 0, 0, 0, 0])
        g1_l2 = bytes([2, 1, 128, 0, 0, 0, 0, 0, 0])
        l2 = bytes([2, 0, 128, 0, 0, 0, 0, 0, 0])
        self.assertEqual(tracker.update(g1), [KeyEvent("G1", True)])
        for report in [g1, b"", bytes([1] + [0] * 8), b"\x02"]:
            self.assertEqual(tracker.update(report), [])
            self.assertEqual(tracker.held, {"G1"})
        self.assertEqual(tracker.update(g1_l2), [KeyEvent("L2", True)])
        self.assertEqual(tracker.update(l2), [KeyEvent("G1", False)])
        self.assertEqual(tracker.update(bytes([2] + [0] * 8)), [KeyEvent("L2", False)])
        self.assertEqual(tracker.held, frozenset())


class KeyReadTests(unittest.TestCase):
    def setUp(self):
        lease = patch("g15display.display.DeviceLease")
        lease.start()
        self.addCleanup(lease.stop)

    @patch("g15display.display._hid")
    def test_read_timeout_and_usb_failure(self, hid):
        hid.return_value.enumerate.return_value = [dict(
            path=b"lcd", usage_page=0xFF00, vendor_id=0x046D, product_id=0xC222)]
        handle = hid.return_value.device.return_value
        handle.read.side_effect = [[2, 1, 0, 0, 0, 0, 0, 0, 0], [], OSError("disconnected")]
        with self.assertRaisesRegex(G15Error, "disconnected"):
            with G15() as lcd:
                self.assertEqual(lcd.read_keys(25), [KeyEvent("G1", True)])
                handle.read.assert_called_with(9, 25)
                self.assertEqual(lcd.read_keys(25), [])
                self.assertEqual(lcd.held_keys, {"G1"})
                lcd.read_keys(25)
        handle.close.assert_called_once()

    def test_unopened_read_rejected(self):
        with self.assertRaises(G15Error):
            G15().read_keys()

    @patch("g15display.display._hid")
    def test_zero_timeout_rejected_to_avoid_blocking_forever(self, hid):
        hid.return_value.enumerate.return_value = [dict(
            path=b"lcd", usage_page=0xFF00, vendor_id=0x046D, product_id=0xC222)]
        with G15() as lcd:
            for timeout in (0, -1, 0.5):
                with self.assertRaises(ValueError):
                    lcd.read_keys(timeout)
        hid.return_value.device.return_value.read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
