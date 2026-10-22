import tempfile
import threading
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from convertitore.runner import run_operation


class PdfWorkerTests(unittest.TestCase):
    def test_merge_publishes_one_pdf_without_replacing_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = []
            for name in ('first.pdf', 'second.pdf'):
                path = root / name
                writer = PdfWriter()
                writer.add_blank_page(72, 72)
                with path.open('wb') as output:
                    writer.write(output)
                inputs.append(path)
            existing = root / 'first-merged.pdf'
            existing.write_bytes(b'keep')
            outputs = run_operation('pdf.merge', inputs, {}, root, threading.Event())
            self.assertEqual(len(outputs), 1)
            self.assertNotEqual(outputs[0], existing)
            self.assertEqual(existing.read_bytes(), b'keep')
            self.assertEqual(len(PdfReader(outputs[0]).pages), 2)

    def test_split_publishes_all_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'two.pdf'
            writer = PdfWriter()
            writer.add_blank_page(72, 72)
            writer.add_blank_page(72, 72)
            with source.open('wb') as output:
                writer.write(output)
            outputs = run_operation('pdf.split', [source], {}, root, threading.Event())
            self.assertEqual(len(outputs), 2)
            self.assertTrue(all(path.exists() for path in outputs))
