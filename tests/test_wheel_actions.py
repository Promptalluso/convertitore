"""Every sector shown on the drop wheel must produce a real output file.

The test drives the same BackgroundController.accept_drop used by a Finder drop,
answering each visual editor the way a person would.
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import imageio_ffmpeg
from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QDialog
from reportlab.pdfgen import canvas as pdf_canvas

from convertitore.audio_editor import AudioEditor
from convertitore.background import BackgroundController
from convertitore.drop_wheel import DropWheel
from convertitore.image_editor import ImageEditor
from convertitore.pdf_page_editor import PdfPageEditor
from convertitore.video_editor import VideoEditor
from convertitore.window import Window

APP = QApplication.instance() or QApplication([])


def _ffmpeg(*args: str) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error',
                    '-y', *args], check=True, timeout=60)


def _make_samples(root: Path) -> dict[str, list[Path]]:
    logo = root / 'logo.png'
    image = Image.new('RGBA', (320, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 140, 160), fill=(10, 10, 10, 255))
    draw.text((160, 90), 'Newcrecon 2026', fill=(10, 10, 10, 255))
    image.save(logo)
    photo = root / 'foto.jpg'
    Image.new('RGB', (640, 480), (120, 160, 200)).save(photo, quality=90)
    pdfs = []
    for name in ('uno.pdf', 'due.pdf'):
        path = root / name
        document = pdf_canvas.Canvas(str(path))
        for page in range(2):
            document.setFont('Helvetica', 28)
            document.drawString(80, 700, f'Pagina {page + 1} TESTO PROVA')
            document.showPage()
        document.save()
        pdfs.append(path)
    videos = []
    for name in ('clip.mp4', 'clip2.mov'):
        path = root / name
        _ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=15',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100',
                '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(path))
        videos.append(path)
    audio = root / 'voce.mp3'
    _ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=330:sample_rate=44100', '-t', '3',
            '-ac', '2', str(audio))
    subtitles = root / 'sottotitoli.srt'
    subtitles.write_text('1\n00:00:00,000 --> 00:00:01,500\nCiao a tutti\n', encoding='utf-8')
    return {'png': [logo], 'jpg': [photo], 'png+jpg': [logo, photo], 'pdf': [pdfs[0]],
            'pdf+pdf': pdfs, 'video': [videos[0]], 'video+video': videos,
            'audio': [audio], 'srt': [subtitles]}


def _wait(condition, seconds: float = 30) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        APP.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return False


def _answer_editor(dialog: QDialog) -> int:
    """Make the choice a person would make, then press Applica."""
    if isinstance(dialog, VideoEditor):
        if not _wait(lambda: dialog.ready and not dialog.canvas.image.isNull()):
            return 0
        rect = dialog.canvas.image_rect()
        dialog.canvas.start = rect.topLeft() + QPoint(10, 10)
        dialog.canvas.end = rect.center()
        if dialog.action in ('media.trim', 'media.redact'):
            dialog.start_slider.setValue(1_000)
            dialog.end_slider.setValue(8_000)
        elif dialog.action == 'media.split':
            dialog.cuts = [round(dialog.duration / 2, 2)]
        elif dialog.action == 'media.speed':
            dialog.speed.setValue(200)
    elif isinstance(dialog, ImageEditor):
        area = dialog.canvas._area()
        dialog.canvas.start = area.topLeft() + QPoint(5, 5)
        dialog.canvas.end = area.center()
        if dialog.action == 'image.adjust':
            dialog.sliders['contrast'].setValue(140)
        elif dialog.action == 'image.annotate':
            dialog.text.setText('Prova')
    elif isinstance(dialog, AudioEditor):
        dialog.waveform.start, dialog.waveform.end = 0.5, 1.5
    elif isinstance(dialog, PdfPageEditor):
        dialog.pages = [1]
    return 1


class WheelActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.samples = _make_samples(Path(cls.tmp.name))
        cls.controllers = []

    @classmethod
    def tearDownClass(cls):
        # Controllers stay referenced until here: a QTimer garbage-collected from a
        # worker thread aborts Qt.
        for controller in cls.controllers:
            controller.deleteLater()
        APP.processEvents()
        cls.tmp.cleanup()

    def _drop(self, files: list[Path], target: str) -> tuple[list[Path], list[str]]:
        controller = BackgroundController(Window(), start_timer=False)
        messages: list[tuple[str, bool]] = []
        controller.report = lambda text, error=False, result=None: messages.append((text, error))
        before = {path for path in files[0].parent.iterdir()}
        with mock.patch.object(QDialog, 'exec', _answer_editor):
            controller.accept_drop([str(path) for path in files], target)
        if controller.batch is not None:
            self.assertTrue(_wait(lambda: controller.batch.isFinished(), 180),
                            f'{target} did not finish')
            _wait(lambda: bool(messages), 5)
        new = [path for path in files[0].parent.iterdir() if path not in before]
        controller.tray.hide()
        for timer in (controller.hud._tick, controller.hud._hide_timer, controller._release_hide):
            timer.stop()
        controller.hud.hide()
        controller.window.close()
        self.controllers.append(controller)
        return new, messages

    def test_every_wheel_sector_creates_a_file(self):
        wheel = DropWheel()
        failures = []
        for kind, files in self.samples.items():
            wheel.configure_for_paths([str(path) for path in files])
            names = [name for page in wheel.pages for name in page if name]
            self.assertTrue(names, f'{kind}: the wheel shows no actions')
            for name in names:
                outputs, messages = self._drop(files, name)
                errors = [text for text, error in messages if error]
                empty = [path.name for path in outputs if path.is_file()
                         and path.stat().st_size == 0]
                if errors or not outputs or empty:
                    failures.append(f'{kind} → {name}: '
                                    f'{errors[0] if errors else "nessun file creato"}'
                                    f'{" (vuoti: " + ", ".join(empty) + ")" if empty else ""}')
        self.assertEqual([], failures, '\n' + '\n'.join(failures))


if __name__ == '__main__':
    unittest.main()
