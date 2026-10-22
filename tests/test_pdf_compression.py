import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from convertitore.input_files import InputError
from convertitore.pdf_operations import run_pdf_action


class PdfCompressionTests(unittest.TestCase):
    def test_image_quality_mode_keeps_pdf_readable_and_no_larger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'photo.png'
            Image.effect_noise((600, 600), 70).convert('RGB').save(image)
            source = root / 'photo.pdf'
            with Image.open(image) as picture:
                picture.save(source, 'PDF', resolution=72.0)
            stage = root / 'stage'
            stage.mkdir()
            result = run_pdf_action('pdf.compress_images', [source], {'quality': 60}, stage)
            self.assertEqual(len(PdfReader(result[0]).pages), 1)
            self.assertLessEqual(result[0].stat().st_size, source.stat().st_size)

    def test_quality_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = Image.new('RGB', (20, 20), 'green')
            source = root / 'photo.pdf'
            image.save(source, 'PDF')
            stage = root / 'stage'
            stage.mkdir()
            with self.assertRaises(InputError):
                run_pdf_action('pdf.compress_images', [source], {'quality': 3}, stage)
