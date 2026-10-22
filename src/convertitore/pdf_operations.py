"""Bounded local PDF operations; output paths remain inside a worker stage."""

import shutil
from pathlib import Path

from pypdf import PdfWriter

from .input_files import InputError
from .pdf_input import MAX_PDF_PAGES, open_pdf

MAX_TEXT_BYTES = 25 * 1024 * 1024


def _one(sources: list[Path]) -> Path:
    if len(sources) != 1:
        raise InputError('Questa operazione richiede un solo PDF.')
    return sources[0]


def _write(writer: PdfWriter, path: Path) -> list[Path]:
    with path.open('wb') as output:
        writer.write(output)
    if not path.is_file() or path.stat().st_size == 0:
        raise InputError('Il risultato PDF è vuoto.')
    return [path]


def run_pdf_action(action: str, sources: list[Path], options: dict,
                   stage_dir: Path) -> list[Path]:
    if not stage_dir.is_dir() or stage_dir.is_symlink():
        raise InputError('Cartella temporanea non valida.')
    if not isinstance(options, dict):
        raise InputError('Parametri PDF non validi.')
    if action == 'pdf.merge':
        if not 2 <= len(sources) <= 100:
            raise InputError('Seleziona da 2 a 100 PDF da unire.')
        writer = PdfWriter()
        total = 0
        for source in sources:
            reader = open_pdf(source)
            total += len(reader.pages)
            if total > MAX_PDF_PAGES:
                raise InputError('L’unione supera 500 pagine.')
            writer.append(reader, import_outline=False)
        return _write(writer, stage_dir / 'merged.pdf')

    source = _one(sources)
    reader = open_pdf(source)
    if action == 'pdf.split':
        outputs = []
        for index, page in enumerate(reader.pages, 1):
            writer = PdfWriter()
            writer.add_page(page)
            outputs.extend(_write(writer, stage_dir / f'page-{index:03d}.pdf'))
        return outputs
    if action == 'pdf.extract_pages':
        pages = options.get('pages')
        if (not isinstance(pages, list) or not pages or len(pages) > MAX_PDF_PAGES
                or any(type(page) is not int or not 1 <= page <= len(reader.pages)
                       for page in pages)):
            raise InputError('Indica numeri di pagina validi a partire da 1.')
        writer = PdfWriter()
        for page in pages:
            writer.add_page(reader.pages[page - 1])
        return _write(writer, stage_dir / 'selected-pages.pdf')
    if action == 'pdf.rotate':
        degrees = options.get('degrees')
        if type(degrees) is not int or degrees not in (90, 180, 270):
            raise InputError('Scegli una rotazione di 90, 180 o 270 gradi.')
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page).rotate(degrees)
        return _write(writer, stage_dir / 'rotated.pdf')
    if action == 'pdf.text':
        pages = options.get('pages', list(range(1, len(reader.pages) + 1)))
        if (not isinstance(pages, list) or not pages or len(pages) > MAX_PDF_PAGES
                or any(type(page) is not int or not 1 <= page <= len(reader.pages)
                       for page in pages)):
            raise InputError('Scegli pagine PDF valide per il testo.')
        path = stage_dir / 'text.txt'
        total = 0
        with path.open('w', encoding='utf-8') as output:
            for index in pages:
                content = f'--- Pagina {index} ---\n{reader.pages[index - 1].extract_text() or ""}\n\n'
                total += len(content.encode('utf-8'))
                if total > MAX_TEXT_BYTES:
                    raise InputError('Il testo estratto supera 25 MiB.')
                output.write(content)
        return [path]
    if action == 'pdf.compress_images':
        quality = options.get('quality')
        if type(quality) is not int or not 40 <= quality <= 90:
            raise InputError('Scegli una qualità PDF da 40 a 90.')
        writer = PdfWriter()
        writer.append(reader, import_outline=False)
        try:
            for page in writer.pages:
                for image in page.images:
                    image.replace(image.image, quality=quality)
            writer.compress_identical_objects(remove_duplicates=True,
                                              remove_unreferenced=True)
        except (OSError, ValueError, NotImplementedError) as exc:
            raise InputError('Questo PDF contiene immagini non comprimibili.') from exc
        path = stage_dir / 'compressed.pdf'
        _write(writer, path)
        if path.stat().st_size > source.stat().st_size:
            shutil.copyfile(source, path)
        return [path]
    if action == 'pdf.optimize_lossless':
        writer = PdfWriter()
        writer.append(reader, import_outline=False)
        for page in writer.pages:
            page.compress_content_streams()
        writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
        path = stage_dir / 'optimized.pdf'
        _write(writer, path)
        if path.stat().st_size > source.stat().st_size:
            shutil.copyfile(source, path)
        return [path]
    raise InputError('Operazione PDF non supportata.')
