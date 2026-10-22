import subprocess
import tempfile
import unittest
from pathlib import Path

import imageio_ffmpeg

from convertitore.input_files import InputError
from convertitore.media_engine import run_media_action
from convertitore.media_join import probe_video
from convertitore.operation_publication import publish_operation

from tests.test_media_engine import make_video


class MediaJoinTests(unittest.TestCase):
    def test_join_mixed_canvas_and_silent_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / 'first.mp4'
            second = root / 'silent.mp4'
            make_video(first)
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner',
                            '-loglevel', 'error', '-f', 'lavfi', '-i',
                            'testsrc2=size=80x60:rate=5', '-t', '0.5',
                            '-c:v', 'libx264', str(second)],
                           capture_output=True, timeout=30, check=True)
            result = publish_operation('media.join', [first, second], {}, root)[0]
            duration, width, height, has_audio = probe_video(result)
            self.assertGreater(duration, 0.9)
            self.assertEqual((width, height), (64, 48))
            self.assertTrue(has_audio)

    def test_split_and_redact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'clip.mp4'
            make_video(source)
            outputs = publish_operation('media.split', [source],
                                        {'points': [0.25]}, root)
            self.assertEqual(len(outputs), 2)
            self.assertTrue(all(path.stat().st_size > 100 for path in outputs))
            redacted = run_media_action('media.redact', source,
                                        {'box': [0, 0, 16, 16],
                                         'start': 0, 'end': 0.3}, root)[0]
            self.assertGreater(redacted.stat().st_size, 100)
            with self.assertRaises(InputError):
                run_media_action('media.split', source, {'points': [0.5, 0.2]}, root)


if __name__ == '__main__':
    unittest.main()
