from datetime import datetime
import unittest
from unittest.mock import patch

from PIL import Image

from g15display.display import G15, G15Error, encode_report, select_device
from g15display.render import clock_screen, text_screen


def device(path=b"lcd", usage_page=0xFF00, product=0xC222):
    return dict(path=path, usage_page=usage_page, vendor_id=0x046D, product_id=product)


class ReportTests(unittest.TestCase):
    def test_blank_has_only_report_id(self):
        self.assertEqual(encode_report(Image.new("1", (160, 43))), b"\x03" + bytes(991))

    def test_known_pixels_cross_bands_and_reach_bottom_right(self):
        image = Image.new("1", (160, 43))
        for xy in [(0, 0), (0, 7), (0, 8), (159, 42)]:
            image.putpixel(xy, 1)
        report = encode_report(image)
        expected = bytearray(992)
        expected[0], expected[32], expected[192], expected[991] = 3, 0x81, 1, 4
        self.assertEqual(report, bytes(expected))

    def test_full_screen_has_no_pixels_outside_43_rows(self):
        report = encode_report(Image.new("1", (160, 43), 1))
        self.assertEqual(report[1:32], bytes(31))
        self.assertEqual(report[32:832], b"\xff" * 800)
        self.assertEqual(report[832:], b"\x07" * 160)

    def test_wrong_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            encode_report(Image.new("1", (43, 160)))


class DeviceTests(unittest.TestCase):
    def setUp(self):
        lease = patch("g15display.display.DeviceLease")
        lease.start()
        self.addCleanup(lease.stop)

    def test_vendor_collection_selected_over_keypad(self):
        chosen = select_device([device(b"keys", 1), device()])
        self.assertEqual(chosen["path"], b"lcd")

    def test_typing_device_and_other_generations_rejected(self):
        for product in (0xC221, 0xC227):
            with self.assertRaises(G15Error):
                select_device([device(product=product)])

    def test_multiple_keyboards_rejected(self):
        with self.assertRaises(G15Error):
            select_device([device(b"first"), device(b"second")])

    @patch("g15display.display._hid")
    def test_partial_write_fails_and_handle_closes(self, hid):
        hid.return_value.enumerate.return_value = [device()]
        handle = hid.return_value.device.return_value
        handle.write.return_value = 991
        with self.assertRaisesRegex(G15Error, "991/992"):
            with G15() as lcd:
                lcd.show(text_screen("TEST"))
        handle.close.assert_called_once()

    @patch("g15display.display._hid")
    def test_successful_write_and_disconnect_cleanup(self, hid):
        hid.return_value.enumerate.return_value = [device()]
        handle = hid.return_value.device.return_value
        handle.write.side_effect = [992, OSError("disconnected")]
        with self.assertRaisesRegex(G15Error, "disconnected"):
            with G15() as lcd:
                lcd.show(text_screen("TEST"))
                self.assertEqual(len(handle.write.call_args.args[0]), 992)
                lcd.show(text_screen("TEST"))
        handle.close.assert_called_once()


class RenderTests(unittest.TestCase):
    def test_four_lines_and_clock_have_correct_dimensions(self):
        for image in [text_screen("Hallo\nG15\nPython\nTest"), clock_screen(datetime(2026, 10, 19, 15, 42, 0))]:
            self.assertEqual(image.size, (160, 43))
            self.assertEqual(image.mode, "1")
            self.assertIsNotNone(image.getbbox())

    def test_too_many_lines_rejected(self):
        with self.assertRaises(ValueError):
            text_screen("1\n2\n3\n4\n5")


if __name__ == "__main__":
    unittest.main()
