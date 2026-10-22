import tempfile
import unittest
from pathlib import Path

from PIL import Image

from convertitore.input_files import InputError
from convertitore.operation_publication import publish_operation


class ImageOperationTests(unittest.TestCase):
    def test_photo_actions_create_expected_pixels_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.png'
            Image.new('RGBA', (100, 80), (200, 40, 20, 128)).save(source)
            background = publish_operation('image.add_background', [source],
                                           {'color': '#FFFFFF', 'padding': 10}, root)[0]
            with Image.open(background) as image:
                self.assertEqual(image.size, (116, 96))
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
            gradient = publish_operation('image.add_background', [source],
                                         {'style': 'gradient', 'color': '#0000FF',
                                          'padding': 10}, root)[0]
            with Image.open(gradient) as image:
                self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
                self.assertEqual(image.getpixel((0, 95)), (255, 255, 255))
            redacted = publish_operation('image.redact', [source],
                                         {'box': [10, 10, 40, 40]}, root)[0]
            with Image.open(redacted) as image:
                self.assertEqual(image.getpixel((20, 20)), (0, 0, 0, 255))
            annotated = publish_operation('image.annotate', [source],
                                          {'text': 'Test', 'x': 5, 'y': 5}, root)[0]
            with Image.open(annotated) as image:
                self.assertEqual(image.size, (100, 80))
            metadata = publish_operation('image.metadata', [source], {}, root)[0]
            self.assertIn('Dimensioni: 100 × 80', metadata.read_text(encoding='utf-8'))

    def test_resize_rotate_crop_and_compress(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'image.png'
            Image.new('RGB', (100, 80), 'red').save(source)
            cases = (
                ('image.resize', {'percent': 50}, (50, 40), 'PNG'),
                ('image.rotate', {'degrees': 90}, (80, 100), 'PNG'),
                ('image.crop', {'box': [10, 10, 60, 50]}, (50, 40), 'PNG'),
                ('image.compress', {'quality': 70}, (100, 80), 'WEBP'),
            )
            for action, options, size, format_ in cases:
                result = publish_operation(action, [source], options, root)[0]
                with Image.open(result) as image:
                    self.assertEqual(image.size, size)
                    self.assertEqual(image.format, format_)
            with self.assertRaises(InputError):
                publish_operation('image.crop', [source], {'box': [0, 0, 101, 80]}, root)


if __name__ == '__main__':
    unittest.main()
