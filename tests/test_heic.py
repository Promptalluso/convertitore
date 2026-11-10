"""iPhone HEIC photos: read, rotate as shown on the phone, and drop location data."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from convertitore.input_files import MAX_PIXELS, validate_source
from convertitore.publication import convert_and_publish

ORIENTATION = 0x0112
GPS_IFD = 0x8825


def make_heic(path: Path, size=(40, 20), orientation: int | None = None,
              with_gps: bool = False) -> Path:
    image = Image.new('RGB', size, (200, 120, 40))
    image.paste((20, 60, 160), (0, 0, size[0] // 2, size[1]))
    exif = Image.Exif()
    if orientation:
        exif[ORIENTATION] = orientation
    if with_gps:
        exif[GPS_IFD] = {1: 'N', 2: (45.0, 28.0, 0.0), 3: 'E', 4: (9.0, 11.0, 0.0)}
    image.save(path, format='HEIF', exif=exif.tobytes() if (orientation or with_gps) else None)
    return path


class HeicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_heic_is_a_supported_photo(self):
        for suffix in ('.heic', '.HEIC', '.heif'):
            with self.subTest(suffix=suffix):
                path = make_heic(self.root / f'foto{suffix}')
                self.assertEqual(validate_source(path), path.resolve())

    def test_heic_converts_to_jpeg_and_png(self):
        source = make_heic(self.root / 'IMG_0001.heic')
        for target, fmt in (('JPEG', 'JPEG'), ('PNG', 'PNG'), ('WEBP', 'WEBP')):
            with self.subTest(target=target):
                output = convert_and_publish(source, target, self.root)
                with Image.open(output) as image:
                    self.assertEqual(image.format, fmt)
                    self.assertEqual(image.size, (40, 20))

    def test_rotated_iphone_photo_keeps_its_orientation(self):
        # Orientation 6: stored landscape, shown portrait on the phone.
        source = make_heic(self.root / 'ritratto.heic', orientation=6)
        output = convert_and_publish(source, 'JPEG', self.root)
        with Image.open(output) as image:
            self.assertEqual(image.size, (20, 40))
            self.assertNotEqual(image.getexif().get(ORIENTATION, 1), 6)

    def test_location_is_not_copied_to_the_jpeg(self):
        source = make_heic(self.root / 'vacanza.heic', with_gps=True)
        with Image.open(source) as original:
            self.assertIn(GPS_IFD, original.getexif())
        output = convert_and_publish(source, 'JPEG', self.root)
        with Image.open(output) as image:
            self.assertNotIn(GPS_IFD, image.getexif())

    def test_48_megapixel_photos_fit_the_limit(self):
        self.assertGreaterEqual(MAX_PIXELS, 8064 * 6048)


if __name__ == '__main__':
    unittest.main()
