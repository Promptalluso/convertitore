"""A floating radial drop target with contextual file actions."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRectF, Qt, Signal, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import QApplication, QDialog

from . import theme
from .drag_sampling import in_default_run_loop
from .native_glass import attach_glass
from .input_files import SUPPORTED_SUFFIXES, accept_as_copy
from .media_engine import AUDIO_SUFFIXES, VIDEO_SUFFIXES
from .subtitle_engine import SUBTITLE_SUFFIXES


# File formats keep their usual capitals; actions read as words.
FORMAT_NAMES = frozenset({'PNG', 'JPEG', 'WEBP', 'AVIF', 'TIFF', 'BMP', 'GIF', 'PDF', 'OCR',
                          'MP4', 'MOV', 'WEBM', 'MKV', 'MP3', 'M4A', 'WAV', 'FLAC',
                          'SRT', 'VTT', 'TXT'})
DISPLAY_NAMES = {'RUOTA90': 'Ruota 90°', 'RUOTA180': 'Ruota 180°', 'RUOTA270': 'Ruota 270°',
                 '720P': '720p', '1080P': '1080p', 'BLEEP': 'Bip'}


class DropWheel(QDialog):
    files_dropped = Signal(list, str)

    SIZE = 320
    CENTER = SIZE / 2
    INNER_RADIUS = 51
    DROP_SETTLE_MS = 250
    OUTER_RADIUS = 145
    SECTORS = (
        ("", 0.0, 60.0),
        ("", 60.0, 120.0),
        ("", 120.0, 180.0),
        ("", 180.0, 240.0),
        ("", 240.0, 300.0),
        ("", 300.0, 360.0),
    )

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Convertitore · Trascina e rilascia")
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setMask(QRegion(0, 0, self.SIZE, self.SIZE, QRegion.Ellipse))
        self.setAcceptDrops(True)
        self._active_format: str | None = None
        self._previous_format: str | None = None
        self._hover_level = 1.0
        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(130)
        self._hover_animation.setStartValue(0.0)
        self._hover_animation.setEndValue(1.0)
        self._hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_animation.valueChanged.connect(self._set_hover_level)
        self.sectors = self._empty_sectors()
        self.pages: tuple[tuple[str, ...], ...] = ()
        self.page_index = 0
        self.context_paths: tuple[str, ...] = ()
        self._center_latched = False
        self._center_hover = False
        self._page_timer = QTimer(self)
        self._page_timer.setSingleShot(True)
        self._page_timer.setInterval(400)
        self._page_timer.timeout.connect(self._advance_page)
        self._hold_tick = QTimer(self)
        self._hold_tick.setInterval(16)
        self._hold_tick.timeout.connect(self._tick_hold)
        self._glass_attached = False

    @property
    def active_format(self) -> str | None:
        return self._active_format

    @active_format.setter
    def active_format(self, value: str | None) -> None:
        if value == self._active_format:
            return
        self._previous_format = self._active_format
        self._active_format = value
        self._hover_animation.stop()
        self._hover_animation.start()

    def _set_hover_level(self, value) -> None:
        self._hover_level = float(value)
        self.update()

    @property
    def _hold_progress(self) -> float:
        if not self._page_timer.isActive():
            return 0.0
        return 1 - self._page_timer.remainingTime() / self._page_timer.interval()

    def _tick_hold(self) -> None:
        self.update()
        if not self._page_timer.isActive():
            self._hold_tick.stop()

    @classmethod
    def _empty_sectors(cls):
        return tuple(('', start, end) for _, start, end in cls.SECTORS)

    def reset_context(self) -> None:
        self._page_timer.stop()
        self.sectors = self._empty_sectors()
        self.pages = ()
        self.page_index = 0
        self.context_paths = ()
        self._center_latched = False
        self._center_hover = False
        self.active_format = None
        self.update()

    @staticmethod
    def _local_paths(event) -> list[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        urls = mime.urls()
        if not urls or not all(url.isLocalFile() for url in urls):
            return []
        # Qt gives forward slashes on Windows; keep the native form everywhere.
        return [str(Path(url.toLocalFile())) for url in urls]

    def configure_for_paths(self, paths: list[str]) -> None:
        self.context_paths = tuple(paths)
        suffixes = [Path(path).suffix.lower() for path in paths]
        if suffixes and all(suffix == '.pdf' for suffix in suffixes):
            if len(paths) > 1:
                pages = (('UNISCI', '', '', '', '', ''),)
            else:
                pages = (('PNG', 'JPEG', 'WEBP', 'TESTO', 'OCR', 'COMPRIMI'),
                         ('DIVIDI', 'OTTIMIZZA', 'RUOTA90', 'RUOTA180', 'RUOTA270', 'ESTRAI'))
        elif len(paths) > 1 and all(suffix in VIDEO_SUFFIXES for suffix in suffixes):
            pages = (('UNISCI', '', '', '', '', ''),)
        elif len(paths) == 1 and suffixes[0] in VIDEO_SUFFIXES:
            pages = (('MP4', 'MOV', 'WEBM', 'MKV', 'GIF', 'MP3'),
                     ('COMPRIMI', '720P', '1080P', 'FOTOGRAMMA', 'RITAGLIA', 'VELOCITÀ'),
                     ('DIVIDI', 'OSCURA', 'TAGLIA', '', '', ''))
        elif len(paths) == 1 and suffixes[0] in AUDIO_SUFFIXES:
            pages = (('MP3', 'M4A', 'WAV', 'FLAC', 'COMPRIMI', 'TAGLIA'),
                     ('MONO', 'STEREO', 'BLEEP', 'CANALI', 'NORMALIZZA', ''))
        elif len(paths) == 1 and suffixes[0] in SUBTITLE_SUFFIXES:
            pages = (('SRT', 'VTT', 'TXT', '', '', ''),)
        elif suffixes and all(suffix in SUPPORTED_SUFFIXES for suffix in suffixes):
            pages = (('WEBP', 'PNG', 'JPEG', 'AVIF', 'TIFF', 'PDF'),
                     ('MODIFICA', 'SFONDO', 'ANNOTA', 'RITAGLIA', 'OSCURA', 'METADATI'),
                     ('BMP', 'GIF', 'OCR', 'RIDUCI', 'RUOTA', 'COMPRIMI')) if len(paths) == 1 else (
                         ('WEBP', 'PNG', 'JPEG', 'AVIF', 'TIFF', 'BMP'),)
        else:
            pages = ()
        self.pages = pages
        self.page_index = 0
        self._center_latched = False
        self._center_hover = False
        self._page_timer.stop()
        self._show_page()

    def _advance_page(self) -> None:
        if self._center_hover and not self._center_latched and len(self.pages) > 1:
            self.page_index = (self.page_index + 1) % len(self.pages)
            self._center_latched = True
            self._show_page()

    def _show_page(self) -> None:
        names = self.pages[self.page_index] if self.pages else ('',) * len(self.SECTORS)
        self.sectors = tuple((name, start, end) for name, (_, start, end)
                             in zip(names, self.SECTORS))
        self.active_format = None
        self.update()

    def format_at(self, x: float, y: float) -> str | None:
        dx, dy = x - self.CENTER, y - self.CENTER
        radius = math.hypot(dx, dy)
        if radius < self.INNER_RADIUS or radius > self.OUTER_RADIUS:
            return None
        angle = math.degrees(math.atan2(-dy, dx)) % 360
        for name, start, end in self.sectors:
            if not name:
                continue
            relative = (angle - start) % 360
            if 4 <= relative <= end - start - 4:
                return name
        return None

    def dragEnterEvent(self, event) -> None:
        paths = self._local_paths(event)
        if paths:
            self.configure_for_paths(paths)
            accept_as_copy(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        dx = event.position().x() - self.CENTER
        dy = event.position().y() - self.CENTER
        in_center = math.hypot(dx, dy) < self.INNER_RADIUS
        if in_center and not self._center_hover and len(self.pages) > 1:
            self._page_timer.start()
            self._hold_tick.start()
        elif not in_center:
            self._page_timer.stop()
            self._center_latched = False
        self._center_hover = in_center
        self.active_format = self.format_at(event.position().x(), event.position().y())
        self.update()
        if self._local_paths(event) and (self.active_format or (in_center and self.pages)):
            accept_as_copy(event)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._page_timer.stop()
        self._center_hover = False
        self._center_latched = False
        self.active_format = None
        self.update()
        event.accept()

    def dropEvent(self, event) -> None:
        self._page_timer.stop()
        self._center_hover = False
        paths = self._local_paths(event)
        if paths and tuple(paths) != self.context_paths:
            self.configure_for_paths(paths)
        target = self.format_at(event.position().x(), event.position().y())
        self.active_format = None
        self.update()
        if target and paths:
            accept_as_copy(event)
            QTimer.singleShot(self.DROP_SETTLE_MS,
                              lambda files=list(paths), action=target:
                              self._emit_after_drag(files, action))
        else:
            event.ignore()

    def _emit_after_drag(self, files: list[str], action: str, attempts: int = 0) -> None:
        # A zero-delay timer can fire while macOS is still delivering the drop. A
        # modal editor opened there blocks Finder for 5 s until it cancels the drop.
        if attempts < 40 and not in_default_run_loop():
            QTimer.singleShot(50, lambda: self._emit_after_drag(files, action, attempts + 1))
            return
        self.files_dropped.emit(files, action)

    def _sector_path(self, start: float, end: float, inset: float = 0.0) -> QPainterPath:
        outer_radius = self.OUTER_RADIUS - inset
        inner_radius = self.INNER_RADIUS + inset
        outer = QRectF(-outer_radius, -outer_radius, outer_radius * 2, outer_radius * 2)
        inner = QRectF(-inner_radius, -inner_radius, inner_radius * 2, inner_radius * 2)
        # Keep the same gap width in pixels on both rims.
        outer_gap = math.degrees(inset / outer_radius) if inset else 0.0
        inner_gap = math.degrees(inset / inner_radius) if inset else 0.0
        path = QPainterPath()
        path.arcMoveTo(outer, start + outer_gap)
        path.arcTo(outer, start + outer_gap, end - start - 2 * outer_gap)
        path.arcTo(inner, end - inner_gap, -(end - start - 2 * inner_gap))
        path.closeSubpath()
        return path

    def _draw_document_icon(self, painter: QPainter, x: float, y: float,
                            color: QColor) -> None:
        painter.save()
        painter.translate(x, y)
        painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        paper = QPainterPath()
        paper.moveTo(-7, -10)
        paper.lineTo(3, -10)
        paper.lineTo(8, -5)
        paper.lineTo(8, 10)
        paper.lineTo(-7, 10)
        paper.closeSubpath()
        painter.drawPath(paper)
        painter.drawPolyline([QPointF(3, -10), QPointF(3, -5), QPointF(8, -5)])
        painter.drawLine(QPointF(-3, 2), QPointF(4, 2))
        painter.drawLine(QPointF(-3, 6), QPointF(2, 6))
        painter.restore()

    def _draw_action_icon(self, painter: QPainter, name: str, x: float, y: float,
                          color: QColor) -> None:
        if name not in ('MODIFICA', 'SFONDO', 'ANNOTA', 'RITAGLIA', 'OSCURA',
                        'METADATI', 'COMPRIMI', 'TAGLIA', 'BLEEP', 'MONO', 'STEREO',
                        'CANALI'):
            self._draw_document_icon(painter, x, y, color)
            return
        painter.save()
        painter.translate(x, y)
        painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        if name == 'MODIFICA':
            for row, knob in ((-7, -3), (0, 5), (7, -5)):
                painter.drawLine(-10, row, 10, row)
                painter.setBrush(QColor(245, 249, 253))
                painter.drawEllipse(QPoint(knob, row), 2, 2)
        elif name == 'SFONDO':
            painter.drawRoundedRect(QRectF(-11, -9, 22, 18), 2, 2)
            painter.drawEllipse(QPoint(5, -3), 2, 2)
            painter.drawLine(-9, 6, -2, 0)
            painter.drawLine(-2, 0, 3, 5)
        elif name == 'ANNOTA':
            painter.drawLine(-8, 8, 7, -7)
            painter.drawLine(-10, 11, -5, 9)
            painter.drawLine(5, -9, 9, -5)
        elif name == 'RITAGLIA':
            painter.drawLine(-7, -11, -7, 6)
            painter.drawLine(-11, 6, 7, 6)
            painter.drawLine(7, 11, 7, -6)
            painter.drawLine(11, -6, -7, -6)
        elif name == 'OSCURA':
            painter.drawEllipse(QRectF(-11, -6, 22, 12))
            painter.setBrush(color)
            painter.drawEllipse(QRectF(-3, -3, 6, 6))
            painter.drawLine(-10, 10, 10, -10)
        elif name == 'METADATI':
            tag = QPainterPath()
            tag.moveTo(-10, -7)
            tag.lineTo(3, -7)
            tag.lineTo(10, 0)
            tag.lineTo(3, 7)
            tag.lineTo(-10, 7)
            tag.closeSubpath()
            painter.drawPath(tag)
            painter.drawEllipse(QPoint(-5, 0), 1, 1)
        elif name == 'COMPRIMI':
            painter.drawLine(-10, -10, -2, -2)
            painter.drawLine(10, -10, 2, -2)
            painter.drawLine(-10, 10, -2, 2)
            painter.drawLine(10, 10, 2, 2)
        elif name == 'TAGLIA':
            painter.drawLine(-9, -9, 8, 8)
            painter.drawLine(-9, 9, 8, -8)
            painter.drawEllipse(QRectF(-12, -12, 5, 5))
            painter.drawEllipse(QRectF(-12, 7, 5, 5))
        else:
            for position, height in ((-8, 5), (-4, 9), (0, 13), (4, 8), (8, 4)):
                painter.drawLine(position, -height // 2, position, height // 2)
        painter.restore()

    @staticmethod
    def display_name(name: str) -> str:
        if name in FORMAT_NAMES:
            return name
        return DISPLAY_NAMES.get(name, name.capitalize())

    def paintEvent(self, event) -> None:
        t = theme.tokens()
        dark = theme.is_dark()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.CENTER, self.CENTER)
        ring = QRectF(-self.OUTER_RADIUS, -self.OUTER_RADIUS,
                      self.OUTER_RADIUS * 2, self.OUTER_RADIUS * 2)

        # Over native glass only a light tint is needed; without it the disc must be opaque.
        if self._glass_attached:
            base = QColor(255, 255, 255, 46) if not dark else QColor(24, 28, 36, 70)
        else:
            base = QColor(246, 248, 251, 238) if not dark else QColor(34, 39, 48, 240)
        painter.setPen(Qt.NoPen)
        painter.setBrush(base)
        painter.drawEllipse(ring.adjusted(-4, -4, 4, 4))

        level = self._hover_level
        for name, start, end in self.sectors:
            if not name:
                continue
            strength = (level if name == self.active_format
                        else 1 - level if name == self._previous_format else 0.0)
            if strength > 0:
                fill = theme.qcolor(t.accent)
                fill.setAlphaF(0.96 * strength)
                painter.setBrush(fill)
                painter.drawPath(self._sector_path(start, end, inset=4))
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 255, round(150 * strength)), 1))
                painter.drawPath(self._sector_path(start, end, inset=4.5))
                painter.setPen(Qt.NoPen)

            middle = math.radians((start + end) / 2)
            x = 99 * math.cos(middle)
            y = -99 * math.sin(middle)
            normal = theme.qcolor(t.text)
            accent_ink = theme.qcolor(t.accent_ink)
            ink = QColor.fromRgbF(
                normal.redF() + (accent_ink.redF() - normal.redF()) * strength,
                normal.greenF() + (accent_ink.greenF() - normal.greenF()) * strength,
                normal.blueF() + (accent_ink.blueF() - normal.blueF()) * strength)
            self._draw_action_icon(painter, name, x, y - 13, ink)
            painter.setPen(ink)
            font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
            font.setPointSizeF(10.5)
            font.setWeight(QFont.DemiBold if name in FORMAT_NAMES else QFont.Medium)
            painter.setFont(font)
            painter.drawText(QRectF(x - 48, y + 5, 96, 22), Qt.AlignCenter,
                             self.display_name(name))
            painter.setPen(Qt.NoPen)

        # Hairline dividers instead of dark gaps between sectors.
        painter.setPen(QPen(theme.qcolor(t.hairline), 1))
        for _, start, _ in self.sectors:
            angle = math.radians(start)
            painter.drawLine(QPointF(self.INNER_RADIUS * math.cos(angle),
                                     -self.INNER_RADIUS * math.sin(angle)),
                             QPointF(self.OUTER_RADIUS * math.cos(angle),
                                     -self.OUTER_RADIUS * math.sin(angle)))
        painter.setPen(QPen(QColor(255, 255, 255, 120 if not dark else 40), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(ring)

        center = QRectF(-self.INNER_RADIUS + 5, -self.INNER_RADIUS + 5,
                        (self.INNER_RADIUS - 5) * 2, (self.INNER_RADIUS - 5) * 2)
        painter.setPen(QPen(theme.qcolor(t.hairline), 1))
        painter.setBrush(QColor(255, 255, 255, 150) if not dark else QColor(255, 255, 255, 26))
        painter.drawEllipse(center)
        if self._hold_progress > 0:
            # Fills while the pointer rests in the center, so the page change is expected.
            painter.setPen(QPen(theme.qcolor(t.accent_strong), 3, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(center.adjusted(2, 2, -2, -2), 90 * 16,
                            round(-360 * 16 * self._hold_progress))
        painter.setPen(theme.qcolor(t.text))
        font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
        font.setPointSizeF(10.5)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        hint = ("Trascina\nqui" if not self.pages else
                "Altre\nazioni" if self.page_index == 0 and len(self.pages) > 1 else
                "Indietro" if self.page_index > 0 else "Rilascia\nsul formato")
        painter.drawText(center, Qt.AlignCenter, hint)
        painter.end()

    def show_near(self, x: int, y: int) -> None:
        self.reset_context()
        screen = QApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        left = max(area.left(), min(x + 36, area.right() - self.width() + 1))
        top = max(area.top(), min(y - self.height() // 2, area.bottom() - self.height() + 1))
        self.move(left, top)
        self.show()
        if not self._glass_attached:
            QTimer.singleShot(0, self._attach_native_glass)

    def _attach_native_glass(self) -> None:
        if not self._glass_attached:
            self._glass_attached = attach_glass(self, self.SIZE / 2)
