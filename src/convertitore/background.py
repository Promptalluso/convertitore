"""Keep the file drop target ready while the main window is closed."""

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from .drag_sampling import sample_drag_state
from .drag_state import DragSample, DragState
from .drop_wheel import DropWheel
from .input_files import InputError, SUPPORTED_SUFFIXES
from .image_editor import ImageEditor
from .progress_hud import ProgressHud
from .audio_editor import AudioEditor, ChannelEditor
from .video_editor import VideoEditor
from .pdf_page_editor import PdfPageEditor
from .media_engine import AUDIO_SUFFIXES, VIDEO_SUFFIXES
from .subtitle_engine import SUBTITLE_SUFFIXES
from .window import Batch, OperationBatch, Window
from .version import VERSION


class BackgroundController(QObject):
    RELEASE_GRACE_MS = 600

    def __init__(self, window: Window, start_timer: bool = True):
        super().__init__(window)
        self.window = window
        self.state = DragState()
        self.wheel = DropWheel()
        self.wheel.files_dropped.connect(self.accept_drop)
        self.hud = ProgressHud()
        self._release_hide = QTimer(self)
        self._release_hide.setSingleShot(True)
        self._release_hide.setInterval(self.RELEASE_GRACE_MS)
        self._release_hide.timeout.connect(self.wheel.hide)
        self.batch: Batch | OperationBatch | None = None
        self.results: list[Path] = []
        self.errors: list[str] = []
        self.paused = False

        icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(f"Convertitore v{VERSION} · Shift + trascina")
        menu = QMenu()
        menu.addAction("Apri finestra", self.show_window)
        self.result_action = menu.addAction("Apri cartella ultimo risultato", self.show_last_result)
        self.result_action.setEnabled(False)
        self.pause_action = menu.addAction("Pausa gesto", self.toggle_paused)
        menu.addSeparator()
        menu.addAction("Esci", self.request_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.poll)
        if start_timer:
            self.timer.start()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.show_window()

    def show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def show_last_result(self) -> None:
        if self.results:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.results[-1].parent)))

    def toggle_paused(self) -> None:
        self.paused = not self.paused
        self.pause_action.setText("Riprendi gesto" if self.paused else "Pausa gesto")
        if self.paused:
            self.state = DragState()
            self.wheel.hide()

    def poll(self) -> None:
        sample = sample_drag_state()
        if sample is None:
            self.wheel.hide()
            self.state = DragState()
        else:
            self.handle_sample(sample)

    def handle_sample(self, sample: DragSample) -> None:
        if self.paused or (self.batch and self.batch.isRunning()):
            return
        action = self.state.feed(sample)
        if action == "show":
            self._release_hide.stop()
            self.wheel.show_near(sample.x, sample.y)
        elif action == "hide":
            if self.wheel.isVisible() and self.wheel.geometry().contains(QPoint(sample.x, sample.y)):
                # The button is up but macOS has not delivered the drop yet. Hiding now
                # makes Finder end the drag outside the app and the drop is lost.
                self._release_hide.start()
            else:
                self.wheel.hide()

    def accept_drop(self, files: list[str], target: str) -> None:
        if not files or len(files) > 100:
            self.report("Seleziona da 1 a 100 file locali.", error=True)
            return
        if self.batch and self.batch.isRunning():
            # The pill already shows the running job; a second drop is ignored.
            return
        self._release_hide.stop()
        self.wheel.hide()
        self.state = DragState()
        self.results = []
        self.errors = []
        self.result_action.setEnabled(False)
        paths = [Path(file) for file in files]
        suffix = paths[0].suffix.lower()
        operation = None
        if suffix == '.pdf':
            if target in ('PNG', 'JPEG', 'WEBP'):
                operation = ('pdf.to_images', {'target': target})
            else:
                operation = {
                    'UNISCI': ('pdf.merge', {}),
                    'DIVIDI': ('pdf.split', {}),
                    'TESTO': ('pdf.text', {}),
                    'OTTIMIZZA': ('pdf.optimize_lossless', {}),
                    'COMPRIMI': ('pdf.compress_images', {'quality': 60}),
                    'OCR': ('ocr.searchable_pdf', {}),
                    'RUOTA90': ('pdf.rotate', {'degrees': 90}),
                    'RUOTA180': ('pdf.rotate', {'degrees': 180}),
                    'RUOTA270': ('pdf.rotate', {'degrees': 270}),
                    'ESTRAI': ('pdf.extract_pages', {}),
                }.get(target)
                if operation and operation[0] in ('pdf.extract_pages', 'pdf.text'):
                    try:
                        editor = PdfPageEditor(paths[0], operation[0])
                    except (InputError, OSError, ValueError) as exc:
                        self.report(str(exc), error=True)
                        return
                    if not editor.exec():
                        return
                    operation = (operation[0], editor.options())
        elif suffix in VIDEO_SUFFIXES and len(paths) > 1:
            operation = ('media.join', {}) if target == 'UNISCI' else None
        elif suffix in VIDEO_SUFFIXES:
            if target in ('MP4', 'MOV', 'WEBM', 'MKV', 'GIF'):
                operation = ('media.convert', {'target': target})
            else:
                operation = {
                    'MP3': ('media.extract_audio', {'target': 'MP3'}),
                    'COMPRIMI': ('media.compress', {}),
                    '720P': ('media.resize', {'height': 720}),
                    '1080P': ('media.resize', {'height': 1080}),
                }.get(target)
                visual_actions = {
                    'FOTOGRAMMA': 'media.frame', 'RITAGLIA': 'media.crop',
                    'VELOCITÀ': 'media.speed', 'DIVIDI': 'media.split',
                    'OSCURA': 'media.redact', 'TAGLIA': 'media.trim',
                }
                if target in visual_actions:
                    action = visual_actions[target]
                    try:
                        editor = VideoEditor(paths[0], action)
                    except (ValueError, OSError) as exc:
                        self.report(str(exc), error=True)
                        return
                    if not editor.exec():
                        return
                    operation = (action, editor.options())
        elif suffix in SUBTITLE_SUFFIXES and len(paths) == 1:
            if target in ('SRT', 'VTT', 'TXT'):
                operation = ('subtitle.convert', {'target': target})
        elif suffix in AUDIO_SUFFIXES:
            if target in ('MP3', 'M4A', 'WAV', 'FLAC'):
                operation = ('media.convert', {'target': target})
            elif target == 'COMPRIMI':
                operation = ('media.compress', {})
            elif target == 'NORMALIZZA':
                operation = ('media.normalize', {})
            elif target in ('MONO', 'STEREO'):
                operation = ('media.channels', {'channels': 1 if target == 'MONO' else 2})
            elif target == 'CANALI':
                editor = ChannelEditor()
                if not editor.exec():
                    return
                operation = ('media.channels', editor.options())
            elif target in ('TAGLIA', 'BLEEP'):
                try:
                    editor = AudioEditor(paths[0], 'media.trim' if target == 'TAGLIA'
                                         else 'media.bleep')
                except (ValueError, OSError) as exc:
                    self.report(str(exc), error=True)
                    return
                if not editor.exec():
                    return
                operation = ('media.trim' if target == 'TAGLIA' else 'media.bleep',
                             editor.options())
        elif suffix in SUPPORTED_SUFFIXES and len(paths) == 1:
            operation = {
                'PDF': ('pdf.from_images', {}),
                'OCR': ('ocr.text', {}),
                'RIDUCI': ('image.resize', {'percent': 50}),
                'RUOTA': ('image.rotate', {'degrees': 90}),
                'COMPRIMI': ('image.compress', {'quality': 70}),
                'MODIFICA': ('image.adjust', {}),
                'SFONDO': ('image.add_background', {}),
                'ANNOTA': ('image.annotate', {}),
                'RITAGLIA': ('image.crop', {}),
                'OSCURA': ('image.redact', {}),
                'METADATI': ('image.metadata', {}),
            }.get(target)
            if operation and operation[0] in ('image.adjust', 'image.add_background',
                                              'image.annotate', 'image.crop', 'image.redact'):
                editor = ImageEditor(paths[0], operation[0])
                if not editor.exec():
                    return
                operation = (operation[0], editor.options())
        if operation:
            action, options = operation
            self.batch = OperationBatch(paths, action, options, None)
            self.batch.completed.connect(self._on_operation_completed)
            self.batch.failed.connect(self._on_operation_failed)
        elif target in ("PNG", "JPEG", "WEBP", "AVIF", "TIFF", "BMP", "GIF") and all(path.suffix.lower() in SUPPORTED_SUFFIXES for path in paths):
            self.batch = Batch(paths, target, None)
            self.batch.result.connect(self._on_result)
        else:
            self.report("Azione non disponibile per questi file.", error=True)
            return
        self.batch.finished.connect(self._on_finished)
        self.batch.start()
        label = DropWheel.display_name(target)
        self.hud.start(f"{paths[0].name} → {label}" if len(paths) == 1
                       else f"{len(paths)} file → {label}")

    def _on_operation_completed(self, outputs: list[str]) -> None:
        self.results.extend(Path(output) for output in outputs)

    def _on_operation_failed(self, message: str) -> None:
        self.errors.append(message)

    def _on_result(self, index: int, status: str, output: str) -> None:
        if output:
            self.results.append(Path(output))
        else:
            self.errors.append(status)

    def _on_finished(self) -> None:
        self.result_action.setEnabled(bool(self.results))
        if self.errors:
            self.report(self.errors[0], error=True)
        elif len(self.results) == 1:
            self.report(f"Creato {self.results[0].name}", result=self.results[0])
        elif self.results:
            self.report(f"Creati {len(self.results)} file", result=self.results[0])
        else:
            self.report("Nessun file creato.", error=True)

    def report(self, text: str, error: bool = False, result: Path | None = None) -> None:
        """Show how a wheel action ended in the glass pill at the top of the screen."""
        if error and self.hud.state != 'working':
            self.hud.message(text)
        else:
            self.hud.finish(not error, text, result)

    def request_quit(self) -> None:
        self.timer.stop()
        self.wheel.hide()
        self.hud.hide()
        if self.batch and self.batch.isRunning():
            self.batch.cancelled.set()
            self.batch.finished.connect(QApplication.quit)
        else:
            QApplication.quit()
