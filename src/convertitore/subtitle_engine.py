"""Convert bounded local SRT and WebVTT caption files."""

import os
import re
import stat
from pathlib import Path

from .input_files import InputError, is_windows_link

MAX_SUBTITLE_BYTES = 5 * 1024 * 1024
SUBTITLE_SUFFIXES = frozenset({'.srt', '.vtt'})
TIMESTAMP = re.compile(r'^(\d{2,}):(\d{2}):(\d{2})[.,](\d{3})$')


def validate_subtitle(raw: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute() or (os.name == 'nt' and str(path).startswith('\\\\')):
        raise InputError('Scegli un sottotitolo locale.')
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                or is_windows_link(info)
                or not 0 < info.st_size <= MAX_SUBTITLE_BYTES
                or path.suffix.lower() not in SUBTITLE_SUFFIXES):
            raise InputError('Scegli un file SRT o VTT valido, fino a 5 MiB.')
        return path.resolve(strict=True)
    except OSError as exc:
        raise InputError('Il sottotitolo non è accessibile.') from exc


def _stamp(raw: str, separator: str) -> str:
    match = TIMESTAMP.fullmatch(raw.strip())
    if not match:
        raise InputError('Il sottotitolo contiene un tempo non valido.')
    hours, minutes, seconds, milliseconds = match.groups()
    if int(minutes) >= 60 or int(seconds) >= 60:
        raise InputError('Il sottotitolo contiene un tempo non valido.')
    return f'{hours}:{minutes}:{seconds}{separator}{milliseconds}'


def _cues(source: Path) -> list[tuple[str, str, list[str]]]:
    try:
        content = source.read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    except UnicodeError as exc:
        raise InputError('Il sottotitolo deve usare UTF-8.') from exc
    if source.suffix.lower() == '.vtt':
        if not content.lstrip().startswith('WEBVTT'):
            raise InputError('Intestazione WEBVTT mancante.')
        content = content[content.find('WEBVTT') + 6:]
    cues = []
    for block in re.split(r'\n\s*\n', content.strip()):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines or lines[0].startswith(('NOTE', 'STYLE', 'REGION')):
            continue
        timing = next((index for index, line in enumerate(lines[:2]) if '-->' in line), None)
        if timing is None:
            continue
        start_raw, end_raw = lines[timing].split('-->', 1)
        end_raw = end_raw.strip().split(' ', 1)[0]
        start = _stamp(start_raw, '.')
        end = _stamp(end_raw, '.')
        if end <= start or not lines[timing + 1:]:
            raise InputError('Una didascalia ha tempi o testo non validi.')
        cues.append((start, end, lines[timing + 1:]))
    if not cues or len(cues) > 100_000:
        raise InputError('Nessuna didascalia valida nel file.')
    return cues


def convert_subtitle(raw: Path, target: str, stage: Path) -> list[Path]:
    source = validate_subtitle(raw)
    if target not in ('SRT', 'VTT', 'TXT') or not stage.is_dir() or stage.is_symlink():
        raise InputError('Formato sottotitoli o cartella non validi.')
    cues = _cues(source)
    if target == 'TXT':
        content = '\n\n'.join('\n'.join(lines) for _, _, lines in cues) + '\n'
    elif target == 'VTT':
        content = 'WEBVTT\n\n' + '\n\n'.join(
            f'{start} --> {end}\n' + '\n'.join(lines)
            for start, end, lines in cues) + '\n'
    else:
        content = '\n\n'.join(
            f'{index}\n{start.replace(".", ",")} --> {end.replace(".", ",")}\n'
            + '\n'.join(lines)
            for index, (start, end, lines) in enumerate(cues, 1)) + '\n'
    output = stage / f'captions.{target.lower()}'
    output.write_text(content, encoding='utf-8')
    return [output]
