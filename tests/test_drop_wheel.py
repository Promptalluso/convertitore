import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QMimeData, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from convertitore.drop_wheel import DropWheel


class DropWheelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_wheel_can_render(self):
        wheel = DropWheel()
        wheel.show()
        self.app.processEvents()
        preview = wheel.grab()
        self.assertFalse(preview.isNull())
        wheel.close()

    def test_wheel_segments_have_distinct_drop_zones(self):
        wheel = DropWheel()
        self.assertIsNone(wheel.format_at(160, 60))
        wheel.configure_for_paths(['/tmp/example.png'])
        self.assertEqual(wheel.format_at(250, 105), "WEBP")
        self.assertEqual(wheel.format_at(160, 60), "PNG")
        self.assertEqual(wheel.format_at(70, 105), "JPEG")
        self.assertEqual(wheel.format_at(247, 210), "PDF")
        self.assertIsNone(wheel.format_at(160, 160))
        self.assertIsNone(wheel.format_at(0, 0))
        wheel.close()

    def test_local_file_drop_selects_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.png"
            path.write_bytes(b"image")
            wheel = DropWheel()
            received = []
            wheel.files_dropped.connect(lambda files, target: received.append((files, target)))
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(path))])
            event = QDropEvent(QPoint(70, 105), Qt.CopyAction, mime, Qt.LeftButton, Qt.ShiftModifier)
            wheel.dropEvent(event)
            self.assertEqual(received, [])
            QTest.qWait(DropWheel.DROP_SETTLE_MS + 150)
            self.assertEqual(received, [([str(path)], "JPEG")])
            wheel.close()

    def test_pdf_drag_enter_changes_visible_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'document.pdf'
            path.write_bytes(b'%PDF-1.4')
            wheel = DropWheel()
            received = []
            wheel.files_dropped.connect(lambda files, target: received.append(target))
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(path))])
            event = QDragEnterEvent(QPoint(160, 60), Qt.CopyAction, mime,
                                    Qt.LeftButton, Qt.ShiftModifier)
            wheel.dragEnterEvent(event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(wheel.format_at(160, 60), 'JPEG')
            self.assertEqual(wheel.format_at(247, 210), 'COMPRIMI')
            move = QDragMoveEvent(QPoint(160, 160), Qt.CopyAction, mime,
                                  Qt.LeftButton, Qt.ShiftModifier)
            wheel.dragMoveEvent(move)
            self.assertTrue(move.isAccepted())
            self.assertEqual(wheel.format_at(160, 60), 'JPEG')
            QTest.qWait(450)
            self.assertEqual(wheel.format_at(160, 60), 'OTTIMIZZA')
            drop = QDropEvent(QPoint(160, 60), Qt.CopyAction, mime,
                              Qt.LeftButton, Qt.ShiftModifier)
            wheel.dropEvent(drop)
            self.assertEqual(received, [])
            QTest.qWait(DropWheel.DROP_SETTLE_MS + 150)
            self.assertEqual(received, ['OTTIMIZZA'])
            wheel.reset_context()
            self.assertIsNone(wheel.format_at(160, 60))
            wheel.close()

    def test_remote_url_is_ignored(self):
        wheel = DropWheel()
        received = []
        wheel.files_dropped.connect(lambda files, target: received.append((files, target)))
        mime = QMimeData()
        mime.setUrls([QUrl("https://example.com/file.png")])
        event = QDropEvent(QPoint(160, 60), Qt.CopyAction, mime, Qt.LeftButton, Qt.ShiftModifier)
        wheel.dropEvent(event)
        self.assertEqual(received, [])
        wheel.close()

    def test_crossing_center_briefly_keeps_current_page(self):
        wheel = DropWheel()
        wheel.configure_for_paths(['/tmp/document.pdf'])
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile('/tmp/document.pdf')])
        center = QDragMoveEvent(QPoint(160, 160), Qt.CopyAction, mime,
                                Qt.LeftButton, Qt.ShiftModifier)
        wheel.dragMoveEvent(center)
        outer = QDragMoveEvent(QPoint(160, 60), Qt.CopyAction, mime,
                               Qt.LeftButton, Qt.ShiftModifier)
        wheel.dragMoveEvent(outer)
        QTest.qWait(450)
        self.assertEqual(wheel.page_index, 0)
        self.assertEqual(wheel.format_at(160, 60), 'JPEG')
        wheel.close()

    def test_pdf_and_video_show_contextual_targets(self):
        wheel = DropWheel()
        wheel.configure_for_paths(['/tmp/example.pdf'])
        self.assertEqual(wheel.format_at(160, 60), 'JPEG')
        self.assertEqual(wheel.format_at(247, 210), 'COMPRIMI')
        wheel.configure_for_paths(['/tmp/example.mp4'])
        self.assertEqual(wheel.format_at(160, 60), 'MOV')
        self.assertEqual(wheel.format_at(247, 210), 'MP3')
        wheel.close()

    def test_photo_and_audio_action_pages(self):
        wheel = DropWheel()
        wheel.configure_for_paths(['/tmp/example.png'])
        wheel.page_index = 1
        wheel._show_page()
        self.assertEqual(wheel.format_at(160, 60), 'SFONDO')
        self.assertEqual(wheel.format_at(247, 210), 'METADATI')
        wheel.configure_for_paths(['/tmp/example.wav'])
        wheel.page_index = 1
        wheel._show_page()
        self.assertEqual(wheel.format_at(160, 60), 'STEREO')
        self.assertEqual(wheel.format_at(70, 105), 'BLEEP')
        wheel.close()


class DropActionTests(unittest.TestCase):
    def test_shift_move_drop_is_accepted_as_copy(self):
        # Windows Explorer proposes a move while Shift is held; a move would delete the source.
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.png"
            path.write_bytes(b"x")
            wheel = DropWheel()
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(path))])
            enter = QDragEnterEvent(QPoint(160, 60), Qt.CopyAction | Qt.MoveAction, mime,
                                    Qt.LeftButton, Qt.ShiftModifier)
            wheel.dragEnterEvent(enter)
            self.assertEqual(enter.dropAction(), Qt.CopyAction)
            drop = QDropEvent(QPoint(160, 60), Qt.CopyAction | Qt.MoveAction, mime,
                              Qt.LeftButton, Qt.ShiftModifier)
            drop.setDropAction(Qt.MoveAction)
            wheel.dropEvent(drop)
            self.assertTrue(drop.isAccepted())
            self.assertEqual(drop.dropAction(), Qt.CopyAction)
            wheel.close()
            app.processEvents()
