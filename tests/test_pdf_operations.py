import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from convertitore.input_files import InputError
from convertitore.pdf_operations import run_pdf_action


def make_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(144, 72)
    with path.open('wb') as output:
        writer.write(output)


class PdfOperationsTests(unittest.TestCase):
    def test_merge_and_split_preserve_order_and_page_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = root / 'a.pdf', root / 'b.pdf'
            make_pdf(first, 1)
            make_pdf(second, 2)
            stage = root / 'stage'
            stage.mkdir()
            merged = run_pdf_action('pdf.merge', [first, second], {}, stage)
            self.assertEqual(len(merged), 1)
            self.assertEqual(len(PdfReader(merged[0]).pages), 3)
            split = run_pdf_action('pdf.split', merged, {}, stage)
            self.assertEqual(len(split), 3)
            self.assertTrue(all(len(PdfReader(path).pages) == 1 for path in split))

    def test_rotate_extract_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'a.pdf'
            make_pdf(source, 3)
            stage = root / 'stage'
            stage.mkdir()
            rotated = run_pdf_action('pdf.rotate', [source], {'degrees': 90}, stage)
            self.assertEqual([page.rotation for page in PdfReader(rotated[0]).pages], [90, 90, 90])
            extracted = run_pdf_action('pdf.extract_pages', [source], {'pages': [3, 1]}, stage)
            self.assertEqual(len(PdfReader(extracted[0]).pages), 2)
            text = run_pdf_action('pdf.text', [source], {}, stage)
            self.assertIn('Pagina 1', text[0].read_text())

    def test_invalid_requests_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'a.pdf'
            make_pdf(source, 1)
            stage = root / 'stage'
            stage.mkdir()
            for action, sources, options in (
                ('pdf.merge', [source], {}),
                ('pdf.rotate', [source], {'degrees': 45}),
                ('pdf.extract_pages', [source], {'pages': [2]}),
                ('pdf.unknown', [source], {}),
            ):
                with self.subTest(action=action, options=options), self.assertRaises(InputError):
                    run_pdf_action(action, sources, options, stage)

    def test_lossless_optimization_does_not_increase_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'a.pdf'
            make_pdf(source, 2)
            stage = root / 'stage'
            stage.mkdir()
            result = run_pdf_action('pdf.optimize_lossless', [source], {}, stage)
            self.assertLessEqual(result[0].stat().st_size, source.stat().st_size)
            self.assertEqual(len(PdfReader(result[0]).pages), 2)
