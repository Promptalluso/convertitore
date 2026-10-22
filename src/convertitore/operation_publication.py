"""Stage and publish one PDF operation without overwriting any output."""

import os
import stat
import tempfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from .input_files import InputError
from .pdf_operations import run_pdf_action
from .pdf_render import images_to_pdf, render_pdf_pages
from .media_engine import run_media_action, TARGET_SUFFIX
from .media_join import join_videos
from .image_operations import run_image_action
from .ocr_engine import ocr_searchable_pdf, ocr_to_text
from .subtitle_engine import convert_subtitle

MAX_OUTPUT = 512 * 1024 * 1024
ALLOWED_SUFFIXES = frozenset({'.pdf', '.txt', '.srt', '.vtt', '.png', '.jpg', '.webp', *TARGET_SUFFIX.values()})


def _validate_folder(raw: Path) -> Path:
    folder = Path(raw)
    if (not folder.is_absolute() or not folder.is_dir() or folder.is_symlink()
            or (os.name == 'nt' and str(folder).startswith('\\\\'))):
        raise InputError('Scegli una cartella locale esistente per i risultati.')
    return folder.resolve(strict=True)


def _staged(action: str, sources: list[Path], options: dict, stage: Path) -> list[Path]:
    if action == 'subtitle.convert':
        if len(sources) != 1:
            raise InputError('Seleziona un sottotitolo per volta.')
        return convert_subtitle(sources[0], options.get('target'), stage)
    if action.startswith('image.'):
        if len(sources) != 1:
            raise InputError('Seleziona un’immagine per volta.')
        return run_image_action(action, sources[0], options, stage)
    if action == 'ocr.text':
        if len(sources) != 1:
            raise InputError('Seleziona un PDF o un’immagine per l’OCR.')
        return ocr_to_text(sources[0], stage)
    if action == 'ocr.searchable_pdf':
        if len(sources) != 1:
            raise InputError('Seleziona un PDF per l’OCR.')
        return ocr_searchable_pdf(sources[0], stage)
    if action.startswith('media.'):
        if action == 'media.join':
            return join_videos(sources, stage)
        if len(sources) != 1:
            raise InputError('Seleziona un file audio o video per volta.')
        return run_media_action(action, sources[0], options, stage)
    if action == 'pdf.to_images':
        if len(sources) != 1:
            raise InputError('Seleziona un PDF da esportare in immagini.')
        return render_pdf_pages(sources[0], options.get('target', 'PNG'), stage,
                                options.get('dpi', 144))
    if action == 'pdf.from_images':
        return images_to_pdf(sources, stage)
    return run_pdf_action(action, sources, options, stage)


def _check_output(path: Path, stage: Path) -> None:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or not path.resolve(strict=True).is_relative_to(stage.resolve(strict=True))
            or not 0 < info.st_size <= MAX_OUTPUT
            or path.suffix.lower() not in ALLOWED_SUFFIXES):
        raise InputError('Risultato non valido o troppo grande.')
    if path.suffix == '.pdf':
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted or not reader.pages:
            raise InputError('Il PDF prodotto non è leggibile.')
    elif path.suffix in ('.txt', '.srt', '.vtt'):
        path.read_text(encoding='utf-8')
    elif path.suffix in ('.png', '.jpg', '.webp'):
        with Image.open(path) as image:
            image.verify()


def publish_operation(action: str, sources: list[Path], options: dict,
                      output_dir: Path) -> list[Path]:
    if not isinstance(action, str) or not 1 <= len(sources) <= 100:
        raise InputError('Operazione o numero di file non valido.')
    folder = _validate_folder(output_dir)
    prefix = Path(sources[0]).stem[:80]
    label = action.split('.')[-1].replace('_', '-')
    created = []
    try:
        with tempfile.TemporaryDirectory(prefix='.convertitore-', dir=folder) as temp:
            stage = Path(temp)
            outputs = _staged(action, [Path(source) for source in sources], options, stage)
            if not outputs or len(outputs) > 500:
                raise InputError('Numero di risultati non valido.')
            for output in outputs:
                _check_output(output, stage)
            for output in outputs:
                stem = f'{prefix}-{label}'
                if len(outputs) > 1:
                    stem += f'-{output.stem}'
                for index in range(1, 10001):
                    number = '' if index == 1 else f'-{index}'
                    result = folder / f'{stem}{number}{output.suffix.lower()}'
                    try:
                        os.link(output, result)
                        created.append(result)
                        break
                    except FileExistsError:
                        continue
                else:
                    raise InputError('Troppi risultati con lo stesso nome.')
        return created
    except Exception:
        for result in created:
            result.unlink(missing_ok=True)
        raise
