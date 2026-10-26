import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
from pypdf import PdfWriter
from PySide6.QtCore import QEventLoop, QMimeData, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from convertitore.background import BackgroundController
from convertitore.drag_state import DragSample
from convertitore.window import Window


class BackgroundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_shift_drag_shows_target_and_release_hides_it(self):
        window = Window()
        controller = BackgroundController(window, start_timer=False)
        controller.handle_sample(DragSample(10, 10, True, True))
        controller.handle_sample(DragSample(30, 10, True, True))
        self.assertTrue(controller.wheel.isVisible())
        controller.handle_sample(DragSample(30, 10, False, True))
        self.assertFalse(controller.wheel.isVisible())
        controller.wheel.close()
        window.close()

    def test_release_over_wheel_waits_for_the_drop(self):
        window = Window()
        controller = BackgroundController(window, start_timer=False)
        controller.handle_sample(DragSample(10, 10, True, True))
        controller.handle_sample(DragSample(30, 10, True, True))
        center = controller.wheel.geometry().center()
        controller.handle_sample(DragSample(center.x(), center.y(), True, True))
        controller.handle_sample(DragSample(center.x(), center.y(), False, True))
        self.assertTrue(controller.wheel.isVisible())
        QTest.qWait(controller.RELEASE_GRACE_MS + 150)
        self.assertFalse(controller.wheel.isVisible())
        controller.wheel.close()
        window.close()

    def test_drop_uses_existing_converter(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.png"
            Image.new("RGB", (3, 2), "blue").save(source)
            window = Window()
            controller = BackgroundController(window, start_timer=False)
            controller.accept_drop([str(source)], "JPEG")
            loop = QEventLoop()
            controller.batch.finished.connect(loop.quit)
            QTimer.singleShot(30000, loop.quit)
            loop.exec()
            self.assertFalse(controller.batch.isRunning())
            self.assertEqual(len(controller.results), 1)
            with Image.open(controller.results[0]) as image:
                self.assertEqual(image.format, "JPEG")
            controller.wheel.close()
            window.close()

    def test_pdf_drop_uses_pdf_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'sample.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            with source.open('wb') as output:
                writer.write(output)
            window = Window()
            controller = BackgroundController(window, start_timer=False)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(source))])
            enter = QDragEnterEvent(QPoint(250, 105), Qt.CopyAction, mime,
                                    Qt.LeftButton, Qt.ShiftModifier)
            controller.wheel.dragEnterEvent(enter)
            drop = QDropEvent(QPoint(250, 105), Qt.CopyAction, mime,
                              Qt.LeftButton, Qt.ShiftModifier)
            controller.wheel.dropEvent(drop)
            self.assertTrue(drop.isAccepted())
            self.assertIsNone(controller.batch)
            QTest.qWait(controller.wheel.DROP_SETTLE_MS + 150)
            loop = QEventLoop()
            controller.batch.finished.connect(loop.quit)
            QTimer.singleShot(30000, loop.quit)
            loop.exec()
            self.assertFalse(controller.batch.isRunning())
            self.assertEqual(len(controller.results), 1)
            with Image.open(controller.results[0]) as image:
                self.assertEqual(image.format, 'PNG')
            controller.wheel.close()
            window.close()
