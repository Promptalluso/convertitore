import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter

from convertitore.input_files import InputError
from convertitore.pdf_render import images_to_pdf, render_pdf_pages


class PdfRenderTests(unittest.TestCase):
    def test_two_pdf_pages_render_to_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'two.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            writer.add_blank_page(144, 72)
            with source.open('wb') as output:
                writer.write(output)
            stage = root / 'stage'
            stage.mkdir()
            images = render_pdf_pages(source, 'PNG', stage, dpi=72)
            self.assertEqual(len(images), 2)
            with Image.open(images[0]) as first, Image.open(images[1]) as second:
                self.assertEqual(first.size, (72, 72))
                self.assertEqual(second.size, (144, 72))

    def test_images_to_pdf_preserves_page_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = root / 'one.png', root / 'two.png'
            Image.new('RGB', (80, 60), 'red').save(first)
            Image.new('RGB', (120, 60), 'blue').save(second)
            stage = root / 'stage'
            stage.mkdir()
            result = images_to_pdf([first, second], stage)
            self.assertEqual(len(PdfReader(result[0]).pages), 2)

    def test_bad_render_options_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'one.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            with source.open('wb') as output:
                writer.write(output)
            stage = root / 'stage'
            stage.mkdir()
            for dpi, target in ((999, 'PNG'), (72, 'TXT')):
                with self.subTest(dpi=dpi, target=target), self.assertRaises(InputError):
                    render_pdf_pages(source, target, stage, dpi=dpi)
