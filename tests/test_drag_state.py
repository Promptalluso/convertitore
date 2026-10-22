import unittest

from convertitore.drag_state import DragSample, DragState


class DragStateTests(unittest.TestCase):
    def test_shift_drag_shows_once_then_hides_on_release(self):
        state = DragState()
        self.assertEqual(state.feed(DragSample(10, 10, True, True)), "idle")
        self.assertEqual(state.feed(DragSample(16, 16, True, True)), "idle")
        self.assertEqual(state.feed(DragSample(25, 10, True, True)), "show")
        self.assertEqual(state.feed(DragSample(30, 10, True, True)), "visible")
        self.assertEqual(state.feed(DragSample(30, 10, False, True)), "hide")
        self.assertEqual(state.feed(DragSample(30, 10, False, True)), "idle")

    def test_shift_can_be_pressed_after_drag_begins(self):
        state = DragState()
        state.feed(DragSample(0, 0, True, False))
        self.assertEqual(state.feed(DragSample(25, 0, True, False)), "idle")
        self.assertEqual(state.feed(DragSample(25, 0, True, True)), "show")
        self.assertEqual(state.feed(DragSample(25, 0, True, False)), "visible")
        self.assertEqual(state.feed(DragSample(25, 0, False, False)), "hide")

    def test_movement_without_shift_never_shows(self):
        state = DragState()
        state.feed(DragSample(0, 0, True, False))
        self.assertEqual(state.feed(DragSample(40, 0, True, False)), "idle")
        self.assertEqual(state.feed(DragSample(40, 0, False, False)), "idle")
