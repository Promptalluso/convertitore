# Third-party notices

## Open Tangerine

This project's image conversion and desktop packaging design adapt the GPL-3.0-only Open Tangerine desktop edition at revision `1fc2333f834017a40a836eab204740ba7627452c`.

Original source: https://github.com/sintaxerrorpvtltd/Open-Tangerine
Copyright © 2026 Sintax Error Private Limited. Original work remains under GPL-3.0-only. The GPLv3 text is included in `LICENSE`.

This application uses a different name and original icon. It does not include the upstream native Swift application, Satsuma code, DragShift assets, or the Tangerine brand.

## Bundled dependencies

- Python 3.12: Python Software Foundation License. https://docs.python.org/3/license.html
- Pillow 13.0.0: HPND. https://github.com/python-pillow/Pillow/blob/main/LICENSE
- PySide6-Essentials and shiboken6 6.12.0: LGPL-3.0-only or GPL alternatives. Qt libraries remain dynamically linked in the package. https://doc.qt.io/qtforpython-6/licenses.html
- pypdf 6.21.1: BSD-3-Clause. https://github.com/py-pdf/pypdf/blob/main/LICENSE
- pypdfium2 5.14.0 and bundled PDFium: Apache-2.0/BSD-3-Clause and PDFium dependency licenses. https://github.com/pypdfium2-team/pypdfium2
- imageio-ffmpeg 0.6.0 Python wrapper: BSD-2-Clause. https://github.com/imageio/imageio-ffmpeg
- RapidOCR 3.10.0 and bundled PP-OCR models: Apache-2.0. https://github.com/RapidAI/RapidOCR
- ONNX Runtime 1.31.0: MIT. https://github.com/microsoft/onnxruntime
- ReportLab 5.0.1: BSD-3-Clause. https://www.reportlab.com/
- FFmpeg 7.1 executable from the imageio-ffmpeg wheel: GPL-enabled build with bundled codecs. https://ffmpeg.org/legal.html . A public release must provide the corresponding FFmpeg source and complete codec license notices alongside the binary.
- PyInstaller 6.22.3 bootloader: GPL with its distribution exception. https://pyinstaller.org/en/stable/license.html

The package includes dependency versions, available license texts, and the corresponding application source. Source and license texts for dependencies are available at the pinned upstream release versions.
