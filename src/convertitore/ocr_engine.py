"""Offline OCR for bounded local PDFs and still images."""

import io
import os
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .input_files import InputError, MAX_PIXELS, validate_source
from .pdf_input import open_pdf

MAX_OCR_PAGES = 100
MAX_OCR_TEXT = 25 * 1024 * 1024


def _engine():
    os.environ['ORT_DISABLE_TELEMETRY'] = '1'
    from rapidocr import RapidOCR
    import rapidocr

    models = Path(rapidocr.__file__).resolve().parent / 'models'
    names = {
        'Det.model_path': 'PP-OCRv6_det_small.onnx',
        'Cls.model_path': 'ch_ppocr_mobile_v2.0_cls_mobile.onnx',
        'Rec.model_path': 'PP-OCRv6_rec_small.onnx',
    }
    params = {}
    for key, name in names.items():
        model = models / name
        if not model.is_file():
            raise InputError('Modelli OCR offline non presenti nel pacchetto.')
        params[key] = str(model)
    return RapidOCR(params=params)


def _recognize(engine, image: Image.Image) -> str:
    with io.BytesIO() as stream:
        with image.convert('RGB') as rgb:
            rgb.save(stream, format='PNG')
        return engine(stream.getvalue())


def _text(engine, image: Image.Image) -> str:
    return '\n'.join(_recognize(engine, image).txts or ())


def ocr_to_text(source: Path, stage: Path) -> list[Path]:
    source = Path(source)
    if not stage.is_dir() or stage.is_symlink():
        raise InputError('Cartella temporanea OCR non valida.')
    is_pdf = source.suffix.lower() == '.pdf'
    if is_pdf:
        reader = open_pdf(source)
        if len(reader.pages) > MAX_OCR_PAGES:
            raise InputError('Puoi elaborare al massimo 100 pagine con OCR.')
    else:
        validate_source(source)
    engine = _engine()
    output = stage / 'ocr.txt'
    total = 0
    with output.open('w', encoding='utf-8') as result:
        if is_pdf:
            document = pdfium.PdfDocument(str(source))
            try:
                for index in range(len(document)):
                    page = document[index]
                    try:
                        width, height = page.get_size()
                        if width * height * 4 > MAX_PIXELS:
                            raise InputError('Una pagina supera il limite OCR di 40 megapixel.')
                        bitmap = page.render(scale=2)
                        try:
                            image = bitmap.to_pil()
                            try:
                                text = _text(engine, image)
                            finally:
                                image.close()
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
                    chunk = f'--- Pagina {index + 1} ---\n{text}\n\n'
                    total += len(chunk.encode('utf-8'))
                    if total > MAX_OCR_TEXT:
                        raise InputError('Il testo OCR supera 25 MiB.')
                    result.write(chunk)
            finally:
                document.close()
        else:
            with Image.open(source) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise InputError('L’immagine supera il limite OCR di 40 megapixel.')
                chunk = _text(engine, image) + '\n'
            if len(chunk.encode('utf-8')) > MAX_OCR_TEXT:
                raise InputError('Il testo OCR supera 25 MiB.')
            result.write(chunk)
    return [output]


def ocr_searchable_pdf(source: Path, stage: Path) -> list[Path]:
    reader = open_pdf(source)
    if len(reader.pages) > MAX_OCR_PAGES:
        raise InputError('Puoi elaborare al massimo 100 pagine con OCR.')
    engine = _engine()
    writer = PdfWriter()
    document = pdfium.PdfDocument(str(source))
    try:
        for index, original in enumerate(reader.pages):
            page = document[index]
            try:
                width, height = page.get_size()
                if width * height * 4 > MAX_PIXELS:
                    raise InputError('Una pagina supera il limite OCR di 40 megapixel.')
                bitmap = page.render(scale=2)
                try:
                    image = bitmap.to_pil()
                    try:
                        recognized = _recognize(engine, image)
                        pixel_width, pixel_height = image.size
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
            overlay_bytes = io.BytesIO()
            overlay = canvas.Canvas(overlay_bytes, pagesize=(width, height))
            for text, box in zip(recognized.txts or (),
                                 recognized.boxes if recognized.boxes is not None else ()):
                x = min(point[0] for point in box) * width / pixel_width
                y = height - max(point[1] for point in box) * height / pixel_height
                line_height = (max(point[1] for point in box) - min(point[1] for point in box)) * height / pixel_height
                object_ = overlay.beginText(max(0, x), max(0, y))
                object_.setTextRenderMode(3)
                object_.setFont('Helvetica', max(1, min(72, line_height * 0.8)))
                object_.textLine(text)
                overlay.drawText(object_)
            overlay.showPage()
            overlay.save()
            overlay_bytes.seek(0)
            overlay_page = PdfReader(overlay_bytes).pages[0]
            writer.add_page(original)
            writer.pages[-1].merge_page(overlay_page)
    finally:
        document.close()
    output = stage / 'searchable.pdf'
    with output.open('wb') as result:
        writer.write(result)
    return [output]
