"""Bounded still-image edits with metadata-free outputs."""

from pathlib import Path

from PIL import ExifTags, Image, ImageColor, ImageDraw, ImageEnhance, ImageFont, ImageOps, UnidentifiedImageError

from .input_files import InputError, MAX_PIXELS, validate_source


def adjust_pixels(pixels: Image.Image, options: dict) -> Image.Image:
    values = [options.get(key, 100) for key in
              ('brightness', 'contrast', 'saturation', 'sharpness')]
    exposure = options.get('exposure', 0)
    highlights = options.get('highlights', 0)
    shadows = options.get('shadows', 0)
    if (any(type(value) is not int or not 0 <= value <= 200 for value in values)
            or any(type(value) is not int or not -100 <= value <= 100
                   for value in (exposure, highlights, shadows))):
        raise InputError('Le regolazioni della foto non sono valide.')
    alpha = pixels.getchannel('A')
    result = pixels.convert('RGB')
    for enhancer, value in zip((ImageEnhance.Brightness, ImageEnhance.Contrast,
                                ImageEnhance.Color, ImageEnhance.Sharpness), values):
        changed = enhancer(result).enhance(value / 100)
        result.close()
        result = changed
    if exposure:
        changed = ImageEnhance.Brightness(result).enhance(2 ** (exposure / 100))
        result.close()
        result = changed
    if highlights or shadows:
        luminance = result.convert('L')
        for amount, upper in ((highlights, True), (shadows, False)):
            if not amount:
                continue
            mask = luminance.point(lambda level: round((max(0, level - 128) if upper
                                                        else max(0, 128 - level)) * 2))
            changed = ImageEnhance.Brightness(result).enhance(1 + amount / 100)
            merged = Image.composite(changed, result, mask)
            changed.close()
            result.close()
            mask.close()
            result = merged
        luminance.close()
    result.putalpha(alpha)
    alpha.close()
    return result


def background_surface(size: tuple[int, int], options: dict) -> Image.Image:
    style = options.get('style', 'solid')
    color = options.get('color', '#FFFFFF')
    if (style not in ('solid', 'gradient', 'image') or not isinstance(color, str)
            or len(color) != 7 or color[0] != '#'
            or any(char not in '0123456789abcdefABCDEF' for char in color[1:])):
        raise InputError('Scegli uno sfondo valido.')
    if style == 'image':
        background_path = options.get('background_path')
        if not isinstance(background_path, str):
            raise InputError('Scegli un’immagine per lo sfondo.')
        source = validate_source(Path(background_path))
        with Image.open(source) as raw:
            if getattr(raw, 'n_frames', 1) != 1:
                raise InputError('Lo sfondo deve essere un’immagine non animata.')
            with ImageOps.exif_transpose(raw) as oriented:
                return ImageOps.fit(oriented.convert('RGB'), size,
                                    method=Image.Resampling.LANCZOS)
    result = Image.new('RGB', size, color)
    if style == 'gradient':
        red, green, blue = ImageColor.getrgb(color)
        drawer = ImageDraw.Draw(result)
        for y in range(size[1]):
            ratio = y / max(1, size[1] - 1)
            shade = tuple(round(channel * (1 - ratio) + 255 * ratio)
                          for channel in (red, green, blue))
            drawer.line((0, y, size[0], y), fill=shade)
    return result


