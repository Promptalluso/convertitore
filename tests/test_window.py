import tempfile
import wave
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from convertitore.window import Window


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for_batch(self, window):
        loop = QEventLoop()
        window.batch.finished.connect(loop.quit)
        QTimer.singleShot(8_000, loop.quit)
        loop.exec()
        self.assertFalse(window.batch.isRunning(), "batch did not finish")

    def test_png_to_jpeg_through_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "image.png"
            Image.new("RGB", (4, 3), "green").save(source)
            window = Window()
            window.add_paths([str(source)])
            window.target.setCurrentText("JPEG")
            window.start_batch()
            self.wait_for_batch(window)
            self.assertEqual(len(window.results), 1)
            with Image.open(window.results[0]) as result:
                self.assertEqual(result.format, "JPEG")
            self.assertIn("Completato", window.file_list.item(0).text())
            window.close()

    def test_wav_to_mp3_through_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'tone.wav'
            with wave.open(str(source), 'wb') as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(8000)
                output.writeframes(b'\x00\x00' * 4000)
            window = Window()
            window.add_paths([str(source)])
            window.target.setCurrentText('Converti in MP3')
            window.start_batch()
            self.wait_for_batch(window)
            self.assertEqual(len(window.results), 1)
            self.assertEqual(window.results[0].suffix, '.mp3')
            self.assertTrue(window.results[0].is_file())
            window.close()

    def test_two_pdfs_merge_through_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = []
            for name in ('one.pdf', 'two.pdf'):
                path = Path(tmp) / name
                writer = PdfWriter()
                writer.add_blank_page(72, 72)
                with path.open('wb') as output:
                    writer.write(output)
                sources.append(path)
            window = Window()
            window.add_paths([str(path) for path in sources])
            window.target.setCurrentText('Unisci PDF')
            window.start_batch()
            self.wait_for_batch(window)
            self.assertEqual(len(window.results), 1)
            self.assertEqual(len(PdfReader(window.results[0]).pages), 2)
            window.close()

    def test_pdf_page_options_are_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            with source.open('wb') as output:
                writer.write(output)
            window = Window()
            window.add_paths([str(source)])
            labels = [window.target.itemText(i) for i in range(window.target.count())]
            self.assertIn('Estrai pagine specifiche…', labels)
            self.assertIn('Crea PDF ricercabile · OCR offline', labels)
            window.close()

    def test_bad_file_does_not_stop_good_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.png"
            bad.write_bytes(b"corrupt")
            good = Path(tmp) / "good.png"
            Image.new("RGB", (2, 2), "blue").save(good)
            window = Window()
            window.add_paths([str(bad), str(good)])
            window.target.setCurrentText("WEBP")
            window.start_batch()
            self.wait_for_batch(window)
            self.assertEqual(len(window.results), 1)
            self.assertIn("Completato", window.file_list.item(1).text())
            self.assertNotIn("Completato", window.file_list.item(0).text())
            window.close()
