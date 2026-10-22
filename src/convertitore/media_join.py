"""Join local video clips with one normalized canvas and audio track."""

import os
import re
import subprocess
from pathlib import Path

from .input_files import InputError
from .media_engine import VIDEO_SUFFIXES, ffmpeg_binary, h264_encoding, validate_media


def probe_video(path: Path) -> tuple[float, int, int, bool]:
    source = validate_media(path)
    if source.suffix.lower() not in VIDEO_SUFFIXES:
        raise InputError('Seleziona un video.')
    command = [str(ffmpeg_binary()), '-hide_banner', '-nostdin',
               '-protocol_whitelist', 'file,pipe', '-i', str(source)]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        result = subprocess.run(command, capture_output=True, timeout=15,
                                creationflags=flags, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InputError('Impossibile leggere le informazioni del video.') from exc
    return parse_video_report(result.stderr[:131_072])


def parse_video_report(report: bytes) -> tuple[float, int, int, bool]:
    """Read the bounded FFmpeg probe output, also used by the visual editor."""
    duration = re.search(rb'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', report)
    video = re.search(rb'Video:.*?\b(\d{2,5})x(\d{2,5})\b', report)
    if not duration or not video:
        raise InputError('Durata o dimensioni video non disponibili.')
    hours, minutes, seconds = duration.groups()
    length = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    width, height = (int(value) for value in video.groups())
    rotation = re.search(rb'displaymatrix: rotation of\s*(-?\d+(?:\.\d+)?)', report)
    if rotation and 45 < abs(float(rotation.group(1))) % 180 < 135:
        width, height = height, width
    if (not 0 < length <= 86400 or not 2 <= width <= 8192
            or not 2 <= height <= 8192):
        raise InputError('Il video supera i limiti di durata o dimensione.')
    has_audio = bool(re.search(rb'Stream #\d+(?::\d+)+.*?: Audio:', report))
    return length, width, height, has_audio


def join_videos(sources: list[Path], stage: Path) -> list[Path]:
    if (not 2 <= len(sources) <= 10 or not stage.is_dir() or stage.is_symlink()):
        raise InputError('Seleziona da 2 a 10 video da unire.')
    details = [probe_video(path) for path in sources]
    width = details[0][1] - details[0][1] % 2
    height = details[0][2] - details[0][2] % 2
    if width < 2 or height < 2:
        raise InputError('La dimensione del primo video non è valida.')
    command = [str(ffmpeg_binary()), '-hide_banner', '-loglevel', 'error',
               '-nostdin', '-n']
    for source in sources:
        command += ['-protocol_whitelist', 'file,pipe', '-i', str(validate_media(source))]
    audio_inputs = []
    next_input = len(sources)
    for duration, _, _, has_audio in details:
        if has_audio:
            audio_inputs.append(None)
        else:
            command += ['-f', 'lavfi', '-t', str(duration), '-i',
                        'anullsrc=channel_layout=stereo:sample_rate=48000']
            audio_inputs.append(next_input)
            next_input += 1
    filters = []
    pieces = []
    for index, synthetic_audio in enumerate(audio_inputs):
        filters.append(f'[{index}:v:0]scale={width}:{height}:'
                       'force_original_aspect_ratio=decrease,'
                       f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,'
                       f'setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{index}]')
        audio_index = index if synthetic_audio is None else synthetic_audio
        filters.append(f'[{audio_index}:a:0]aresample=48000,asetpts=PTS-STARTPTS[a{index}]')
        pieces.append(f'[v{index}][a{index}]')
    filters.append(''.join(pieces) + f'concat=n={len(sources)}:v=1:a=1[outv][outa]')
    output = stage / 'joined.mp4'
    command += ['-filter_complex', ';'.join(filters), '-map', '[outv]', '-map', '[outa]',
                '-map_metadata', '-1', *h264_encoding(), '-c:a', 'aac', '-b:a', '160k',
                str(output)]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=900,
                                creationflags=flags, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InputError('L’unione dei video non è stata completata.') from exc
    if result.returncode or not output.is_file() or output.stat().st_size == 0:
        raise InputError('I video selezionati non possono essere uniti.')
    return [output]
