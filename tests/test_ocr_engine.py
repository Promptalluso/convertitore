"""Exercise offline OCR using the models shipped by RapidOCR."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from convertitore.operation_publication import publish_operation


class OcrEngineTests(unittest.TestCase):
    def test_image_to_text_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = Image.new('RGB', (1000, 260), 'white')
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default(size=72)
            draw.text((50, 60), 'HELLO WORLD 123', fill='black', font=font)
            source = root / 'scan.png'
            image.save(source)
            outputs = publish_operation('ocr.text', [source], {}, root)
            content = outputs[0].read_text(encoding='utf-8')
            self.assertIn('HELLO', content)
            self.assertIn('WORLD', content)

    def test_scanned_pdf_to_text_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = Image.new('RGB', (1000, 260), 'white')
            ImageDraw.Draw(image).text((50, 60), 'HELLO WORLD 123', fill='black',
                                       font=ImageFont.load_default(size=72))
            source = root / 'scan.pdf'
            image.save(source, format='PDF', resolution=72)
            outputs = publish_operation('ocr.text', [source], {}, root)
            content = outputs[0].read_text(encoding='utf-8')
            self.assertIn('Pagina 1', content)
            self.assertIn('HELLO', content)

    def test_scanned_pdf_becomes_searchable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = Image.new('RGB', (1000, 260), 'white')
            ImageDraw.Draw(image).text((50, 60), 'HELLO WORLD 123', fill='black',
                                       font=ImageFont.load_default(size=72))
            source = root / 'scan.pdf'
            image.save(source, format='PDF', resolution=72)
            self.assertFalse(PdfReader(source).pages[0].extract_text())
            outputs = publish_operation('ocr.searchable_pdf', [source], {}, root)
            self.assertIn('HELLO', PdfReader(outputs[0]).pages[0].extract_text())


if __name__ == '__main__':
    unittest.main()
