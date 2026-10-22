"""Visual controls for video actions, using the FFmpeg already bundled with the app."""

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QProcess, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from . import theme
from .input_files import InputError
from .media_engine import ffmpeg_binary, validate_media
from .media_join import parse_video_report


class VideoCanvas(QWidget):
    def __init__(self, width: int, height: int, selectable: bool):
        super().__init__()
        self.video_size = (width, height)
        self.selectable = selectable
        self.image = QPixmap()
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.setFixedSize(660, 420)
        self.setCursor(Qt.CrossCursor if selectable else Qt.ArrowCursor)

    def set_frame(self, frame: QPixmap) -> None:
        self.image = frame
        self.update()

    def image_rect(self) -> QRect:
        if self.image.isNull():
            return QRect()
        size = self.image.size()
        size.scale(self.width() - 20, self.height() - 20, Qt.KeepAspectRatio)
        return QRect((self.width() - size.width()) // 2,
                     (self.height() - size.height()) // 2,
                     size.width(), size.height())

    def _clamp(self, point: QPoint) -> QPoint:
        rect = self.image_rect()
        return QPoint(max(rect.left(), min(rect.right(), point.x())),
                      max(rect.top(), min(rect.bottom(), point.y())))

    def selected_box(self, crop: bool) -> list[int] | None:
        if self.start is None or self.end is None:
            return None
        area = self.image_rect()
        if area.isEmpty():
            return None
        selection = QRect(self.start, self.end).normalized().intersected(area)
        if selection.width() < 4 or selection.height() < 4:
            return None
        width, height = self.video_size
        x1 = max(0, min(width - 1, round((selection.left() - area.left()) * width / area.width())))
        y1 = max(0, min(height - 1, round((selection.top() - area.top()) * height / area.height())))
        x2 = max(x1 + 1, min(width, round((selection.right() + 1 - area.left()) * width / area.width())))
        y2 = max(y1 + 1, min(height, round((selection.bottom() + 1 - area.top()) * height / area.height())))
        if crop:
            x1 -= x1 % 2
            y1 -= y1 % 2
            x2 -= x2 % 2
            y2 -= y2 % 2
            if x2 - x1 < 2 or y2 - y1 < 2:
                return None
        return [x1, y1, x2 - x1, y2 - y1]

    def mousePressEvent(self, event):
        if (self.selectable and event.button() == Qt.LeftButton
                and self.image_rect().contains(event.position().toPoint())):
            self.start = self._clamp(event.position().toPoint())
            self.end = self.start
            self.update()

    def mouseMoveEvent(self, event):
        if self.start is not None and event.buttons() & Qt.LeftButton:
            self.end = self._clamp(event.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start is not None:
            self.end = self._clamp(event.position().toPoint())
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.qcolor(theme.tokens().canvas))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
        rect = self.image_rect()
        if not self.image.isNull():
            painter.drawPixmap(rect, self.image)
        if self.start is not None and self.end is not None:
            selection = QRect(self.start, self.end).normalized().intersected(rect)
            painter.fillRect(selection, QColor(218, 233, 248, 45))
            painter.setPen(QPen(QColor('white'), 2))
            painter.drawRect(selection)


