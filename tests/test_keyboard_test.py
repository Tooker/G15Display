import queue
import time
import unittest
from unittest.mock import Mock, patch

from g15display.display import G15Error
from g15display.i18n import Translator
from g15display.keyboard_test import (G15_TYPING_DESCRIPTOR, KeyMetrics, KeyboardTest,
                                     ReportProblem, TypingKeyboard, decode_typing_report,
                                     result_message)


def report(*keys, modifiers=0):
    return bytes([modifiers, 0, *keys, *([0] * (6 - len(keys)))])


class KeyboardMetricsTests(unittest.TestCase):
    def test_boot_report_letters_backspace_and_modifiers(self):
        self.assertEqual(decode_typing_report(report(0x2a, 0x04, modifiers=0x81)), {0x2a, 0x04, 0xe0, 0xe7})
        self.assertEqual(decode_typing_report(report(0x2a, 0x2a)), {0x2a})
        self.assertEqual(decode_typing_report(report()), frozenset())

    def test_rollover_short_and_unrelated_reports_are_rejected(self):
        for raw in (b'', bytes(7), bytes(9), bytes([0, 1, 0, 0, 0, 0, 0, 0]), report(1), report(2), report(3), report(0xff)):
            with self.assertRaises(ReportProblem):
                decode_typing_report(raw)

    def test_held_key_and_duplicate_reports_are_not_repeated_presses(self):
        metrics = KeyMetrics()
        metrics.update(report(), 0)
        metrics.update(report(0x2a), 1)
        for stamp in (1.1, 1.2, 3, 5):
            metrics.update(report(0x2a), stamp)
        held = metrics.snapshot(6)
        self.assertEqual((held['presses'], held['releases'], held['duration'], held['rapid']), (1, 0, 5, 0))
        metrics.update(report(), 7)
        self.assertEqual((metrics.presses, metrics.releases, metrics.max_hold), (1, 1, 6))

    def test_rapid_repress_is_only_a_timing_clue(self):
        metrics = KeyMetrics()
        for raw, stamp in ((report(0x2a), 1), (report(), 1.1), (report(0x2a), 1.12), (report(), 1.2)):
            metrics.update(raw, stamp)
        data = metrics.snapshot(2)
        self.assertEqual((data['presses'], data['releases'], data['rapid']), (2, 2, 1))
        data.update(expected=None, session_problem=False)
        self.assertIn('Press ten times', Translator('en')(result_message(data)))

    def test_other_keys_do_not_count_and_no_text_is_collected(self):
        metrics = KeyMetrics()
        metrics.update(report(4), 0)
        metrics.update(report(4, 0x2a), 1)
        metrics.update(report(4), 2)
        self.assertEqual((metrics.presses, metrics.releases), (1, 1))
        self.assertNotIn('keys', metrics.snapshot(3))
        self.assertNotIn('events', vars(metrics))

    def test_rollover_gap_never_manufactures_a_bounce(self):
        metrics = KeyMetrics()
        metrics.update(report(0x2a), 0)
        with self.assertRaises(ReportProblem):
            metrics.update(report(1), 1)
        self.assertTrue(metrics.snapshot(1)['uncertain'])
        metrics.update(report(0x2a), 2)
        self.assertEqual((metrics.presses, metrics.rapid_represses), (1, 0))
        data = metrics.snapshot(3)
        data.update(expected=10, session_problem=False)
        self.assertIn('incomplete', Translator('en')(result_message(data)))

    def test_reference_count_identifies_mismatch_without_claiming_hardware_fault(self):
        metrics = KeyMetrics()
        for index in range(8):
            metrics.update(report(0x2a), index)
            metrics.update(report(), index + 0.2)
        data = metrics.snapshot(9)
        data.update(expected=10, session_problem=False)
        result = Translator('en')(result_message(data))
        self.assertIn('Expected: 10, received: 8', result)
        self.assertIn('cause unknown', result)
        data['expected'] = None
        self.assertIn('Press ten times', Translator('en')(result_message(data)))

    def test_ten_successful_presses_do_not_rule_out_intermittent_fault(self):
        metrics = KeyMetrics()
        for index in range(10):
            metrics.update(report(0x2a), index)
            metrics.update(report(), index + 0.2)
        data = metrics.snapshot(11)
        data.update(expected=10, session_problem=False)
        self.assertIn('does not rule out', Translator('en')(result_message(data)))
        data.update(held=True)
        self.assertIn('Release is missing', Translator('en')(result_message(data)))


