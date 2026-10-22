"""Run bundled FFmpeg with fixed local conversion profiles."""

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .input_files import InputError

MAX_MEDIA_BYTES = 2 * 1024 * 1024 * 1024
SF_DATALESS = getattr(stat, 'SF_DATALESS', 0x40000000)
VIDEO_SUFFIXES = frozenset({'.mp4', '.mov', '.webm', '.mkv'})
AUDIO_SUFFIXES = frozenset({'.mp3', '.m4a', '.aac', '.wav', '.flac'})
VIDEO_TARGETS = frozenset({'MP4', 'MOV', 'WEBM', 'MKV', 'GIF'})
AUDIO_TARGETS = frozenset({'MP3', 'M4A', 'WAV', 'FLAC'})
TARGET_SUFFIX = {'MP4': '.mp4', 'MOV': '.mov', 'WEBM': '.webm', 'MKV': '.mkv',
                 'GIF': '.gif', 'MP3': '.mp3', 'M4A': '.m4a', 'WAV': '.wav',
                 'FLAC': '.flac'}


def validate_media(raw: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute() or (os.name == 'nt' and str(path).startswith('\\\\')):
        raise InputError('Scegli un file audio o video locale.')
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            raise InputError('Scegli un file normale, non un collegamento.')
        # An iCloud placeholder makes FFmpeg wait for a download that may never start.
        if getattr(info, 'st_flags', 0) & SF_DATALESS:
            raise InputError('Il file è su iCloud e non è scaricato su questo Mac. '
                             'Nel Finder: tasto destro > Scarica ora, poi riprova.')
        if not 0 < info.st_size <= MAX_MEDIA_BYTES:
            raise InputError('Il file audio o video non può superare 2 GiB.')
        if path.suffix.lower() not in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
            raise InputError('Formato audio o video non supportato.')
        return path.resolve(strict=True)
    except OSError as exc:
        raise InputError('Il file audio o video non è accessibile.') from exc


def ffmpeg_binary() -> Path:
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable)
        if sys.platform == 'darwin':
            binary = executable.parent.parent / 'Resources' / 'ffmpeg'
        else:
            binary = executable.parent / 'ffmpeg.exe'
    else:
        import imageio_ffmpeg
        binary = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not binary.is_file():
        raise InputError('FFmpeg non è incluso in questa build.')
    return binary


def h264_encoding(compact: bool = False) -> list[str]:
    """Apple's hardware encoder is about ten times faster on 4K phone video."""
    if sys.platform == 'darwin':
        return ['-c:v', 'h264_videotoolbox', '-allow_sw', '1',
                '-q:v', '50' if compact else '65', '-pix_fmt', 'yuv420p']
    return ['-c:v', 'libx264', '-preset', 'veryfast',
            '-crf', '29' if compact else '23', '-pix_fmt', 'yuv420p']


def _codec(target: str, compact: bool = False) -> list[str]:
    if target in ('MP4', 'MOV', 'MKV'):
        return ['-map', '0:v:0', '-map', '0:a:0?', *h264_encoding(compact),
                '-c:a', 'aac', '-b:a', '128k' if compact else '160k']
    if target == 'WEBM':
        return ['-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libvpx-vp9',
                '-crf', '36' if compact else '32', '-b:v', '0',
                '-c:a', 'libopus', '-b:a', '96k' if compact else '128k']
    if target == 'GIF':
        return ['-map', '0:v:0', '-vf', 'fps=10,scale=480:-1:flags=lanczos',
                '-loop', '0']
    if target == 'MP3':
        return ['-map', '0:a:0', '-vn', '-c:a', 'libmp3lame',
                '-b:a', '128k' if compact else '192k']
    if target == 'M4A':
        return ['-map', '0:a:0', '-vn', '-c:a', 'aac',
                '-b:a', '128k' if compact else '192k']
    if target == 'WAV':
        return ['-map', '0:a:0', '-vn', '-c:a', 'pcm_s16le']
    if target == 'FLAC':
        return ['-map', '0:a:0', '-vn', '-c:a', 'flac']
    raise InputError('Formato media di uscita non supportato.')


def _seconds(value, name: str) -> float:
    if type(value) not in (int, float) or not 0 <= value <= 86_400:
        raise InputError(f'{name} deve essere un numero tra 0 e 86400 secondi.')
    return float(value)


