"""Decide when a Shift drag should reveal the file drop target."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DragSample:
    x: int
    y: int
    left_down: bool
    shift_down: bool


class DragState:
    def __init__(self, threshold: int = 12):
        self.threshold = threshold
        self.anchor: tuple[int, int] | None = None
        self.visible = False

    def feed(self, sample: DragSample) -> str:
        if not sample.left_down:
            self.anchor = None
            if self.visible:
                self.visible = False
                return "hide"
            return "idle"

        if self.anchor is None:
            self.anchor = (sample.x, sample.y)
        if self.visible:
            return "visible"
        if not sample.shift_down:
            return "idle"

        distance_sq = (sample.x - self.anchor[0]) ** 2 + (sample.y - self.anchor[1]) ** 2
        if distance_sq >= self.threshold ** 2:
            self.visible = True
            return "show"
        return "idle"
