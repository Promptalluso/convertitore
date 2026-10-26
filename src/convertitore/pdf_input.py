"""Cheap PDF validation for the UI, and full checks inside the worker."""

import os
import stat
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .input_files import InputError, is_windows_link

MAX_PDF_BYTES = 250 * 1024 * 1024
MAX_PDF_PAGES = 500


def validate_pdf(raw: str | Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute() or (os.name == 'nt' and str(path).startswith('\\\\')):
        raise InputError('Scegli un PDF locale con percorso assoluto.')
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.is_symlink() or is_windows_link(info):
            raise InputError('Scegli un PDF normale, non un collegamento o una cartella.')
        if not 0 < info.st_size <= MAX_PDF_BYTES:
            raise InputError('Il PDF deve essere non vuoto e non superare 250 MiB.')
        if path.suffix.lower() != '.pdf':
            raise InputError('Il file deve avere estensione .pdf.')
        with path.open('rb') as source:
            if source.read(5) != b'%PDF-':
                raise InputError('Il file non contiene un PDF valido.')
        return path.resolve(strict=True)
    except OSError as exc:
        raise InputError('Il PDF non è accessibile.') from exc


def open_pdf(raw: str | Path) -> PdfReader:
    path = validate_pdf(raw)
    try:
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            raise InputError('Il PDF è protetto da password.')
        count = len(reader.pages)
        if not 1 <= count <= MAX_PDF_PAGES:
            raise InputError('Il PDF deve avere da 1 a 500 pagine.')
        return reader
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError('Impossibile leggere il PDF.') from exc
