"""Page preview and selection for PDF page and text extraction."""

from pathlib import Path

import pypdfium2 as pdfium
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                               QListWidget, QPushButton, QSpinBox, QVBoxLayout)

from . import theme
from .input_files import InputError
from .pdf_input import open_pdf


def page_preview(path: Path, number: int) -> QPixmap:
    document = None
    try:
        document = pdfium.PdfDocument(str(path))
        page = document[number - 1]
        try:
            width, height = page.get_size()
            if width <= 0 or height <= 0:
                raise InputError('Dimensioni della pagina PDF non valide.')
            scale = min(1.2, 480 / width, 520 / height)
            if not 0 < scale <= 1.2:
                raise InputError('Dimensioni della pagina PDF non valide.')
            bitmap = page.render(scale=scale)
            try:
                with bitmap.to_pil() as source:
                    with source.convert('RGB') as image:
                        pixels = image.tobytes('raw', 'RGB')
                        result = QImage(pixels, image.width, image.height,
                                        image.width * 3, QImage.Format_RGB888).copy()
                        return QPixmap.fromImage(result)
            finally:
                bitmap.close()
        finally:
            page.close()
    except (OSError, RuntimeError, ValueError) as exc:
        raise InputError('Impossibile mostrare l’anteprima PDF.') from exc
    finally:
        if document is not None:
            document.close()


class PdfPageEditor(QDialog):
    GLASS_SURFACE = True

    def __init__(self, path: Path, action: str, parent=None):
        super().__init__(parent)
        theme.prepare_surface(self)
        if action not in ('pdf.extract_pages', 'pdf.text'):
            raise ValueError('Azione PDF non supportata.')
        self.path = path
        self.action = action
        self.page_count = len(open_pdf(path).pages)
        self.pages: list[int] = []
        self.setWindowTitle('Scegli pagine PDF' if action == 'pdf.extract_pages'
                            else 'Estrai testo dalle pagine')
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        left = QVBoxLayout()
        layout.addLayout(left, 3)
        self.preview = QLabel()
        self.preview.setFixedSize(500, 540)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet(f'background: {theme.tokens().canvas}; border-radius: 14px;')
        left.addWidget(self.preview)
        pager = QHBoxLayout()
        pager.addWidget(QLabel('Pagina'))
        self.number = QSpinBox()
        self.number.setRange(1, self.page_count)
        self.number.valueChanged.connect(self._show_page)
        pager.addWidget(self.number)
        pager.addWidget(QLabel(f'di {self.page_count}'))
        pager.addStretch()
        left.addLayout(pager)
        right = QVBoxLayout()
        layout.addLayout(right, 2)
        right.addWidget(QLabel('Pagine selezionate, nell’ordine desiderato'))
        self.selected = QListWidget()
        self.selected.setMinimumWidth(240)
        right.addWidget(self.selected, 1)
        add = QPushButton('Aggiungi pagina mostrata')
        add.clicked.connect(self._add)
        right.addWidget(add)
        remove = QPushButton('Rimuovi selezionata')
        remove.clicked.connect(self._remove)
        right.addWidget(remove)
        self.error = QLabel('')
        self.error.setObjectName('error')
        right.addWidget(self.error)
        buttons = QHBoxLayout()
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        apply = QPushButton('Estrai')
        apply.setDefault(True)
        apply.clicked.connect(self._accept_if_valid)
        buttons.addWidget(cancel)
        buttons.addWidget(apply)
        right.addLayout(buttons)
        self._show_page(1)
        self.adjustSize()
        pointer = QCursor.pos()
        screen = QApplication.screenAt(pointer) or QApplication.primaryScreen()
        if screen:
            bounds = screen.availableGeometry()
            self.move(max(bounds.left(), min(pointer.x() + 20, bounds.right() - self.width())),
                      max(bounds.top(), min(pointer.y() + 20, bounds.bottom() - self.height())))

    def _show_page(self, number: int):
        try:
            image = page_preview(self.path, number)
            self.preview.setPixmap(image)
            self.error.setText('')
        except InputError as exc:
            self.preview.clear()
            self.error.setText(str(exc))

    def _add(self):
        number = self.number.value()
        if number not in self.pages:
            self.pages.append(number)
            self.selected.addItem(f'Pagina {number}')

    def _remove(self):
        row = self.selected.currentRow()
        if row >= 0:
            self.pages.pop(row)
            self.selected.takeItem(row)

    def _accept_if_valid(self):
        if self.pages:
            self.accept()
        else:
            self.error.setText('Aggiungi almeno una pagina.')

    def options(self) -> dict:
        return {'pages': list(self.pages)}
