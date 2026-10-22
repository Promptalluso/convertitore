"""Small local photo editor for actions that need a visual choice."""

from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QColorDialog, QDialog, QHBoxLayout, QLabel,
                               QComboBox, QFileDialog, QLineEdit, QPushButton,
                               QSlider, QVBoxLayout, QWidget)

from . import theme
from .image_operations import adjust_pixels, background_surface
from .input_files import InputError, validate_source


class PhotoCanvas(QWidget):
    selection_changed = Signal()

    def __init__(self, path: Path, mode: str):
        super().__init__()
        self.mode = mode
        with Image.open(path) as raw:
            with ImageOps.exif_transpose(raw) as oriented:
                self.original_size = oriented.size
                self.preview = oriented.convert('RGBA')
                self.preview.thumbnail((620, 400), Image.Resampling.LANCZOS)
        self.setMinimumSize(640, 420)
        self.start: QPoint | None = None
        self.end: QPoint | None = None
        self.adjustments = {'exposure': 0, 'brightness': 100, 'contrast': 100,
                            'highlights': 0, 'shadows': 0, 'saturation': 100,
                            'sharpness': 100}
        self.background = '#FFFFFF'
        self.background_style = 'solid'
        self.background_path = ''
        self.padding = 12

    def _area(self) -> QRect:
        scale = min((self.width() - 20) / self.preview.width,
                    (self.height() - 20) / self.preview.height)
        width = round(self.preview.width * scale)
        height = round(self.preview.height * scale)
        return QRect((self.width() - width) // 2,
                     (self.height() - height) // 2, width, height)

    def _point(self, point: QPoint) -> QPoint:
        area = self._area()
        return QPoint(max(area.left(), min(point.x(), area.right())),
                      max(area.top(), min(point.y(), area.bottom())))

    def selected_box(self) -> list[int] | None:
        if self.start is None or self.end is None:
            return None
        area = self._area()
        selected = QRect(self.start, self.end).normalized().intersected(area)
        if selected.width() < 3 or selected.height() < 3:
            return None
        scale_x = self.original_size[0] / area.width()
        scale_y = self.original_size[1] / area.height()
        return [round((selected.left() - area.left()) * scale_x),
                round((selected.top() - area.top()) * scale_y),
                min(self.original_size[0], round((selected.right() + 1 - area.left()) * scale_x)),
                min(self.original_size[1], round((selected.bottom() + 1 - area.top()) * scale_y))]

    def selected_point(self) -> tuple[int, int] | None:
        if self.start is None:
            return None
        area = self._area()
        return (min(self.original_size[0] - 1,
                    round((self.start.x() - area.left()) * self.original_size[0] / area.width())),
                min(self.original_size[1] - 1,
                    round((self.start.y() - area.top()) * self.original_size[1] / area.height())))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._area().contains(event.position().toPoint()):
            self.start = self._point(event.position().toPoint())
            self.end = self.start
            self.update()

    def mouseMoveEvent(self, event):
        if self.start is not None and event.buttons() & Qt.LeftButton:
            self.end = self._point(event.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start is not None:
            self.end = self._point(event.position().toPoint())
            self.selection_changed.emit()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.qcolor(theme.tokens().canvas))
        painter.drawRoundedRect(QRectF(self.rect()), 14, 14)
        image = self.preview.copy()
        if self.mode == 'image.adjust':
            changed = adjust_pixels(image, self.adjustments)
            image.close()
            image = changed
        if self.mode == 'image.add_background':
            margin = round(min(image.size) * self.padding / 100)
            options = {'style': self.background_style, 'color': self.background,
                       'background_path': self.background_path}
            try:
                board = background_surface((image.width + 2 * margin,
                                            image.height + 2 * margin), options).convert('RGBA')
            except (InputError, OSError):
                board = Image.new('RGBA', (image.width + 2 * margin,
                                           image.height + 2 * margin), self.background)
            board.alpha_composite(image, (margin, margin))
            image.close()
            image = board
        data = image.tobytes('raw', 'RGBA')
        qt_image = QImage(data, image.width, image.height, image.width * 4,
                          QImage.Format_RGBA8888).copy()
        painter.drawPixmap(self._area(), QPixmap.fromImage(qt_image))
        if self.start is not None and self.end is not None:
            painter.setPen(QPen(QColor('#ffffff'), 2, Qt.DashLine))
            if self.mode == 'image.annotate':
                painter.drawEllipse(self.start, 5, 5)
            elif self.mode in ('image.crop', 'image.redact'):
                painter.fillRect(QRect(self.start, self.end).normalized(), QColor(10, 26, 44, 75))
                painter.drawRect(QRect(self.start, self.end).normalized())
        image.close()


class ImageEditor(QDialog):
    GLASS_SURFACE = True

    def __init__(self, path: Path, action: str, parent=None):
        super().__init__(parent)
        theme.prepare_surface(self)
        self.action = action
        self.setWindowTitle({'image.adjust': 'Modifica foto',
                             'image.add_background': 'Aggiungi sfondo',
                             'image.crop': 'Ritaglia',
                             'image.redact': 'Oscura area',
                             'image.annotate': 'Annota foto'}[action])
        self.canvas = PhotoCanvas(path, action)
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.sliders: dict[str, QSlider] = {}
        if action == 'image.adjust':
            for label, key in (('Esposizione', 'exposure'), ('Luminosità', 'brightness'),
                               ('Contrasto', 'contrast'), ('Luci', 'highlights'),
                               ('Ombre', 'shadows'), ('Saturazione', 'saturation'),
                               ('Nitidezza', 'sharpness')):
                row = QHBoxLayout()
                title = QLabel(label)
                title.setFixedWidth(95)
                slider = QSlider(Qt.Horizontal)
                if key in ('exposure', 'highlights', 'shadows'):
                    slider.setRange(-100, 100)
                    slider.setValue(0)
                else:
                    slider.setRange(0, 200)
                    slider.setValue(100)
                self.sliders[key] = slider
                row.addWidget(title)
                row.addWidget(slider)
                layout.addLayout(row)
                slider.valueChanged.connect(self._refresh)
        elif action == 'image.add_background':
            row = QHBoxLayout()
            self.style = QComboBox()
            self.style.addItems(['Colore', 'Sfumatura', 'Immagine'])
            self.style.currentIndexChanged.connect(self._choose_style)
            row.addWidget(self.style)
            color = QPushButton('Scegli colore…')
            color.clicked.connect(self._choose_color)
            row.addWidget(color)
            image_button = QPushButton('Scegli immagine…')
            image_button.clicked.connect(self._choose_background_image)
            row.addWidget(image_button)
            row.addWidget(QLabel('Margine'))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(12)
            slider.valueChanged.connect(self._refresh)
            self.sliders['padding'] = slider
            row.addWidget(slider)
            layout.addLayout(row)
        elif action == 'image.annotate':
            self.text = QLineEdit()
            self.text.setPlaceholderText('Scrivi il testo, poi clicca sull’immagine')
            self.text.setMaxLength(200)
            layout.addWidget(self.text)
        else:
            layout.addWidget(QLabel('Trascina sull’immagine per scegliere l’area.'))
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        apply = QPushButton('Applica')
        apply.setDefault(True)
        apply.clicked.connect(self._accept_if_valid)
        buttons.addWidget(cancel)
        buttons.addWidget(apply)
        layout.addLayout(buttons)

    def _choose_color(self):
        color = QColorDialog.getColor(QColor(self.canvas.background), self)
        if color.isValid():
            self.canvas.background = color.name()
            self.canvas.update()

    def _choose_background_image(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Immagine di sfondo', '',
                                              'Immagini (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp *.avif)')
        if path:
            try:
                validate_source(Path(path))
            except (InputError, OSError):
                return
            self.canvas.background_path = path
            self.canvas.background_style = 'image'
            self.style.setCurrentIndex(2)
            self.canvas.update()

    def _choose_style(self, index):
        if index == 2 and not self.canvas.background_path:
            self._choose_background_image()
            if not self.canvas.background_path:
                self.style.setCurrentIndex(0)
            return
        self.canvas.background_style = ('solid', 'gradient', 'image')[index]
        self.canvas.update()

    def _refresh(self):
        if self.action == 'image.adjust':
            self.canvas.adjustments = {key: slider.value()
                                       for key, slider in self.sliders.items()}
        else:
            self.canvas.padding = self.sliders['padding'].value()
        self.canvas.update()

    def _accept_if_valid(self):
        if self.action in ('image.crop', 'image.redact') and not self.canvas.selected_box():
            return
        if self.action == 'image.annotate' and (not self.text.text().strip()
                                                or self.canvas.selected_point() is None):
            return
        self.accept()

    def options(self) -> dict:
        if self.action == 'image.adjust':
            return {key: slider.value() for key, slider in self.sliders.items()}
        if self.action == 'image.add_background':
            return {'style': self.canvas.background_style,
                    'color': self.canvas.background,
                    'background_path': self.canvas.background_path,
                    'padding': self.sliders['padding'].value()}
        if self.action in ('image.crop', 'image.redact'):
            return {'box': self.canvas.selected_box()}
        x, y = self.canvas.selected_point()
        return {'text': self.text.text().strip(), 'x': x, 'y': y}