def run_media_action(action: str, raw: Path, options: dict,
                     stage_dir: Path) -> list[Path]:
    if not isinstance(options, dict) or not stage_dir.is_dir() or stage_dir.is_symlink():
        raise InputError('Parametri media o cartella temporanea non validi.')
    source = validate_media(raw)
    is_video = source.suffix.lower() in VIDEO_SUFFIXES
    if action == 'media.split':
        if not is_video:
            raise InputError('Seleziona un video da dividere.')
        from .media_join import probe_video
        duration = probe_video(source)[0]
        points = options.get('points')
        if (not isinstance(points, list) or not 1 <= len(points) <= 9
                or any(type(point) not in (int, float) for point in points)
                or any(not 0.01 <= point <= duration - 0.01 for point in points)
                or points != sorted(set(points))):
            raise InputError('Indica fino a nove punti di taglio crescenti.')
        bounds = [0.0, *points, duration]
        outputs = []
        for index, (start, end) in enumerate(zip(bounds, bounds[1:]), 1):
            if end - start < 0.01:
                raise InputError('I tagli devono distare almeno 0,01 secondi.')
            chunk = run_media_action('media.trim', source,
                                     {'start': start, 'end': end}, stage_dir)[0]
            output = stage_dir / f'part-{index:03d}.mp4'
            chunk.rename(output)
            outputs.append(output)
        return outputs
    prefix = []
    if action == 'media.convert':
        target = options.get('target')
        if target not in TARGET_SUFFIX or (target in VIDEO_TARGETS and not is_video):
            raise InputError('Scegli un formato compatibile con il file.')
        output = stage_dir / ('converted' + TARGET_SUFFIX[target])
        encoding = _codec(target)
    elif action == 'media.extract_audio':
        target = options.get('target', 'MP3')
        if not is_video or target not in AUDIO_TARGETS:
            raise InputError('Seleziona un video e un formato audio.')
        output = stage_dir / ('audio' + TARGET_SUFFIX[target])
        encoding = _codec(target)
    elif action == 'media.compress':
        target = 'MP4' if is_video else 'MP3'
        output = stage_dir / ('compressed' + TARGET_SUFFIX[target])
        encoding = _codec(target, compact=True)
        if is_video:
            encoding += ['-vf', 'scale=w=min(1920\\,iw):h=min(1080\\,ih):force_original_aspect_ratio=decrease']
    elif action == 'media.resize':
        height = options.get('height')
        if not is_video or type(height) is not int or height not in (720, 1080):
            raise InputError('Scegli un video e una risoluzione di 720p o 1080p.')
        output = stage_dir / 'resized.mp4'
        encoding = _codec('MP4') + [
            '-vf', f'scale=w=min(1920\\,iw):h=min({height}\\,ih):force_original_aspect_ratio=decrease']
    elif action == 'media.crop':
        box = options.get('box')
        if (not is_video or not isinstance(box, list) or len(box) != 4
                or any(type(value) is not int for value in box)):
            raise InputError('Indica quattro coordinate intere per il video.')
        x, y, width, height = box
        if (not 0 <= x <= 8192 or not 0 <= y <= 8192
                or not 2 <= width <= 8192 or not 2 <= height <= 8192
                or width % 2 or height % 2):
            raise InputError('Il ritaglio video richiede dimensioni pari tra 2 e 8192 pixel.')
        output = stage_dir / 'cropped.mp4'
        encoding = _codec('MP4') + ['-vf', f'crop={width}:{height}:{x}:{y}']
    elif action == 'media.speed':
        factor = options.get('factor')
        if (not is_video or type(factor) not in (int, float)
                or not 0.25 <= factor <= 4):
            raise InputError('Scegli una velocità tra 0,25× e 4×.')
        factor = float(factor)
        tempo = []
        remainder = factor
        while remainder < 0.5:
            tempo.append('atempo=0.5')
            remainder /= 0.5
        while remainder > 2:
            tempo.append('atempo=2')
            remainder /= 2
        tempo.append(f'atempo={remainder:g}')
        output = stage_dir / 'speed.mp4'
        encoding = _codec('MP4') + ['-vf', f'setpts=PTS/{factor:g}',
                                    '-af', ','.join(tempo)]
    elif action == 'media.redact':
        box = options.get('box')
        if (not is_video or not isinstance(box, list) or len(box) != 4
                or any(type(value) is not int for value in box)):
            raise InputError('Indica l’area video da oscurare.')
        x, y, width, height = box
        start = _seconds(options.get('start'), 'L’inizio')
        end = _seconds(options.get('end'), 'La fine')
        if (not 0 <= x <= 8192 or not 0 <= y <= 8192
                or not 1 <= width <= 8192 or not 1 <= height <= 8192
                or end <= start):
            raise InputError('Area o intervallo video non valido.')
        output = stage_dir / 'redacted.mp4'
        encoding = _codec('MP4') + [
            '-vf', f"drawbox=x={x}:y={y}:w={width}:h={height}:"
                   f"color=black:t=fill:enable='between(t,{start},{end})'"]
    elif action == 'media.frame':
        if not is_video:
            raise InputError('Il fotogramma richiede un video.')
        timestamp = _seconds(options.get('time', 0), 'Il tempo')
        prefix = ['-ss', str(timestamp)]
        output = stage_dir / 'frame.png'
        encoding = ['-map', '0:v:0', '-frames:v', '1', '-update', '1']
    elif action == 'media.trim':
        start = _seconds(options.get('start'), 'L’inizio')
        end = _seconds(options.get('end'), 'La fine')
        if end <= start:
            raise InputError('La fine deve seguire l’inizio.')
        prefix = ['-ss', str(start)]
        target = 'MP4' if is_video else 'MP3'
        output = stage_dir / ('trimmed' + TARGET_SUFFIX[target])
        encoding = ['-t', str(end - start)] + _codec(target)
    elif action == 'media.channels':
        if is_video:
            raise InputError('Seleziona un file audio per i canali.')
        channels = options.get('channels')
        if type(channels) is not int or channels not in (1, 2):
            raise InputError('Scegli mono o stereo.')
        left, right = options.get('left', 100), options.get('right', 100)
        if (type(left) is not int or type(right) is not int
                or not 0 <= left <= 200 or not 0 <= right <= 200):
            raise InputError('Il volume dei canali deve essere tra 0 e 200%.')
        output = stage_dir / 'channels.mp3'
        encoding = _codec('MP3') + ['-ac', str(channels)]
        if channels == 2 and (left != 100 or right != 100):
            encoding += ['-af', 'aformat=channel_layouts=stereo,'
                         f'pan=stereo|c0={left / 100}*c0|c1={right / 100}*c1']
    elif action == 'media.normalize':
        if is_video:
            raise InputError('Seleziona un file audio da normalizzare.')
        output = stage_dir / 'normalized.mp3'
        encoding = _codec('MP3') + ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11']
    elif action == 'media.bleep':
        if is_video:
            raise InputError('Seleziona un file audio per il bleep.')
        start = _seconds(options.get('start'), 'L’inizio')
        end = _seconds(options.get('end'), 'La fine')
        if end <= start or end - start > 60:
            raise InputError('Il bleep deve durare tra 0 e 60 secondi.')
        frequency = options.get('frequency', 1000)
        if type(frequency) is not int or not 200 <= frequency <= 3000:
            raise InputError('La frequenza del bleep deve essere tra 200 e 3000 Hz.')
        output = stage_dir / 'bleeped.mp3'
        filtergraph = (f"[0:a:0]volume=enable='between(t,{start},{end})':volume=0[muted];"
                       f'sine=frequency={frequency}:sample_rate=44100:duration={end-start},'
                       f'adelay={round(start * 1000)}:all=1[tone];'
                       '[muted][tone]amix=inputs=2:duration=first:dropout_transition=0[out]')
        encoding = ['-filter_complex', filtergraph, '-map', '[out]', '-vn',
                    '-c:a', 'libmp3lame', '-b:a', '192k']
    else:
        raise InputError('Operazione media non supportata.')
    command = [str(ffmpeg_binary()), '-hide_banner', '-loglevel', 'error',
               '-nostdin', '-n'] + prefix + [
               '-protocol_whitelist', 'file,pipe', '-i', str(source),
               '-map_metadata', '-1'] + encoding + [str(output)]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with tempfile.TemporaryFile() as error:
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=error,
                                    creationflags=flags, timeout=900, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InputError('FFmpeg non ha completato l’operazione.') from exc
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            error.seek(0, os.SEEK_END)
            error.seek(max(0, error.tell() - 8192))
            report = error.read().splitlines()
            if any(b"for option 'map'" in line and b'0:a:0' in line for line in report):
                raise InputError('Questo file non ha una traccia audio.')
            markers =(b'moov atom not found', b'Invalid data found',
                       b'Permission denied', b'Protocol not on whitelist',
                       b'No such file or directory', b'Error while filtering',
                       b'Error submitting a packet', b'Error opening input')
            detail = next((line.strip().decode('utf-8', errors='replace')[:160]
                           for marker in markers for line in report if marker in line), '')
            message = 'Il file non è compatibile con questa conversione media.'
            raise InputError(f'{message} FFmpeg: {detail}' if detail else message)
    return [output]
