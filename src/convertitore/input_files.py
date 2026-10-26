"""Validate local files before conversion."""

import os
import stat
from pathlib import Path

MAX_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 40_000_000
SUPPORTED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".avif"})


class InputError(ValueError):
    """A selected file cannot be used by this release."""


IO_REPARSE_TAG_NAME_SURROGATE = 0x20000000


def is_windows_link(info: os.stat_result) -> bool:
    """True for Windows symlinks and junctions.

    OneDrive files are reparse points too (attribute 0x400), so that attribute alone
    would reject most files on a Windows 11 Desktop or Documents folder.
    """
    return bool(getattr(info, "st_reparse_tag", 0) & IO_REPARSE_TAG_NAME_SURROGATE)


def validate_source(raw: str | Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute() or (os.name == "nt" and str(path).startswith("\\\\")):
        raise InputError("Scegli un file locale con percorso assoluto.")
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                or is_windows_link(info)):
            raise InputError("Scegli un file normale, non un collegamento o una cartella.")
        if not 0 < info.st_size <= MAX_BYTES:
            raise InputError("Il file deve essere non vuoto e non superare 100 MiB.")
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise InputError("Formato immagine non supportato.")
        return path.resolve(strict=True)
    except OSError as exc:
        raise InputError("Il file non è accessibile.") from exc


def validate_batch(raws: list[str | Path]) -> list[Path]:
    if not 1 <= len(raws) <= 100:
        raise InputError("Seleziona da 1 a 100 file.")
    return [validate_source(raw) for raw in raws]
