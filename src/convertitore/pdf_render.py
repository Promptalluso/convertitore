"""Convert between local PDFs and bounded still images."""

import math
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from .input_files import InputError, MAX_PIXELS, validate_batch
from .pdf_input import open_pdf

MAX_RENDER_PAGES = 100


def render_pdf_pages(source: Path, target: str, stage_dir: Path,
                     dpi: int = 144) -> list[Path]:
    if target not in ('PNG', 'JPEG', 'WEBP'):
        raise InputError('Scegli PNG, JPEG o WebP per le pagine PDF.')
    if type(dpi) is not int or not 72 <= dpi <= 200:
        raise InputError('Scegli una risoluzione da 72 a 200 DPI.')
    reader = open_pdf(source)
    if len(reader.pages) > MAX_RENDER_PAGES:
        raise InputError('Puoi esportare al massimo 100 pagine per volta.')
    outputs = []
    suffix = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[target]
    document = None
    try:
        document = pdfium.PdfDocument(str(source))
        for index in range(len(document)):
            page = document[index]
            try:
                width, height = page.get_size()
                scale = dpi / 72
                if (not math.isfinite(width) or not math.isfinite(height)
                        or width <= 0 or height <= 0
                        or math.ceil(width * scale) * math.ceil(height * scale) > MAX_PIXELS):
                    raise InputError('Una pagina supera il limite di 40 megapixel.')
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    try:
                        output = stage_dir / f'page-{index + 1:03d}.{suffix}'
                        if target == 'JPEG':
                            image.convert('RGB').save(output, format='JPEG', quality=90)
                        else:
                            image.save(output, format=target, quality=90)
                        outputs.append(output)
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
        return outputs
    except (OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError('Impossibile convertire le pagine PDF.') from exc
    finally:
        if document is not None:
            document.close()


def images_to_pdf(sources: list[Path], stage_dir: Path) -> list[Path]:
    paths = validate_batch(sources)
    images = []
    try:
        for path in paths:
            with Image.open(path) as original:
                if getattr(original, 'n_frames', 1) != 1:
                    raise InputError('Le immagini animate non possono diventare pagine PDF.')
                if original.width * original.height > MAX_PIXELS:
                    raise InputError('Un’immagine supera il limite di 40 megapixel.')
                original.load()
                with ImageOps.exif_transpose(original) as oriented:
                    with oriented.convert('RGBA') as rgba:
                        page = Image.new('RGB', rgba.size, 'white')
                        page.paste(rgba, mask=rgba.getchannel('A'))
                        images.append(page)
        output = stage_dir / 'images.pdf'
        images[0].save(output, format='PDF', save_all=True,
                       append_images=images[1:], resolution=72.0)
        return [output]
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise InputError('Impossibile creare il PDF dalle immagini.') from exc
    finally:
        for image in images:
            image.close()