class KeyboardDeviceTests(unittest.TestCase):
    @patch('g15display.keyboard_test._hid')
    def test_only_known_physical_keyboard_interface_is_opened_read_only(self, hid):
        keyboard = dict(vendor_id=0x046d, product_id=0xc221, interface_number=0, usage_page=1, usage=6, path=b'physical')
        unrelated = [dict(keyboard, product_id=0xc222, path=b'lcd'),
                     dict(keyboard, interface_number=1, usage_page=12, usage=1, path=b'media'),
                     dict(keyboard, vendor_id=0x16c0, path=b'virtual')]
        hid.return_value.enumerate.return_value = unrelated + [keyboard]
        device = hid.return_value.device.return_value
        device.get_report_descriptor.return_value = G15_TYPING_DESCRIPTOR
        with TypingKeyboard() as reader:
            device.read.return_value = report(0x2a)
            self.assertEqual(reader.read(), report(0x2a))
        device.open_path.assert_called_once_with(b'physical')
        device.read.assert_called_once_with(64, 50)
        device.write.assert_not_called()
        device.send_feature_report.assert_not_called()
        device.close.assert_called_once()

    @patch('g15display.keyboard_test._hid')
    def test_unknown_format_is_closed_and_rejected(self, hid):
        hid.return_value.enumerate.return_value = [dict(vendor_id=0x046d, product_id=0xc221, interface_number=0, usage_page=1, usage=6, path=b'physical')]
        device = hid.return_value.device.return_value
        device.get_report_descriptor.return_value = b'unknown'
        with self.assertRaises(G15Error):
            with TypingKeyboard():
                self.fail('unsupported layout opened')
        device.close.assert_called_once()


class KeyboardSessionTests(unittest.TestCase):
    def test_start_is_explicit_timeouts_preserve_hold_and_stop_freezes_state(self):
        packets = queue.Queue()
        device = Mock()
        device.__enter__ = Mock(return_value=device)
        device.__exit__ = Mock()
        def read():
            try:
                return packets.get(timeout=0.02)
            except queue.Empty:
                return b''
        device.read.side_effect = read
        factory = Mock(return_value=device)
        session = KeyboardTest(device_factory=factory)
        factory.assert_not_called()
        session.start()
        self.addCleanup(session.stop)
        packets.put(report(0x2a))
        deadline = time.monotonic() + 1
        while session.snapshot()['presses'] == 0 and time.monotonic() < deadline:
            time.sleep(0.005)
        time.sleep(0.04)  # At least one empty read; no synthetic release.
        self.assertTrue(session.snapshot()['held'])
        session.finish()
        first = session.snapshot()
        time.sleep(0.02)
        second = session.snapshot()
        self.assertFalse(second['running'])
        self.assertEqual((second['presses'], second['releases'], second['expected']), (1, 0, 10))
        self.assertEqual(first['duration'], second['duration'])
        device.__exit__.assert_called_once()

    def test_connection_error_does_not_become_a_missing_key_diagnosis(self):
        factory = Mock(side_effect=OSError('unplugged'))
        session = KeyboardTest(device_factory=factory)
        session.start()
        session.thread.join(timeout=1)
        session.finish()
        self.assertTrue(session.snapshot()['session_problem'])
        self.assertIn('incomplete', Translator('en')(result_message(session.snapshot())))
        session.reset()
        self.assertFalse(session.snapshot()['session_problem'])
        self.assertIsNone(session.snapshot()['expected'])


if __name__ == '__main__':
    unittest.main()
