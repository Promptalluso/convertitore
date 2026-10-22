"""Waveform assisted trim and bleep selection using the bundled FFmpeg."""

import array
import os
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from . import theme
from .media_engine import ffmpeg_binary


def audio_duration(path: Path) -> float:
    command = [str(ffmpeg_binary()), '-hide_banner', '-nostdin',
               '-protocol_whitelist', 'file,pipe', '-i', str(path)]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    result = subprocess.run(command, capture_output=True, timeout=10,
                            creationflags=flags, check=False)
    match = re.search(rb'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
    if not match:
        raise ValueError('Impossibile leggere la durata del file audio.')
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if not 0 < duration <= 86400:
        raise ValueError('La durata del file audio non è supportata.')
    return duration


def audio_waveform(path: Path, duration: float) -> list[float]:
    if duration > 300:
        return []
    command = [str(ffmpeg_binary()), '-hide_banner', '-loglevel', 'error',
               '-nostdin', '-threads', '2', '-protocol_whitelist', 'file,pipe',
               '-i', str(path), '-map', '0:a:0', '-vn', '-ac', '1',
               '-ar', '1200', '-f', 's16le', 'pipe:1']
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        result = subprocess.run(command, capture_output=True, timeout=20,
                                creationflags=flags, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode or len(result.stdout) > 800_000:
        return []
    samples = array.array('h')
    samples.frombytes(result.stdout[:len(result.stdout) // 2 * 2])
    if not samples:
        return []
    bars = 240
    step = max(1, len(samples) // bars)
    return [max(abs(sample) for sample in samples[i:i + step]) / 32768
            for i in range(0, len(samples), step)][:bars]


class Waveform(QWidget):
    def __init__(self, bars: list[float], duration: float, max_interval: float | None = None):
        super().__init__()
        self.bars = bars
        self.duration = duration
        self.max_interval = max_interval
        self.start = 0.0
        self.end = min(duration, 60.0)
        self.dragging = None
        self.setMinimumSize(620, 180)

    def _position(self, seconds: float) -> float:
        return 16 + seconds / self.duration * (self.width() - 32)

    def _seconds(self, x: float) -> float:
        return max(0, min(self.duration, (x - 16) / (self.width() - 32) * self.duration))

    def mousePressEvent(self, event):
        x = event.position().x()
        self.dragging = ('start' if abs(x - self._position(self.start))
                         <= abs(x - self._position(self.end)) else 'end')
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging is None:
            return
        value = self._seconds(event.position().x())
        if self.dragging == 'start':
            self.start = min(value, self.end - 0.01)
            if self.max_interval is not None:
                self.start = max(self.start, self.end - self.max_interval)
        else:
            self.end = max(value, self.start + 0.01)
            if self.max_interval is not None:
                self.end = min(self.end, self.start + self.max_interval)
        self.update()
        self.parent()._refresh_time()

    def mouseReleaseEvent(self, event):
        self.dragging = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.qcolor(theme.tokens().canvas))
        painter.drawRoundedRect(QRectF(self.rect()), 14, 14)
        center = self.height() / 2
        if self.bars:
            width = (self.width() - 32) / len(self.bars)
            painter.setPen(QPen(theme.qcolor(theme.tokens().accent_strong), max(1, width - 1)))
            for index, amplitude in enumerate(self.bars):
                size = max(3, amplitude * (self.height() - 45) / 2)
                x = 16 + index * width
                painter.drawLine(round(x), round(center - size), round(x), round(center + size))
        else:
            painter.setPen(theme.qcolor(theme.tokens().text_muted))
            painter.drawText(self.rect(), Qt.AlignCenter, 'Anteprima forma d’onda disponibile fino a 5 minuti')
        veil = theme.qcolor(theme.tokens().window)
        veil.setAlpha(170)
        painter.fillRect(0, 0, round(self._position(self.start)), self.height(), veil)
        painter.fillRect(round(self._position(self.end)), 0, self.width(), self.height(), veil)
        painter.setPen(QPen(theme.qcolor(theme.tokens().focus), 3, Qt.SolidLine, Qt.RoundCap))
        for value in (self.start, self.end):
            x = round(self._position(value))
            painter.drawLine(x, 0, x, self.height())


class AudioEditor(QDialog):
    GLASS_SURFACE = True

    def __init__(self, path: Path, action: str, parent=None):
        super().__init__(parent)
        theme.prepare_surface(self)
        self.setWindowTitle('Taglia audio' if action == 'media.trim' else 'Aggiungi bleep')
        self.duration = audio_duration(path)
        self.waveform = Waveform(audio_waveform(path, self.duration), self.duration,
                                 60 if action == 'media.bleep' else None)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Trascina le due linee bianche per scegliere l’intervallo.'))
        layout.addWidget(self.waveform)
        self.time_label = QLabel()
        layout.addWidget(self.time_label)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        apply = QPushButton('Applica')
        apply.setDefault(True)
        apply.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(apply)
        layout.addLayout(row)
        self._refresh_time()

    def _refresh_time(self):
        self.time_label.setText(f'Da {self.waveform.start:.2f} s a {self.waveform.end:.2f} s'
                                f' · durata totale {self.duration:.2f} s')

    def options(self) -> dict:
        return {'start': round(self.waveform.start, 2),
                'end': round(self.waveform.end, 2)}


class ChannelEditor(QDialog):
    GLASS_SURFACE = True

    def __init__(self, parent=None):
        super().__init__(parent)
        theme.prepare_surface(self)
        self.setWindowTitle('Canali audio')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Scegli mono o stereo e regola il livello di ciascun canale.'))
        self.mode = QComboBox()
        self.mode.addItems(['Stereo', 'Mono'])
        layout.addWidget(self.mode)
        self.levels = {}
        for label, key in (('Sinistra', 'left'), ('Destra', 'right')):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 200)
            slider.setValue(100)
            row.addWidget(slider)
            number = QLabel('100%')
            row.addWidget(number)
            slider.valueChanged.connect(lambda value, target=number: target.setText(f'{value}%'))
            layout.addLayout(row)
            self.levels[key] = slider
        self.mode.currentIndexChanged.connect(
            lambda index: [slider.setEnabled(index == 0) for slider in self.levels.values()])
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        apply = QPushButton('Applica')
        apply.setDefault(True)
        apply.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(apply)
        layout.addLayout(buttons)

    def options(self) -> dict:
        return {'channels': 1 if self.mode.currentIndex() else 2,
                'left': self.levels['left'].value(),
                'right': self.levels['right'].value()}