def run_image_action(action: str, source: Path, options: dict,
                     stage: Path) -> list[Path]:
    source = validate_source(source)
    if not isinstance(options, dict) or not stage.is_dir() or stage.is_symlink():
        raise InputError('Parametri immagine non validi.')
    try:
        with Image.open(source) as original:
            if getattr(original, 'n_frames', 1) != 1:
                raise InputError('Seleziona un’immagine non animata.')
            if original.width * original.height > MAX_PIXELS:
                raise InputError('L’immagine supera 40 megapixel.')
            if action == 'image.metadata':
                lines = [f'File: {source.name}', f'Dimensioni: {original.width} × {original.height}',
                         f'Formato: {original.format or source.suffix.upper()}', '']
                for tag, value in sorted(original.getexif().items()):
                    label = ExifTags.TAGS.get(tag, str(tag))
                    rendered = str(value).replace('\n', ' ')[:500]
                    lines.append(f'{label}: {rendered}')
                output = stage / 'metadata.txt'
                output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                return [output]
            original.load()
            with ImageOps.exif_transpose(original) as oriented:
                with oriented.convert('RGBA') as pixels:
                    if action == 'image.resize':
                        percent = options.get('percent')
                        if type(percent) is not int or percent not in (25, 50, 75):
                            raise InputError('Scegli una scala del 25, 50 o 75%.')
                        size = (max(1, round(pixels.width * percent / 100)),
                                max(1, round(pixels.height * percent / 100)))
                        result = pixels.resize(size, Image.Resampling.LANCZOS)
                    elif action == 'image.rotate':
                        degrees = options.get('degrees')
                        if type(degrees) is not int or degrees not in (90, 180, 270):
                            raise InputError('Scegli una rotazione di 90, 180 o 270 gradi.')
                        result = pixels.rotate(-degrees, expand=True)
                    elif action == 'image.crop':
                        box = options.get('box')
                        if (not isinstance(box, list) or len(box) != 4
                                or any(type(value) is not int for value in box)):
                            raise InputError('Indica quattro coordinate intere per il ritaglio.')
                        left, top, right, bottom = box
                        if not (0 <= left < right <= pixels.width
                                and 0 <= top < bottom <= pixels.height):
                            raise InputError('Il ritaglio deve restare dentro l’immagine.')
                        result = pixels.crop(tuple(box))
                    elif action == 'image.compress':
                        quality = options.get('quality')
                        if type(quality) is not int or quality not in (50, 70, 90):
                            raise InputError('Scegli una qualità di 50, 70 o 90.')
                        result = pixels.copy()
                    elif action == 'image.strip_metadata':
                        result = pixels.copy()
                    elif action == 'image.adjust':
                        result = adjust_pixels(pixels, options)
                    elif action == 'image.add_background':
                        padding = options.get('padding', 12)
                        if type(padding) is not int or not 0 <= padding <= 100:
                            raise InputError('Scegli un margine tra 0 e 100%.')
                        margin = round(min(pixels.size) * padding / 100)
                        if (pixels.width + 2 * margin) * (pixels.height + 2 * margin) > MAX_PIXELS:
                            raise InputError('Lo sfondo supera il limite di 40 megapixel.')
                        result = background_surface((pixels.width + 2 * margin,
                                                     pixels.height + 2 * margin), options)
                        result.paste(pixels, (margin, margin), pixels)
                    elif action in ('image.redact', 'image.annotate'):
                        result = pixels.copy()
                        drawer = ImageDraw.Draw(result)
                        if action == 'image.redact':
                            box = options.get('box')
                            if (not isinstance(box, list) or len(box) != 4
                                    or any(type(value) is not int for value in box)):
                                raise InputError('Indica l’area da oscurare.')
                            left, top, right, bottom = box
                            if not (0 <= left < right <= pixels.width
                                    and 0 <= top < bottom <= pixels.height):
                                raise InputError('L’area deve restare dentro l’immagine.')
                            drawer.rectangle(box, fill=(0, 0, 0, 255))
                        else:
                            value = options.get('text')
                            x, y = options.get('x'), options.get('y')
                            if (not isinstance(value, str) or not 1 <= len(value) <= 200
                                    or type(x) is not int or type(y) is not int
                                    or not 0 <= x < pixels.width or not 0 <= y < pixels.height):
                                raise InputError('Indica testo e posizione validi.')
                            font = ImageFont.load_default(size=max(14, min(96, pixels.width // 25)))
                            drawer.text((x, y), value, font=font, fill=(255, 255, 255, 255),
                                        stroke_width=2, stroke_fill=(15, 23, 42, 255))
                    else:
                        raise InputError('Operazione immagine non supportata.')
                    try:
                        output = stage / ('compressed.webp' if action == 'image.compress' else 'edited.png')
                        result.save(output, format='WEBP' if action == 'image.compress' else 'PNG',
                                    quality=options.get('quality', 90))
                        return [output]
                    finally:
                        result.close()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise InputError('Impossibile modificare l’immagine.') from exc