class VideoEditor(QDialog):
    GLASS_SURFACE = True

    def __init__(self, path: Path, action: str, parent=None):
        super().__init__(parent)
        theme.prepare_surface(self)
        if action not in {'media.crop', 'media.redact', 'media.frame', 'media.trim',
                          'media.split', 'media.speed'}:
            raise ValueError('Azione video non supportata.')
        self.action = action
        self.path = validate_media(path)
        self.duration = 0.0
        self.ready = False
        self.setWindowTitle({
            'media.crop': 'Ritaglia video', 'media.redact': 'Oscura video',
            'media.frame': 'Scegli fotogramma', 'media.trim': 'Taglia video',
            'media.split': 'Dividi video', 'media.speed': 'Velocità video',
        }[action])
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.canvas = VideoCanvas(640, 360, action in ('media.crop', 'media.redact'))
        self.cuts: list[float] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(11)
        guidance = {
            'media.crop': 'Trascina sull’anteprima per scegliere il ritaglio.',
            'media.redact': 'Trascina sull’anteprima per coprire un’area. Scegli anche l’intervallo.',
            'media.frame': 'Sposta il cursore per scegliere il fotogramma.',
            'media.trim': 'Scegli l’inizio e la fine guardando l’anteprima.',
            'media.split': 'Sposta il cursore e aggiungi fino a nove punti di taglio.',
            'media.speed': 'Scegli la velocità del video.',
        }
        layout.addWidget(QLabel(guidance[action]))
        layout.addWidget(self.canvas)
        self.timeline = QSlider(Qt.Horizontal)
        self.timeline.setRange(0, 10_000)
        self.timeline.valueChanged.connect(self._refresh_labels)
        self.timeline.sliderReleased.connect(self._request_frame)
        layout.addWidget(self.timeline)
        self.time_label = QLabel()
        layout.addWidget(self.time_label)
        if action in ('media.trim', 'media.redact'):
            self.start_slider = self._range_slider(layout, 'Inizio', 0)
            self.end_slider = self._range_slider(layout, 'Fine', 10_000)
        if action == 'media.split':
            row = QHBoxLayout()
            add = QPushButton('Aggiungi taglio qui')
            add.clicked.connect(self._add_cut)
            row.addWidget(add)
            self.cuts_label = QLabel('Nessun taglio')
            row.addWidget(self.cuts_label, 1)
            layout.addLayout(row)
        if action == 'media.speed':
            self.speed = QSlider(Qt.Horizontal)
            self.speed.setRange(25, 400)
            self.speed.setValue(100)
            self.speed.valueChanged.connect(self._refresh_labels)
            layout.addWidget(self.speed)
        self.error = QLabel('Carico l’anteprima…')
        self.error.setObjectName('error')
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        apply = QPushButton('Applica')
        self.apply_button = apply
        apply.setDefault(True)
        apply.setEnabled(False)
        apply.clicked.connect(self._accept_if_valid)
        buttons.addWidget(cancel)
        buttons.addWidget(apply)
        layout.addLayout(buttons)
        self.probe_process = QProcess(self)
        self.probe_process.finished.connect(self._probe_finished)
        self.probe_process.errorOccurred.connect(
            lambda _: self.error.setText('Impossibile leggere il video.'))
        self.probe_timer = QTimer(self)
        self.probe_timer.setSingleShot(True)
        self.probe_timer.timeout.connect(self.probe_process.kill)
        self.frame_process = QProcess(self)
        self.frame_process.finished.connect(self._frame_finished)
        self.frame_process.errorOccurred.connect(
            lambda _: self.error.setText('Impossibile mostrare il fotogramma.'))
        self.frame_timer = QTimer(self)
        self.frame_timer.setSingleShot(True)
        self.frame_timer.timeout.connect(self.frame_process.kill)
        self.wanted_frame = 0
        self.running_frame: int | None = None
        self._closing = False
        self._refresh_labels()
        self.adjustSize()
        pointer = QCursor.pos()
        screen = QApplication.screenAt(pointer) or QApplication.primaryScreen()
        if screen:
            bounds = screen.availableGeometry()
            self.move(max(bounds.left(), min(pointer.x() + 20, bounds.right() - self.width())),
                      max(bounds.top(), min(pointer.y() + 20, bounds.bottom() - self.height())))
        QTimer.singleShot(0, self._start_probe)

    def _range_slider(self, layout: QVBoxLayout, label: str, value: int) -> QSlider:
        row = QHBoxLayout()
        title = QLabel(label)
        title.setFixedWidth(50)
        row.addWidget(title)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 10_000)
        slider.setValue(value)
        slider.sliderReleased.connect(lambda: self.timeline.setValue(slider.value()))
        slider.sliderReleased.connect(self._request_frame)
        slider.valueChanged.connect(self._refresh_labels)
        row.addWidget(slider)
        layout.addLayout(row)
        return slider

    def _seconds(self, slider: QSlider) -> float:
        return round(slider.value() / 10_000 * self.duration, 2)

    def _start_probe(self):
        if self._closing:
            return
        self.probe_process.setProgram(str(ffmpeg_binary()))
        self.probe_process.setArguments(['-hide_banner', '-nostdin',
                                         '-protocol_whitelist', 'file,pipe',
                                         '-i', str(self.path)])
        self.probe_process.start()
        self.probe_timer.start(15_000)

    def _probe_finished(self, exit_code, exit_status):
        if self._closing:
            return
        self.probe_timer.stop()
        report = bytes(self.probe_process.readAllStandardError())[:131_072]
        try:
            self.duration, width, height, _ = parse_video_report(report)
            self.canvas.video_size = (width, height)
            self.ready = True
            self.apply_button.setEnabled(True)
            self._request_frame()
        except InputError as exc:
            known_errors = (b'Invalid data found', b'moov atom not found',
                            b'Permission denied', b'Protocol not on whitelist',
                            b'No such file or directory', b'Duration: N/A')
            detail = next((line.strip().decode('utf-8', errors='replace')[:160]
                           for line in report.splitlines()
                           if any(marker in line for marker in known_errors)), '')
            self.error.setText(f'{exc}  FFmpeg: {detail}' if detail else str(exc))
        self._refresh_labels()

    def _request_frame(self):
        if not self.ready:
            return
        self.wanted_frame = self.timeline.value()
        if self.frame_process.state() != QProcess.NotRunning:
            return
        self._start_frame()

    def _start_frame(self):
        if self._closing:
            return
        self.running_frame = self.wanted_frame
        timestamp = min(self._seconds(self.timeline), max(0, self.duration - 0.05))
        self.frame_process.setProgram(str(ffmpeg_binary()))
        self.frame_process.setArguments([
            '-hide_banner', '-loglevel', 'error', '-nostdin', '-ss', f'{timestamp:.3f}',
            '-protocol_whitelist', 'file,pipe', '-i', str(self.path),
            '-map', '0:v:0', '-frames:v', '1',
            '-vf', 'scale=640:400:force_original_aspect_ratio=decrease',
            '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'])
        self.error.setText('Carico il fotogramma…')
        self.frame_process.start()
        self.frame_timer.start(12_000)

    def _frame_finished(self, exit_code, exit_status):
        if self._closing:
            return
        self.frame_timer.stop()
        data = bytes(self.frame_process.readAllStandardOutput())
        if self.running_frame == self.wanted_frame:
            image = QPixmap()
            if exit_code == 0 and len(data) <= 8_000_000 and image.loadFromData(data):
                self.canvas.set_frame(image)
                self.error.setText('')
            else:
                self.error.setText('Questo fotogramma non è disponibile.')
        if self.running_frame != self.wanted_frame:
            QTimer.singleShot(0, self._start_frame)

    def _refresh_labels(self):
        detail = f'{self._seconds(self.timeline):.2f} / {self.duration:.2f} s'
        if self.action in ('media.trim', 'media.redact'):
            detail += (f'  ·  Da {self._seconds(self.start_slider):.2f}'
                       f' a {self._seconds(self.end_slider):.2f} s')
        if self.action == 'media.speed':
            detail += f'  ·  {self.speed.value() / 100:.2f}×'
        self.time_label.setText(detail)

    def _add_cut(self):
        if not self.ready:
            return
        value = self._seconds(self.timeline)
        if 0.01 <= value <= self.duration - 0.01 and value not in self.cuts and len(self.cuts) < 9:
            self.cuts.append(value)
            self.cuts.sort()
            self.cuts_label.setText('Tagli: ' + ', '.join(f'{cut:.2f} s' for cut in self.cuts))

    def _accept_if_valid(self):
        if not self.ready:
            return
        if self.options() is None:
            self.error.setText('Scegli un’area o un intervallo valido.')
            return
        self.accept()

    def options(self) -> dict | None:
        if not self.ready:
            return None
        if self.action == 'media.crop':
            box = self.canvas.selected_box(crop=True)
            return {'box': box} if box else None
        if self.action == 'media.redact':
            box = self.canvas.selected_box(crop=False)
            start, end = self._seconds(self.start_slider), self._seconds(self.end_slider)
            return {'box': box, 'start': start, 'end': end} if box and end > start else None
        if self.action == 'media.frame':
            return {'time': min(self._seconds(self.timeline), max(0, self.duration - 0.05))}
        if self.action == 'media.trim':
            start, end = self._seconds(self.start_slider), self._seconds(self.end_slider)
            return {'start': start, 'end': end} if end > start else None
        if self.action == 'media.split':
            return {'points': self.cuts} if self.cuts else None
        return {'factor': self.speed.value() / 100}

    def _stop_processes(self):
        self._closing = True
        self.probe_timer.stop()
        self.frame_timer.stop()
        for process in (self.probe_process, self.frame_process):
            if process.state() != QProcess.NotRunning:
                process.kill()
                process.waitForFinished(1000)

    def done(self, result):
        self._stop_processes()
        super().done(result)

    def closeEvent(self, event):
        self._stop_processes()
        super().closeEvent(event)
