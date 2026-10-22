import tempfile
import unittest
from pathlib import Path

from convertitore.input_files import InputError
from convertitore.operation_publication import publish_operation


class SubtitleTests(unittest.TestCase):
    def test_srt_vtt_round_trip_and_plain_text(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            original = folder / 'sample.srt'
            original.write_text('1\n00:00:01,000 --> 00:00:02,500\nCiao mondo\n\n'
                                '2\n00:00:03,000 --> 00:00:04,000\nSeconda riga\n',
                                encoding='utf-8')
            vtt, = publish_operation('subtitle.convert', [original], {'target': 'VTT'}, folder)
            self.assertTrue(vtt.read_text(encoding='utf-8').startswith('WEBVTT\n\n'))
            srt, = publish_operation('subtitle.convert', [vtt], {'target': 'SRT'}, folder)
            self.assertIn('00:00:01,000 --> 00:00:02,500', srt.read_text(encoding='utf-8'))
            plain, = publish_operation('subtitle.convert', [vtt], {'target': 'TXT'}, folder)
            self.assertEqual(plain.read_text(encoding='utf-8'), 'Ciao mondo\n\nSeconda riga\n')

    def test_invalid_timestamp_is_rejected_without_published_result(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            original = folder / 'invalid.srt'
            original.write_text('1\n00:99:01,000 --> 00:00:02,000\nCiao\n', encoding='utf-8')
            with self.assertRaises(InputError):
                publish_operation('subtitle.convert', [original], {'target': 'VTT'}, folder)
            self.assertEqual(list(folder.iterdir()), [original])


if __name__ == '__main__':
    unittest.main()
