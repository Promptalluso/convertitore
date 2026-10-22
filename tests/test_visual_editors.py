import subprocess
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter
from PIL import Image
from PySide6.QtCore import QPoint, Qt, QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from convertitore.media_engine import ffmpeg_binary
from convertitore.media_join import probe_video
from convertitore.operation_publication import publish_operation
from convertitore.pdf_page_editor import PdfPageEditor
from convertitore.video_editor import VideoEditor
from convertitore.image_editor import ImageEditor


class VisualEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _wait_video(self, editor):
        for _ in range(100):
            if editor.ready and not editor.canvas.image.isNull():
                return
            QTest.qWait(50)
        self.fail(editor.error.text() or 'Anteprima video non caricata')

    def test_video_crop_comes_from_dragging_over_real_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'sample.mp4'
            subprocess.run([str(ffmpeg_binary()), '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=10',
                            '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                            str(source)], capture_output=True, timeout=30, check=True)
            editor = VideoEditor(source, 'media.crop')
            editor.show()
            self._wait_video(editor)
            rect = editor.canvas.image_rect()
            start = QPoint(rect.left() + 30, rect.top() + 30)
            end = QPoint(rect.right() - 30, rect.bottom() - 30)
            QTest.mousePress(editor.canvas, Qt.LeftButton, pos=start)
            QTest.mouseMove(editor.canvas, end)
            QTest.mouseRelease(editor.canvas, Qt.LeftButton, pos=end)
            options = editor.options()
            self.assertIsNotNone(options)
            x, y, width, height = options['box']
            self.assertTrue(0 <= x < x + width <= 320)
            self.assertTrue(0 <= y < y + height <= 240)
            self.assertEqual(width % 2, 0)
            self.assertEqual(height % 2, 0)
            cropped, = publish_operation('media.crop', [source], options, Path(directory))
            self.assertEqual(probe_video(cropped)[1:3], (width, height))
            editor.close()
            editor.deleteLater()
            self.app.processEvents()

    def test_pdf_preview_selects_pages_for_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'sample.pdf'
            writer = PdfWriter()
            writer.add_blank_page(200, 300)
            writer.add_blank_page(200, 300)
            with source.open('wb') as output:
                writer.write(output)
            editor = PdfPageEditor(source, 'pdf.text')
            self.assertFalse(editor.preview.pixmap().isNull())
            editor.number.setValue(2)
            editor._add()
            result, = publish_operation('pdf.text', [source], editor.options(), folder)
            self.assertIn('--- Pagina 2 ---', result.read_text(encoding='utf-8'))
            self.assertNotIn('--- Pagina 1 ---', result.read_text(encoding='utf-8'))
            editor.close()
            editor.deleteLater()
            self.app.processEvents()

    def test_image_crop_from_drag_reduces_actual_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'photo.png'
            Image.new('RGB', (320, 240), 'red').save(source)
            editor = ImageEditor(source, 'image.crop')
            editor.show()
            self.app.processEvents()
            area = editor.canvas._area()
            QTest.mousePress(editor.canvas, Qt.LeftButton,
                             pos=QPoint(area.left() + 40, area.top() + 30))
            QTest.mouseMove(editor.canvas, QPoint(area.right() - 40, area.bottom() - 30))
            QTest.mouseRelease(editor.canvas, Qt.LeftButton,
                               pos=QPoint(area.right() - 40, area.bottom() - 30))
            options = editor.options()
            result, = publish_operation('image.crop', [source], options, Path(directory))
            with Image.open(result) as image:
                self.assertLess(image.width, 320)
                self.assertLess(image.height, 240)
            editor.close()
            editor.deleteLater()
            self.app.processEvents()

    def test_video_trim_from_visual_interval_reduces_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'sample.mp4'
            subprocess.run([str(ffmpeg_binary()), '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=10',
                            '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                            str(source)], capture_output=True, timeout=30, check=True)
            editor = VideoEditor(source, 'media.trim')
            editor.show()
            self._wait_video(editor)
            editor.start_slider.setValue(2500)
            editor.end_slider.setValue(7500)
            result, = publish_operation('media.trim', [source], editor.options(), Path(directory))
            self.assertAlmostEqual(probe_video(result)[0], 1.0, delta=0.15)
            editor.close()
            editor.deleteLater()
            self.app.processEvents()

    def test_unreadable_video_keeps_probe_error_after_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'broken.mov'
            source.write_bytes(b'not a video')
            editor = VideoEditor(source, 'media.trim')
            editor.show()
            for _ in range(100):
                QTest.qWait(50)
                if (editor.probe_process.state() == QProcess.NotRunning
                        and 'Carico' not in editor.error.text()):
                    break
            self.assertFalse(editor.ready)
            self.assertIn('moov atom not found', editor.error.text())
            editor._accept_if_valid()
            self.assertIn('moov atom not found', editor.error.text())
            editor.close()
            editor.deleteLater()
            self.app.processEvents()

    def test_rotated_phone_video_uses_displayed_dimensions_for_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'base.mp4'
            rotated = folder / 'phone.mp4'
            binary = str(ffmpeg_binary())
            subprocess.run([binary, '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=10',
                            '-t', '1', '-c:v', 'libx264', str(source)],
                           capture_output=True, timeout=30, check=True)
            subprocess.run([binary, '-hide_banner', '-loglevel', 'error',
                            '-display_rotation:v:0', '90', '-i', str(source),
                            '-c', 'copy', str(rotated)], capture_output=True,
                           timeout=30, check=True)
            editor = VideoEditor(rotated, 'media.crop')
            editor.show()
            self._wait_video(editor)
            self.assertEqual(editor.canvas.video_size, (240, 320))
            area = editor.canvas.image_rect()
            QTest.mousePress(editor.canvas, Qt.LeftButton,
                             pos=QPoint(area.left() + 30, area.top() + 40))
            QTest.mouseMove(editor.canvas,
                            QPoint(area.right() - 30, area.bottom() - 40))
            QTest.mouseRelease(editor.canvas, Qt.LeftButton,
                               pos=QPoint(area.right() - 30, area.bottom() - 40))
            options = editor.options()
            cropped, = publish_operation('media.crop', [rotated], options, folder)
            self.assertEqual(probe_video(cropped)[1:3], tuple(options['box'][2:]))
            editor.close()
            editor.deleteLater()
            self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
