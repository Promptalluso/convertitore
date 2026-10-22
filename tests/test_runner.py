import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image

from convertitore.runner import Cancelled, run_job


class WorkerTests(unittest.TestCase):
    def test_worker_converts_a_real_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.png"
            Image.new("RGB", (2, 2), "orange").save(source)
            request = json.dumps({"source": str(source), "target": "JPEG", "output_dir": tmp}).encode()
            result = subprocess.run([sys.executable, "-m", "convertitore", "--worker"],
                                    input=request, capture_output=True, timeout=15,
                                    env={**os.environ, "PYTHONPATH": "src"})
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            with Image.open(payload["output"]) as image:
                self.assertEqual(image.format, "JPEG")

    def test_runner_converts_a_real_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.png"
            Image.new("RGB", (2, 2), "blue").save(source)
            output = run_job(source, "WEBP", Path(tmp), threading.Event())
            with Image.open(output) as image:
                self.assertEqual(image.format, "WEBP")

    def test_cancelled_job_stops(self):
        event = threading.Event()
        event.set()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Cancelled):
                run_job(Path(tmp) / "unused.png", "PNG", Path(tmp), event,
                        command=[sys.executable, "-c", "import time; time.sleep(10)"])

    def test_timeout_stops_slow_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TimeoutError):
                run_job(Path(tmp) / "unused.png", "PNG", Path(tmp), threading.Event(),
                        timeout=0.2,
                        command=[sys.executable, "-c", "import time; time.sleep(10)"])
