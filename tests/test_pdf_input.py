import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from convertitore.input_files import InputError
from convertitore.pdf_input import MAX_PDF_PAGES, validate_pdf, open_pdf


class PdfInputTests(unittest.TestCase):
    def test_valid_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'one.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            with path.open('wb') as output:
                writer.write(output)
            self.assertEqual(validate_pdf(path), path.resolve())
            reader = open_pdf(path)
            self.assertEqual(len(reader.pages), 1)

    def test_non_pdf_and_link_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fake = folder / 'fake.pdf'
            fake.write_bytes(b'not a PDF')
            with self.assertRaises(InputError):
                validate_pdf(fake)
            target = folder / 'one.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            with target.open('wb') as output:
                writer.write(output)
            link = folder / 'link.pdf'
            link.symlink_to(target)
            with self.assertRaises(InputError):
                validate_pdf(link)

    def test_encrypted_pdf_is_rejected_without_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'locked.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            writer.encrypt('secret')
            with path.open('wb') as output:
                writer.write(output)
            self.assertEqual(validate_pdf(path), path.resolve())
            with self.assertRaises(InputError):
                open_pdf(path)

    def test_page_limit_constant(self):
        self.assertGreaterEqual(MAX_PDF_PAGES, 100)
        self.assertLessEqual(MAX_PDF_PAGES, 1000)
