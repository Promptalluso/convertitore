"""Stage an image and publish it without replacing an existing file."""

import os
import tempfile
from pathlib import Path

from .image_conversion import encode_image
from .input_files import InputError, validate_source

MAX_OUTPUT = 512 * 1024 * 1024
EXTENSIONS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp",
              "TIFF": "tiff", "BMP": "bmp", "GIF": "gif", "AVIF": "avif"}


def convert_and_publish(source: Path, target: str, output_dir: Path) -> Path:
    source = validate_source(source)
    folder = Path(output_dir)
    if target not in EXTENSIONS:
        raise InputError("Formato di uscita non supportato.")
    if (not folder.is_absolute() or not folder.is_dir() or folder.is_symlink()
            or (os.name == "nt" and str(folder).startswith("\\\\"))):
        raise InputError("Scegli una cartella locale esistente per i risultati.")
    folder = folder.resolve(strict=True)

    try:
        with tempfile.TemporaryDirectory(prefix=".convertitore-", dir=folder) as temp:
            stage = Path(temp) / "output"
            encode_image(source, target, stage)
            if not stage.is_file() or not 0 < stage.stat().st_size <= MAX_OUTPUT:
                raise InputError("Il risultato è vuoto o supera 512 MiB.")
            stem = source.stem[:100] + "-converted"
            for index in range(1, 10001):
                suffix = "" if index == 1 else f"-{index}"
                result = folder / f"{stem}{suffix}.{EXTENSIONS[target]}"
                try:
                    os.link(stage, result)
                    return result
                except FileExistsError:
                    continue
                except OSError as exc:
                    raise InputError("Usa una cartella locale che supporti la creazione sicura dei file.") from exc
            raise InputError("Troppi risultati con lo stesso nome nella cartella.")
    except OSError as exc:
        raise InputError("Impossibile scrivere nella cartella dei risultati.") from exc
