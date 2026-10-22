import unittest
from unittest.mock import Mock

from convertitore.drag_sampling import mac_buttons, windows_buttons


class DragSamplingTests(unittest.TestCase):
    def test_mac_reads_left_button_and_shift_mask(self):
        quartz = Mock()
        quartz.CGEventSourceButtonState.return_value = True
        quartz.CGEventSourceFlagsState.return_value = 1 << 17
        self.assertEqual(mac_buttons(quartz), (True, True))
        quartz.CGEventSourceFlagsState.return_value = 0
        self.assertEqual(mac_buttons(quartz), (True, False))

    def test_windows_reads_high_bit_of_key_state(self):
        user32 = Mock()
        user32.GetAsyncKeyState.side_effect = lambda key: {1: 0x8000, 16: 0x8000}[key]
        self.assertEqual(windows_buttons(user32), (True, True))
        user32.GetAsyncKeyState.side_effect = lambda key: {1: 0, 16: 1}[key]
        self.assertEqual(windows_buttons(user32), (False, False))
