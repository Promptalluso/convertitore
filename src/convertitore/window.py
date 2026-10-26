"""Desktop batch window shared by macOS and Windows."""

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from . import theme
from .input_files import InputError, SUPPORTED_SUFFIXES, accept_as_copy, validate_source
from .image_editor import ImageEditor
from .audio_editor import AudioEditor, ChannelEditor
from .video_editor import VideoEditor
from .pdf_page_editor import PdfPageEditor
from .pdf_input import validate_pdf
from .media_engine import AUDIO_SUFFIXES, VIDEO_SUFFIXES, validate_media
from .subtitle_engine import SUBTITLE_SUFFIXES, validate_subtitle
from .runner import Cancelled, run_job, run_operation
from .version import VERSION


class DropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(230)
        self.setAccessibleName("File da convertire")

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() == 0:
            t = theme.tokens()
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            area = self.viewport().rect().adjusted(6, 6, -6, -6)
            pen = QPen(theme.qcolor(t.hairline), 1.5, Qt.DashLine)
            pen.setDashPattern([4, 4])
            painter.setPen(pen)
            painter.drawRoundedRect(area, 12, 12)
            middle = area.center()
            painter.setPen(QPen(theme.qcolor(t.text_muted), 1.8, Qt.SolidLine, Qt.RoundCap,
                                Qt.RoundJoin))
            painter.drawLine(middle.x(), middle.y() - 40, middle.x(), middle.y() - 18)
            painter.drawLine(middle.x() - 9, middle.y() - 27, middle.x(), middle.y() - 18)
            painter.drawLine(middle.x() + 9, middle.y() - 27, middle.x(), middle.y() - 18)
            painter.setPen(theme.qcolor(t.text))
            painter.drawText(area.adjusted(0, 10, 0, 0), Qt.AlignCenter, "Trascina qui i file")
            painter.setPen(theme.qcolor(t.text_muted))
            painter.drawText(area.adjusted(0, 50, 0, 0), Qt.AlignCenter,
                             "Immagini, PDF, video, audio o sottotitoli")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and all(url.isLocalFile() for url in event.mimeData().urls()):
            accept_as_copy(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and all(url.isLocalFile() for url in event.mimeData().urls()):
            self.files_dropped.emit([str(Path(url.toLocalFile())) for url in event.mimeData().urls()])
            accept_as_copy(event)
        else:
            event.ignore()


class Batch(QThread):
    result = Signal(int, str, str)
    progress = Signal(int, int)

    def __init__(self, paths: list[Path], target: str, output_dir: Path | None):
        super().__init__()
        self.paths = paths
        self.target = target
        self.output_dir = output_dir
        self.cancelled = threading.Event()

    def run(self) -> None:
        for index, source in enumerate(self.paths):
            if self.cancelled.is_set():
                break
            try:
                output = run_job(source, self.target, self.output_dir or source.parent, self.cancelled)
                self.result.emit(index, "Completato", str(output))
            except Cancelled:
                self.result.emit(index, "Annullato", "")
                break
            except Exception as exc:
                self.result.emit(index, str(exc), "")
            self.progress.emit(index + 1, len(self.paths))


class OperationBatch(QThread):
    completed = Signal(list)
    failed = Signal(str)

    def __init__(self, paths: list[Path], action: str, options: dict,
                 output_dir: Path | None):
        super().__init__()
        self.paths = paths
        self.action = action
        self.options = options
        self.output_dir = output_dir
        self.cancelled = threading.Event()

    def run(self) -> None:
        try:
            outputs = run_operation(self.action, self.paths, self.options,
                                    self.output_dir or self.paths[0].parent,
                                    self.cancelled,
                                    timeout=900 if self.action.startswith('media.') else 180)
            self.completed.emit([str(path) for path in outputs])
        except Exception as exc:
            self.failed.emit(str(exc))


class Window(QMainWindow):
    GLASS_SURFACE = True

    def __init__(self):
        super().__init__()
        theme.prepare_surface(self)
        self.paths: list[Path] = []
        self.results: list[Path] = []
        self.output_dir: Path | None = None
        self.batch: Batch | OperationBatch | None = None
        self.setWindowTitle(f"Convertitore · v{VERSION}")
        self.resize(780, 620)

        base = QWidget()
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        layout.setContentsMargins(28, 36, 28, 20)
        layout.setSpacing(12)

        title = QLabel("Convertitore")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("Aggiungi i file, scegli cosa farne e premi Converti.")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        self.file_list = DropList()
        self.file_list.files_dropped.connect(self.add_paths)
        layout.addWidget(self.file_list)

        file_row = QHBoxLayout()
        layout.addLayout(file_row)
        self.add_button = QPushButton("Aggiungi file…")
        self.add_button.clicked.connect(self.pick_files)
        file_row.addWidget(self.add_button)
        self.clear_button = QPushButton("Svuota")
        self.clear_button.clicked.connect(self.clear_files)
        file_row.addWidget(self.clear_button)
        self.folder_button = QPushButton("Salva accanto agli originali")
        self.folder_button.clicked.connect(self.choose_folder)
        file_row.addStretch()
        file_row.addWidget(self.folder_button)

        convert_row = QHBoxLayout()
        layout.addLayout(convert_row)
        action_label = QLabel("Azione")
        action_label.setObjectName("muted")
        convert_row.addWidget(action_label)
        self.target = QComboBox()
        self.target.addItems(["PNG", "JPEG", "WEBP", "TIFF", "BMP", "GIF", "AVIF"])
        convert_row.addWidget(self.target, 1)
        self.convert_button = QPushButton("Converti")
        self.convert_button.setObjectName("primary")
        self.convert_button.clicked.connect(self.start_batch)
        convert_row.addWidget(self.convert_button)
        self.cancel_button = QPushButton("Annulla")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_batch)
        convert_row.addWidget(self.cancel_button)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.status = QLabel("Pronto. Fino a 100 file per volta.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        self.status.setObjectName("muted")
        status_row = QHBoxLayout()
        layout.addLayout(status_row)
        status_row.addWidget(self.status, 1)
        self.open_button = QPushButton("Apri cartella dei risultati")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_output)
        status_row.addWidget(self.open_button)
        footer = QLabel(f"Versione {VERSION}. I file restano sul tuo computer.")
        footer.setObjectName("footer")
        layout.addWidget(footer)

    def add_paths(self, paths: list[str]) -> None:
        if self.batch and self.batch.isRunning():
            return
        reached_limit = False
        for raw in paths:
            if len(self.paths) >= 100:
                reached_limit = True
                break
            path = Path(raw)
            self.paths.append(path)
            try:
                if path.suffix.lower() == '.pdf':
                    validate_pdf(path)
                elif path.suffix.lower() in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
                    validate_media(path)
                elif path.suffix.lower() in SUBTITLE_SUFFIXES:
                    validate_subtitle(path)
                else:
                    validate_source(path)
                detail = "Pronto"
            except (InputError, OSError) as exc:
                detail = str(exc)
            item_text = f"{path.name} · {detail}"
            self.file_list.addItem(item_text)
            self.file_list.item(self.file_list.count() - 1).setToolTip(str(path))
        self.status.setText("Limite di 100 file per batch raggiunto." if reached_limit
                            else f"{len(self.paths)} file selezionati.")
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        self.target.clear()
        if not self.paths or all(path.suffix.lower() in SUPPORTED_SUFFIXES
                                 for path in self.paths):
            for name in ('PNG', 'JPEG', 'WEBP', 'TIFF', 'BMP', 'GIF', 'AVIF'):
                self.target.addItem(name)
            if self.paths:
                self.target.addItem('Crea PDF', ('pdf.from_images', {}))
                if len(self.paths) == 1:
                    for label, action in (
                        ('Modifica foto…', 'image.adjust'),
                        ('Aggiungi sfondo…', 'image.add_background'),
                        ('Annota foto…', 'image.annotate'),
                        ('Ritaglia immagine…', 'image.crop'),
                        ('Oscura area in modo permanente…', 'image.redact'),
                        ('Esporta metadati', 'image.metadata'),
                        ('Rimuovi metadati', 'image.strip_metadata'),
                    ):
                        self.target.addItem(label, (action, {}))
                    self.target.addItem('Riconosci testo · OCR offline', ('ocr.text', {}))
                    for percent in (25, 50, 75):
                        self.target.addItem(f'Ridimensiona al {percent}%',
                                            ('image.resize', {'percent': percent}))
                    for degrees in (90, 180, 270):
                        self.target.addItem(f'Ruota immagine {degrees}°',
                                            ('image.rotate', {'degrees': degrees}))
                    for quality in (50, 70, 90):
                        self.target.addItem(f'Comprimi immagine · qualità {quality}',
                                            ('image.compress', {'quality': quality}))
        elif all(path.suffix.lower() == '.pdf' for path in self.paths):
            if len(self.paths) > 1:
                self.target.addItem('Unisci PDF', ('pdf.merge', {}))
            else:
                for name, action, options in (
                    ('Dividi PDF in pagine', 'pdf.split', {}),
                    ('Estrai pagine specifiche…', 'pdf.extract_pages', {}),
                    ('Ruota PDF 90°', 'pdf.rotate', {'degrees': 90}),
                    ('Ruota PDF 180°', 'pdf.rotate', {'degrees': 180}),
                    ('Ruota PDF 270°', 'pdf.rotate', {'degrees': 270}),
                    ('Estrai testo', 'pdf.text', {}),
                    ('Riconosci testo · OCR offline', 'ocr.text', {}),
                    ('Crea PDF ricercabile · OCR offline', 'ocr.searchable_pdf', {}),
                    ('Ottimizza PDF senza perdita', 'pdf.optimize_lossless', {}),
                    ('Comprimi PDF · qualità 60', 'pdf.compress_images', {'quality': 60}),
                    ('Comprimi PDF · qualità 80', 'pdf.compress_images', {'quality': 80}),
                    ('PDF in PNG', 'pdf.to_images', {'target': 'PNG'}),
                    ('PDF in JPEG', 'pdf.to_images', {'target': 'JPEG'}),
                    ('PDF in WebP', 'pdf.to_images', {'target': 'WEBP'}),
                ):
                    self.target.addItem(name, (action, options))
        elif len(self.paths) > 1 and all(path.suffix.lower() in VIDEO_SUFFIXES
                                          for path in self.paths):
            self.target.addItem('Unisci video', ('media.join', {}))
        elif len(self.paths) == 1 and self.paths[0].suffix.lower() in VIDEO_SUFFIXES:
            for target in ('MP4', 'MOV', 'WEBM', 'MKV', 'GIF'):
                self.target.addItem(f'Converti in {target}',
                                    ('media.convert', {'target': target}))
            self.target.addItem('Comprimi video', ('media.compress', {}))
            self.target.addItem('Riduci video a 1080p', ('media.resize', {'height': 1080}))
            self.target.addItem('Riduci video a 720p', ('media.resize', {'height': 720}))
            self.target.addItem('Taglia video…', ('media.trim', {}))
            self.target.addItem('Ritaglia video…', ('media.crop', {}))
            self.target.addItem('Cambia velocità video…', ('media.speed', {}))
            self.target.addItem('Dividi video…', ('media.split', {}))
            self.target.addItem('Oscura area video…', ('media.redact', {}))
            self.target.addItem('Estrai audio MP3',
                                ('media.extract_audio', {'target': 'MP3'}))
            self.target.addItem('Scegli fotogramma…', ('media.frame', {}))
        elif len(self.paths) == 1 and self.paths[0].suffix.lower() in AUDIO_SUFFIXES:
            for target in ('MP3', 'M4A', 'WAV', 'FLAC'):
                self.target.addItem(f'Converti in {target}',
                                    ('media.convert', {'target': target}))
            self.target.addItem('Comprimi audio', ('media.compress', {}))
            self.target.addItem('Normalizza volume audio', ('media.normalize', {}))
            self.target.addItem('Taglia audio…', ('media.trim', {}))
            self.target.addItem('Converti in mono', ('media.channels', {'channels': 1}))
            self.target.addItem('Converti in stereo', ('media.channels', {'channels': 2}))
            self.target.addItem('Regola canali audio…', ('media.channels', {}))
            self.target.addItem('Aggiungi bleep…', ('media.bleep', {}))
        elif len(self.paths) == 1 and self.paths[0].suffix.lower() in SUBTITLE_SUFFIXES:
            for name in ('SRT', 'VTT', 'TXT'):
                self.target.addItem(f'Converti sottotitoli in {name}',
                                    ('subtitle.convert', {'target': name}))
        self.convert_button.setEnabled(self.target.count() > 0)

    def pick_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(self, "Scegli immagini, PDF, video, audio o sottotitoli")
        self.add_paths(selected)

    def clear_files(self) -> None:
        if self.batch and self.batch.isRunning():
            return
        self.paths.clear()
        self.results.clear()
        self.file_list.clear()
        self.progress.setValue(0)
        self.open_button.setEnabled(False)
        self.status.setText("Pronto.")
        self._refresh_actions()

    def choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Cartella dei risultati")
        if selected:
            self.output_dir = Path(selected)
            self.folder_button.setText(f"Risultati: {self.output_dir.name}")

    def start_batch(self) -> None:
        if not self.paths or self.target.count() == 0 or (self.batch and self.batch.isRunning()):
            return
        operation = self.target.currentData()
        if operation:
            action, raw_options = operation
            options = self._ask_options(action, raw_options)
            if options is None:
                return
        self.results.clear()
        self.open_button.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Conversione in corso…")
        for control in (self.add_button, self.clear_button, self.folder_button,
                        self.target, self.convert_button):
            control.setEnabled(False)
        self.cancel_button.setEnabled(True)
        if operation:
            self.batch = OperationBatch(list(self.paths), action, options, self.output_dir)
            self.batch.completed.connect(self.on_operation_completed)
            self.batch.failed.connect(self.on_operation_error)
        else:
            self.batch = Batch(list(self.paths), self.target.currentText(), self.output_dir)
            self.batch.result.connect(self.on_result)
            self.batch.progress.connect(self.on_progress)
        self.batch.finished.connect(self.on_finished)
        self.batch.start()

    def _ask_options(self, action: str, preset: dict) -> dict | None:
        options = dict(preset)
        if action in ('image.adjust', 'image.add_background', 'image.annotate',
                      'image.crop', 'image.redact'):
            editor = ImageEditor(self.paths[0], action, self)
            return editor.options() if editor.exec() else None
        if action in ('media.crop', 'media.redact', 'media.frame', 'media.trim',
                      'media.split', 'media.speed') and self.paths[0].suffix.lower() in VIDEO_SUFFIXES:
            try:
                editor = VideoEditor(self.paths[0], action, self)
            except (InputError, OSError, ValueError) as exc:
                self.status.setText(str(exc))
                return None
            return editor.options() if editor.exec() else None
        if action == 'media.channels' and 'channels' not in options:
            editor = ChannelEditor(self)
            return editor.options() if editor.exec() else None
        if action in ('pdf.extract_pages', 'pdf.text'):
            try:
                editor = PdfPageEditor(self.paths[0], action, self)
            except (InputError, OSError, ValueError) as exc:
                self.status.setText(str(exc))
                return None
            return editor.options() if editor.exec() else None
        elif action in ('media.trim', 'media.bleep') and self.paths[0].suffix.lower() in AUDIO_SUFFIXES:
            try:
                editor = AudioEditor(self.paths[0], action, self)
            except (ValueError, OSError) as exc:
                self.status.setText(str(exc))
                return None
            return editor.options() if editor.exec() else None
        return options

    def on_operation_completed(self, outputs: list[str]) -> None:
        self.results.extend(Path(path) for path in outputs)
        for index, source in enumerate(self.paths):
            item = self.file_list.item(index)
            item.setText(f'{source.name} · Completato')
            item.setToolTip(outputs[0])
        self.progress.setValue(100)
        self.open_button.setEnabled(True)
        self.status.setText(f'{len(outputs)} risultati creati.')

    def on_operation_error(self, message: str) -> None:
        for index, source in enumerate(self.paths):
            item = self.file_list.item(index)
            item.setText(f'{source.name} · {message}')
            item.setToolTip(message)
        self.status.setText(message)

    def on_result(self, index: int, status: str, output: str) -> None:
        item = self.file_list.item(index)
        item.setText(f"{self.paths[index].name} · {status}")
        item.setToolTip(output or status)
        if output:
            self.results.append(Path(output))
            self.open_button.setEnabled(True)
        self.status.setText(status)

    def on_progress(self, done: int, total: int) -> None:
        self.progress.setValue(round(done / total * 100))

    def on_finished(self) -> None:
        for control in (self.add_button, self.clear_button, self.folder_button,
                        self.target, self.convert_button):
            control.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status.setText(f"Terminato: {len(self.results)} risultati. Controlla ogni riga per gli errori.")

    def cancel_batch(self) -> None:
        if self.batch:
            self.batch.cancelled.set()
            self.status.setText("Annullamento in corso… I risultati completati restano disponibili.")

    def open_output(self) -> None:
        if self.results:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.results[-1].parent)))

    def closeEvent(self, event) -> None:
        if self.batch and self.batch.isRunning():
            self.batch.cancelled.set()
            event.ignore()
            QTimer.singleShot(100, self.close)
        else:
            event.accept()


def main(smoke_ui: bool = False) -> int:
    app = QApplication([])
    window = Window()
    window.show()
    if smoke_ui:
        QTimer.singleShot(500, app.quit)
    return app.exec()
