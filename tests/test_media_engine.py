import stat
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import imageio_ffmpeg

from convertitore.input_files import InputError
from convertitore.media_engine import SF_DATALESS, run_media_action, validate_media
from convertitore.audio_editor import audio_duration, audio_waveform


def make_video(path: Path) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error',
                    '-f', 'lavfi', '-i', 'testsrc2=size=64x48:rate=5',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=8000',
                    '-t', '0.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', str(path)], check=True, timeout=30)


class MediaEngineTests(unittest.TestCase):
    def test_audio_channels_bleep_and_waveform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.wav'
            with wave.open(str(source), 'wb') as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(8000)
                output.writeframes(b'\0\0' * 16000)
            self.assertAlmostEqual(audio_duration(source), 2.0, places=1)
            self.assertTrue(audio_waveform(source, 2.0))
            channels = run_media_action('media.channels', source, {'channels': 2}, root)[0]
            self.assertGreater(channels.stat().st_size, 100)
            bleep = run_media_action('media.bleep', source,
                                     {'start': 0.2, 'end': 0.7}, root)[0]
            self.assertGreater(bleep.stat().st_size, 100)
            with self.assertRaises(InputError):
                run_media_action('media.bleep', source,
                                 {'start': 0.7, 'end': 0.2}, root)

    def test_video_to_webm_and_audio_to_mp3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.mp4'
            make_video(source)
            stage = root / 'stage'
            stage.mkdir()
            video = run_media_action('media.convert', source, {'target': 'WEBM'}, stage)
            self.assertEqual(video[0].suffix, '.webm')
            self.assertGreater(video[0].stat().st_size, 100)
            audio = run_media_action('media.extract_audio', source, {'target': 'MP3'}, stage)
            self.assertEqual(audio[0].suffix, '.mp3')
            self.assertGreater(audio[0].stat().st_size, 100)

    def test_compress_and_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.mp4'
            make_video(source)
            stage = root / 'stage'
            stage.mkdir()
            compressed = run_media_action('media.compress', source, {}, stage)
            self.assertEqual(compressed[0].suffix, '.mp4')
            frame = run_media_action('media.frame', source, {'time': 0.1}, stage)
            self.assertEqual(frame[0].suffix, '.png')
            resized = run_media_action('media.resize', source, {'height': 720}, stage)
            self.assertEqual(resized[0].suffix, '.mp4')
            self.assertGreater(resized[0].stat().st_size, 100)

    def test_crop_speed_and_normalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / 'source.mp4'
            make_video(video)
            cropped = run_media_action('media.crop', video,
                                       {'box': [0, 0, 32, 24]}, root)[0]
            self.assertGreater(cropped.stat().st_size, 100)
            faster = run_media_action('media.speed', video, {'factor': 2.0}, root)[0]
            self.assertGreater(faster.stat().st_size, 100)
            with self.assertRaises(InputError):
                run_media_action('media.crop', video, {'box': [0, 0, 31, 24]}, root)
            audio = run_media_action('media.extract_audio', video,
                                     {'target': 'WAV'}, root)[0]
            normalized = run_media_action('media.normalize', audio, {}, root)[0]
            self.assertGreater(normalized.stat().st_size, 100)

    def test_unsupported_target_and_remote_input_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.mp4'
            source.write_bytes(b'fake')
            stage = root / 'stage'
            stage.mkdir()
            with self.assertRaises(InputError):
                run_media_action('media.convert', source, {'target': 'EXE'}, stage)
            with self.assertRaises(InputError):
                run_media_action('media.convert', Path('https://example.com/a.mp4'),
                                 {'target': 'MP4'}, stage)

    def test_unreadable_movie_reports_ffmpeg_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'broken.mov'
            source.write_bytes(b'not a video')
            with self.assertRaisesRegex(InputError, 'moov atom not found'):
                run_media_action('media.convert', source, {'target': 'GIF'}, root)

    def test_audio_from_silent_video_says_why(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'silent.mp4'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'testsrc2=size=64x48:rate=5', '-t', '0.5',
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)],
                           check=True, timeout=30)
            with self.assertRaisesRegex(InputError, 'traccia audio'):
                run_media_action('media.extract_audio', source, {'target': 'MP3'}, root)

    def test_icloud_placeholder_is_rejected_before_ffmpeg(self):
        placeholder = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_size=4_615_918,
                                      st_flags=SF_DATALESS)
        with mock.patch.object(Path, 'lstat', return_value=placeholder):
            with self.assertRaisesRegex(InputError, 'iCloud'):
                validate_media(Path(tempfile.gettempdir()).resolve() / 'clip.mov')
