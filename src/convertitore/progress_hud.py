"""Glass pill at the top of the screen that shows a wheel job while it runs and how it ended.

macOS hides notifications from unsigned apps, so this is the only place the result appears.
"""

import math
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from . import theme
from .native_glass import attach_glass


class ProgressHud(QWidget):
    WIDTH = 400
    HEIGHT = 68
    ERROR_HEIGHT = 110  # errors get up to three lines: they say what to do next
    RADIUS = 34
    BUTTON = QRectF(WIDTH - 92, 18, 76, 32)

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setWindowTitle('Convertitore')
        self.state = 'idle'          # working, done or error
        self.title = ''
        self.detail = ''
        self.result_path: Path | None = None
        self._started = 0.0
        self._glass_attached = False
        self._tick = QTimer(self)
        self._tick.setInterval(16)
        self._tick.timeout.connect(self.update)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)
        self._fade = QPropertyAnimation(self, b'windowOpacity', self)
        self._fade.setDuration(180)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)

    # Public API -----------------------------------------------------------------------

    def start(self, title: str) -> None:
        self.state, self.title, self.detail, self.result_path = 'working', title, '', None
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self._started = time.monotonic()
        self._hide_timer.stop()
        self._tick.start()
        self._present()

    def finish(self, ok: bool, text: str, result: Path | None = None) -> None:
        self.state = 'done' if ok else 'error'
        self.detail = text
        self.result_path = result if ok else None
        self.setFixedSize(self.WIDTH, self.HEIGHT if ok else self.ERROR_HEIGHT)
        if not self.title:
            self.title = 'Convertitore'
        self._tick.stop()
        self._present()
        self._hide_timer.start(6000 if ok else 12000)
        self.update()

    def message(self, text: str) -> None:
        """An error before any job started, for example an unsupported drop."""
        self.title = 'Azione non riuscita'
        self.finish(False, text)

    def dismiss(self) -> None:
        if not self.isVisible():
            return
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._hide_after_fade)
        self._fade.start()

    # Internals ------------------------------------------------------------------------

    def _hide_after_fade(self) -> None:
        self._fade.finished.disconnect(self._hide_after_fade)
        if self.windowOpacity() == 0.0:
            self.hide()
            self._tick.stop()

    def _present(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.WIDTH // 2, area.top() + 12)
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
            if not self._glass_attached:
                self._glass_attached = attach_glass(self, self.RADIUS)
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(1.0)
        self._fade.start()
        self.update()

    def mousePressEvent(self, event) -> None:
        if (self.state == 'done' and self.result_path is not None
                and self.BUTTON.contains(event.position())):
            self._reveal(self.result_path)
        self.dismiss()

    @staticmethod
    def _reveal(path: Path) -> None:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', '-R', str(path)])
        elif sys.platform == 'win32':
            subprocess.Popen(['explorer', '/select,', str(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def paintEvent(self, event) -> None:
        t = theme.tokens()
        dark = theme.is_dark()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pill = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = self.RADIUS
        if self._glass_attached:
            base = QColor(255, 255, 255, 60) if not dark else QColor(24, 28, 36, 80)
        else:
            base = QColor(246, 248, 251, 245) if not dark else QColor(34, 39, 48, 245)
        painter.setPen(QPen(theme.qcolor(t.hairline), 1))
        painter.setBrush(base)
        painter.drawRoundedRect(pill, radius, radius)

        # Badge: document while working, check when done, exclamation on error.
        badge = QRectF(14, 14, 40, 40)
        accent = theme.qcolor(t.accent)
        ink = theme.qcolor(t.accent_ink)
        if self.state == 'error':
            accent = theme.qcolor(t.error)
            accent.setAlpha(40)
            ink = theme.qcolor(t.error)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(badge)
        painter.setPen(QPen(ink, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        c = badge.center()
        if self.state == 'done':
            painter.drawPolyline([c + QPointF(-8, 0), c + QPointF(-2, 6), c + QPointF(9, -6)])
        elif self.state == 'error':
            painter.drawLine(c + QPointF(0, -9), c + QPointF(0, 3))
            painter.drawPoint(c + QPointF(0, 9))
        else:
            # A short arc turns around the badge so the pill never looks frozen.
            angle = (time.monotonic() - self._started) * 300 % 360
            painter.drawArc(badge.adjusted(9, 9, -9, -9), round(-angle * 16), 100 * 16)

        text_right = self.WIDTH - (104 if self.state == 'done' and self.result_path else 22)
        font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
        font.setPointSizeF(12.5)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(theme.qcolor(t.text))
        metrics = painter.fontMetrics()
        title = metrics.elidedText(self.title, Qt.ElideMiddle, round(text_right - 66))
        painter.drawText(QRectF(66, 13, text_right - 66, 22), Qt.AlignLeft | Qt.AlignVCenter, title)

        font.setPointSizeF(11)
        font.setWeight(QFont.Normal)
        painter.setFont(font)
        painter.setPen(theme.qcolor(t.error if self.state == 'error' else t.text_muted))
        if self.state == 'working':
            detail = f'Sto lavorando… {int(time.monotonic() - self._started)} s'
        else:
            detail = self.detail
        if self.state == 'error':
            painter.drawText(QRectF(66, 35, text_right - 66, 62),
                             Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, detail)
        else:
            detail = painter.fontMetrics().elidedText(detail, Qt.ElideRight, round(text_right - 66))
            painter.drawText(QRectF(66, 34, text_right - 66, 20),
                             Qt.AlignLeft | Qt.AlignVCenter, detail)

        if self.state == 'working':
            # Indeterminate bar: the worker reports only when it ends, so no fake percentage.
            track = QRectF(66, self.HEIGHT - 11, self.WIDTH - 66 - 26, 3)
            faint = theme.qcolor(t.hairline)
            painter.setPen(Qt.NoPen)
            painter.setBrush(faint)
            painter.drawRoundedRect(track, 1.5, 1.5)
            phase = (time.monotonic() - self._started) % 1.4 / 1.4
            eased = (1 - math.cos(phase * math.pi)) / 2
            segment = track.width() * 0.32
            x = track.left() - segment + (track.width() + segment) * eased
            bar = QRectF(max(track.left(), x), track.top(),
                         min(track.right(), x + segment) - max(track.left(), x), track.height())
            if bar.width() > 0:
                painter.setBrush(theme.qcolor(t.accent_strong))
                painter.drawRoundedRect(bar, 1.5, 1.5)
        elif self.state == 'done' and self.result_path is not None:
            painter.setPen(QPen(theme.qcolor(t.accent_strong), 1))
            painter.setBrush(theme.qcolor(t.accent))
            painter.drawRoundedRect(self.BUTTON, 16, 16)
            painter.setPen(theme.qcolor(t.accent_ink))
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.drawText(self.BUTTON, Qt.AlignCenter, 'Mostra')
        painter.end()
