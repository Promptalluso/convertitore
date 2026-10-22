import tempfile
import unittest
from pathlib import Path

from convertitore.input_files import InputError, validate_batch, validate_source


class InputTests(unittest.TestCase):
    def test_regular_png_and_batch_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.png"
            path.write_bytes(b"not-empty")
            self.assertEqual(validate_source(path), path.resolve())
            self.assertEqual(validate_batch([path]), [path.resolve()])
            with self.assertRaises(InputError):
                validate_batch([path] * 101)

    def test_symlink_empty_and_unsupported_extension_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.png"
            path.touch()
            with self.assertRaises(InputError):
                validate_source(path)
            path.write_bytes(b"not-empty")
            link = Path(tmp) / "b.png"
            try:
                link.symlink_to(path)
            except (OSError, NotImplementedError):
                pass  # Windows accounts may lack permission to create symlinks.
            else:
                with self.assertRaises(InputError):
                    validate_source(link)
            other = Path(tmp) / "c.svg"
            other.write_bytes(b"not-empty")
            with self.assertRaises(InputError):
                validate_source(other)

    def test_batch_order_and_duplicates_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.png"
            b = Path(tmp) / "b.jpg"
            a.write_bytes(b"a")
            b.write_bytes(b"b")
            self.assertEqual(validate_batch([b, a, b]), [b.resolve(), a.resolve(), b.resolve()])


class ImageConversionTests(unittest.TestCase):
    def test_transparent_png_to_jpeg_flattens_on_white(self):
        from PIL import Image
        from convertitore.image_conversion import encode_image

        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "transparent.png", Path(tmp) / "out.jpg"
            Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(source)
            encode_image(source, "JPEG", output)
            with Image.open(output) as result:
                self.assertEqual(result.format, "JPEG")
                self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))

    def test_png_and_webp_round_trip_dimensions(self):
        from PIL import Image
        from convertitore.image_conversion import encode_image

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.png"
            Image.new("RGBA", (11, 7), (12, 34, 56, 78)).save(source)
            for target in ("PNG", "WEBP"):
                output = Path(tmp) / f"out.{target.lower()}"
                encode_image(source, target, output)
                with Image.open(output) as result:
                    self.assertEqual(result.size, (11, 7))
                    self.assertEqual(result.format, target)

    def test_tiff_bmp_gif_round_trip(self):
        from PIL import Image
        from convertitore.publication import convert_and_publish

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'input.png'
            Image.new('RGB', (11, 7), 'blue').save(source)
            for target in ('TIFF', 'BMP', 'GIF', 'AVIF'):
                output = convert_and_publish(source, target, root)
                with Image.open(output) as image:
                    self.assertEqual(image.size, (11, 7))
                    self.assertEqual(image.format, target)
                png = convert_and_publish(output, 'PNG', root)
                with Image.open(png) as image:
                    self.assertEqual(image.format, 'PNG')

    def test_animated_webp_is_rejected(self):
        from PIL import Image
        from convertitore.image_conversion import encode_image

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "animated.webp"
            frames = [Image.new("RGB", (2, 2), color) for color in ("red", "blue")]
            frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, format="WEBP")
            with self.assertRaises(InputError):
                encode_image(source, "PNG", Path(tmp) / "out.png")

    def test_oversized_dimensions_are_rejected_before_load(self):
        from unittest.mock import patch
        from convertitore.image_conversion import encode_image

        class LargeImage:
            width = 10_000
            height = 5_000
            n_frames = 1
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def load(self): raise AssertionError("must not decode")

        with tempfile.TemporaryDirectory() as tmp:
            with patch("PIL.Image.open", return_value=LargeImage()):
                with self.assertRaises(InputError):
                    encode_image(Path(tmp) / "large.png", "PNG", Path(tmp) / "out.png")

    def test_metadata_is_not_copied(self):
        from PIL import Image
        from convertitore.image_conversion import encode_image

        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "tagged.jpg", Path(tmp) / "out.jpg"
            image = Image.new("RGB", (2, 2), "green")
            exif = Image.Exif()
            exif[270] = "private marker"
            image.save(source, exif=exif)
            encode_image(source, "JPEG", output)
            with Image.open(output) as result:
                self.assertNotIn("private marker", str(result.getexif()))


class PublicationTests(unittest.TestCase):
    def test_existing_output_survives_and_second_result_gets_unique_name(self):
        from PIL import Image
        from convertitore.publication import convert_and_publish

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "picture.png"
            Image.new("RGB", (3, 2), "orange").save(source)
            existing = folder / "picture-converted.jpg"
            existing.write_bytes(b"keep me")
            first = convert_and_publish(source, "JPEG", folder)
            second = convert_and_publish(source, "JPEG", folder)
            self.assertEqual(existing.read_bytes(), b"keep me")
            self.assertNotEqual(first, second)
            with Image.open(first) as image:
                self.assertEqual(image.size, (3, 2))
            with Image.open(second) as image:
                self.assertEqual(image.size, (3, 2))
            self.assertFalse(list(folder.glob(".convertitore-*")))

    def test_corrupt_image_does_not_publish_output(self):
        from convertitore.publication import convert_and_publish

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "bad.png"
            source.write_bytes(b"corrupt")
            with self.assertRaises(InputError):
                convert_and_publish(source, "PNG", folder)
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["bad.png"])

    def test_unavailable_atomic_creation_reports_error(self):
        from unittest.mock import patch
        from PIL import Image
        from convertitore.publication import convert_and_publish

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "picture.png"
            Image.new("RGB", (2, 2), "blue").save(source)
            with patch("convertitore.publication.os.link", side_effect=OSError("denied")):
                with self.assertRaises(InputError):
                    convert_and_publish(source, "PNG", folder)
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["picture.png"])
