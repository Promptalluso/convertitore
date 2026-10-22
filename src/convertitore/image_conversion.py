"""Decode one still image and write a new PNG, JPEG or WebP file."""

from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from .input_files import InputError, MAX_PIXELS

TARGETS = frozenset({"PNG", "JPEG", "WEBP", "TIFF", "BMP", "GIF", "AVIF"})


def encode_image(source: Path, target: str, stage: Path) -> None:
    if target not in TARGETS:
        raise InputError("Formato di uscita non supportato.")
    try:
        with Image.open(source) as original:
            if getattr(original, "n_frames", 1) != 1:
                raise InputError("Le immagini animate o con più pagine non sono supportate.")
            if original.width * original.height > MAX_PIXELS:
                raise InputError("L'immagine supera il limite di 40 megapixel.")
            original.load()
            with ImageOps.exif_transpose(original) as oriented:
                with oriented.convert("RGBA") as pixels:
                    if target in ("JPEG", "BMP", "GIF"):
                        with Image.new("RGB", pixels.size, "white") as result:
                            result.paste(pixels, mask=pixels.getchannel("A"))
                            if target == "GIF":
                                result.save(stage, format="GIF")
                            elif target == "BMP":
                                result.save(stage, format="BMP")
                            else:
                                result.save(stage, format="JPEG", quality=90)
                    else:
                        # A new pixel image drops the source's EXIF and ancillary info.
                        with Image.new("RGBA", pixels.size) as result:
                            result.paste(pixels)
                            if target == "TIFF":
                                result.save(stage, format="TIFF", compression="tiff_deflate")
                            else:
                                result.save(stage, format=target, quality=90)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise InputError("Impossibile leggere o convertire l'immagine.") from exc
