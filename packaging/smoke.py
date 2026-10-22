"""Open a built package and convert a real file through its worker."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter


def packaged_executable(dist: Path) -> Path:
    if sys.platform == "darwin":
        return dist / "Convertitore.app" / "Contents" / "MacOS" / "Convertitore"
    return dist / "Convertitore" / "Convertitore.exe"


def main() -> int:
    dist = Path(sys.argv[1]).resolve()
    executable = packaged_executable(dist)
    if not executable.is_file():
        raise FileNotFoundError(f"Pacchetto non trovato: {executable}")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "input.png"
        Image.new("RGB", (2, 2), "orange").save(source)
        request = json.dumps({"source": str(source), "target": "JPEG", "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=30, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Conversione confezionata fallita."))
        with Image.open(payload["output"]) as image:
            if image.format != "JPEG" or image.size != (2, 2):
                raise RuntimeError("Il JPEG confezionato non è valido.")
        for target, expected in (("TIFF", "TIFF"), ("BMP", "BMP"),
                                 ("GIF", "GIF"), ("AVIF", "AVIF")):
            request = json.dumps({"source": str(source), "target": target,
                                  "output_dir": tmp}).encode()
            result = subprocess.run([str(executable), "--worker"], input=request,
                                    capture_output=True, timeout=30, check=False)
            payload = json.loads(result.stdout)
            if result.returncode != 0 or not payload.get("ok"):
                raise RuntimeError(payload.get("error", f"{target} confezionato non funziona."))
            with Image.open(payload["output"]) as image:
                if image.format != expected or image.size != (2, 2):
                    raise RuntimeError(f"Il file {target} confezionato non è valido.")
        request = json.dumps({"action": "image.resize", "sources": [str(source)],
                              "options": {"percent": 50}, "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=30, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Modifica immagine confezionata non funziona."))
        with Image.open(payload["outputs"][0]) as image:
            if image.size != (1, 1):
                raise RuntimeError("Il ridimensionamento confezionato non è valido.")
        request = json.dumps({"action": "image.redact", "sources": [str(source)],
                              "options": {"box": [0, 0, 1, 1]}, "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=30, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Oscuramento confezionato non funziona."))
        with Image.open(payload["outputs"][0]) as image:
            if image.getpixel((0, 0)) != (0, 0, 0, 255):
                raise RuntimeError("L’area oscurata non è valida.")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "input.pdf"
        writer = PdfWriter()
        writer.add_blank_page(72, 72)
        with source.open("wb") as output:
            writer.write(output)
        for action, sources, options in (
            ("pdf.merge", [source, source], {}),
            ("pdf.to_images", [source], {"target": "PNG", "dpi": 72}),
        ):
            request = json.dumps({"action": action, "sources": [str(path) for path in sources],
                                  "options": options, "output_dir": tmp}).encode()
            result = subprocess.run([str(executable), "--worker"], input=request,
                                    capture_output=True, timeout=30, check=False)
            payload = json.loads(result.stdout)
            if result.returncode != 0 or not payload.get("ok"):
                raise RuntimeError(payload.get("error", f"{action} non riuscita."))
            outputs = [Path(item) for item in payload["outputs"]]
            if action == "pdf.merge" and len(PdfReader(outputs[0]).pages) != 2:
                raise RuntimeError("L’unione PDF confezionata non è valida.")
            if action == "pdf.to_images":
                with Image.open(outputs[0]) as image:
                    if image.format != "PNG" or image.size != (72, 72):
                        raise RuntimeError("La resa PDFium confezionata non è valida.")
    ffmpeg = (dist / "Convertitore.app" / "Contents" / "Resources" / "ffmpeg"
              if sys.platform == "darwin" else dist / "Convertitore" / "ffmpeg.exe")
    if not ffmpeg.is_file():
        raise FileNotFoundError("FFmpeg non è incluso nel pacchetto.")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "scan.png"
        image = Image.new("RGB", (1000, 260), "white")
        ImageDraw.Draw(image).text((50, 60), "HELLO WORLD 123", fill="black",
                                   font=ImageFont.load_default(size=72))
        image.save(source)
        request = json.dumps({"action": "ocr.text", "sources": [str(source)],
                              "options": {}, "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=120, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "OCR confezionato non funziona."))
        if "HELLO" not in Path(payload["outputs"][0]).read_text(encoding="utf-8"):
            raise RuntimeError("Il testo OCR confezionato non è valido.")
        pdf_source = Path(tmp) / "scan.pdf"
        image.save(pdf_source, format="PDF", resolution=72)
        request = json.dumps({"action": "ocr.searchable_pdf", "sources": [str(pdf_source)],
                              "options": {}, "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=120, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "PDF ricercabile confezionato non funziona."))
        if "HELLO" not in PdfReader(payload["outputs"][0]).pages[0].extract_text():
            raise RuntimeError("Il PDF OCR confezionato non è ricercabile.")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "tone.wav"
        subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", "sine=frequency=440:sample_rate=8000", "-t", "0.3",
                        str(source)], capture_output=True, timeout=30, check=True)
        request = json.dumps({"action": "media.convert", "sources": [str(source)],
                              "options": {"target": "MP3"}, "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=30, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "FFmpeg confezionato non funziona."))
        if Path(payload["outputs"][0]).stat().st_size <= 100:
            raise RuntimeError("Il file MP3 confezionato è vuoto.")
        video = Path(tmp) / "clip.mp4"
        subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error",
                        "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=5",
                        "-t", "0.5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(video)], capture_output=True, timeout=30, check=True)
        request = json.dumps({"action": "media.resize", "sources": [str(video)],
                              "options": {"height": 720}, "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=60, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Ridimensionamento video confezionato non funziona."))
        if Path(payload["outputs"][0]).stat().st_size <= 100:
            raise RuntimeError("Il video confezionato è vuoto.")
        for action, options in (("media.crop", {"box": [8, 8, 32, 24]}),
                                ("media.trim", {"start": 0.1, "end": 0.4})):
            request = json.dumps({"action": action, "sources": [str(video)],
                                  "options": options, "output_dir": tmp}).encode()
            result = subprocess.run([str(executable), "--worker"], input=request,
                                    capture_output=True, timeout=60, check=False)
            payload = json.loads(result.stdout)
            if result.returncode != 0 or not payload.get("ok"):
                raise RuntimeError(payload.get("error", f"{action} confezionato non funziona."))
            output = Path(payload["outputs"][0])
            probe = subprocess.run([str(ffmpeg), "-hide_banner", "-i", str(output)],
                                   capture_output=True, timeout=15, check=False)
            report = probe.stderr
            if action == "media.crop" and not re.search(rb'Video:.*?\b32x24\b', report):
                raise RuntimeError("Il ritaglio video confezionato ha dimensioni errate.")
            if action == "media.trim":
                match = re.search(rb'Duration:\s*00:00:(\d+(?:\.\d+)?)', report)
                if not match or not 0.2 <= float(match.group(1)) <= 0.4:
                    raise RuntimeError("Il taglio video confezionato ha durata errata.")
        captions = Path(tmp) / "captions.srt"
        captions.write_text("1\n00:00:01,000 --> 00:00:02,000\nCiao\n", encoding="utf-8")
        request = json.dumps({"action": "subtitle.convert", "sources": [str(captions)],
                              "options": {"target": "VTT"}, "output_dir": tmp}).encode()
        result = subprocess.run([str(executable), "--worker"], input=request,
                                capture_output=True, timeout=30, check=False)
        payload = json.loads(result.stdout)
        if result.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Sottotitoli confezionati non funzionano."))
        if not Path(payload["outputs"][0]).read_text(encoding="utf-8").startswith("WEBVTT"):
            raise RuntimeError("Il VTT confezionato non è valido.")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    startup = subprocess.run([str(executable), "--smoke-ui"], timeout=30,
                             env=env, capture_output=True, check=False)
    if startup.returncode != 0:
        raise RuntimeError(startup.stderr.decode("utf-8", "replace")[-1000:])
    print("Package smoke passed: image, PDF, video crop/trim, MP3, subtitles, offline OCR and Qt startup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
