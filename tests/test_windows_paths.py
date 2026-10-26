"""Windows file attributes: OneDrive files are reparse points but are not links."""

import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from convertitore.input_files import InputError, validate_source
from convertitore.media_engine import validate_media
from convertitore.pdf_input import validate_pdf
from convertitore.subtitle_engine import validate_subtitle

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
IO_REPARSE_TAG_CLOUD_6 = 0x9000601A   # OneDrive Files On-Demand
IO_REPARSE_TAG_SYMLINK = 0xA000000C


def _windows_info(path: Path, tag: int) -> SimpleNamespace:
    return SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_size=path.stat().st_size,
                           st_file_attributes=FILE_ATTRIBUTE_REPARSE_POINT, st_reparse_tag=tag)


class WindowsPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.files = {}
        image = root / 'foto.png'
        Image.new('RGB', (8, 8), 'white').save(image)
        self.files[validate_source] = image
        clip = root / 'clip.mp4'
        clip.write_bytes(b'0' * 64)
        self.files[validate_media] = clip
        subtitles = root / 'testo.srt'
        subtitles.write_text('1\n00:00:00,000 --> 00:00:01,000\nCiao\n', encoding='utf-8')
        self.files[validate_subtitle] = subtitles
        document = root / 'documento.pdf'
        document.write_bytes(b'%PDF-1.4\n%%EOF\n')
        self.files[validate_pdf] = document

    def tearDown(self):
        self.tmp.cleanup()

    def test_onedrive_files_are_accepted_as_regular_files(self):
        for validate, path in self.files.items():
            with self.subTest(validate=validate.__name__):
                with mock.patch.object(Path, 'lstat',
                                       return_value=_windows_info(path, IO_REPARSE_TAG_CLOUD_6)):
                    try:
                        validate(path)
                    except InputError as exc:
                        self.assertNotIn('collegamento', str(exc))

    def test_windows_symlinks_are_still_rejected(self):
        for validate, path in self.files.items():
            with self.subTest(validate=validate.__name__):
                with mock.patch.object(Path, 'lstat',
                                       return_value=_windows_info(path, IO_REPARSE_TAG_SYMLINK)):
                    with self.assertRaises(InputError):
                        validate(path)


if __name__ == '__main__':
    unittest.main()
