"""Attach native macOS materials behind Qt windows when the bridge library is present."""

import ctypes
import os
import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


@lru_cache(maxsize=1)
def _bridge():
    if sys.platform != "darwin":
        return None
    candidates = [Path(sys.executable).resolve().parent.parent / "Resources" / "native_glass.dylib"]
    if os.environ.get("CONVERTITORE_NATIVE_GLASS"):
        candidates.insert(0, Path(os.environ["CONVERTITORE_NATIVE_GLASS"]))
    for path in candidates:
        if path.is_file():
            try:
                library = ctypes.CDLL(str(path))
                library.convertitore_attach_glass.argtypes = (ctypes.c_void_p, ctypes.c_double)
                library.convertitore_attach_glass.restype = ctypes.c_bool
                library.convertitore_attach_window_material.argtypes = (ctypes.c_void_p,)
                library.convertitore_attach_window_material.restype = ctypes.c_bool
                return library
            except (OSError, AttributeError):
                return None
    return None


def _native():
    """The bridge, only when Qt draws on real Cocoa windows.

    Under the offscreen platform winId() is not an NSView and the bridge would crash.
    """
    app = QGuiApplication.instance()
    if app is None or app.platformName() != "cocoa":
        return None
    return _bridge()


def attach_glass(widget, corner_radius: float) -> bool:
    library = _native()
    if library is None:
        return False
    try:
        return bool(library.convertitore_attach_glass(ctypes.c_void_p(int(widget.winId())),
                                                      corner_radius))
    except (OSError, ValueError):
        return False


def glass_available() -> bool:
    return _native() is not None


def attach_window_material(widget) -> bool:
    """Give a window the translucent macOS material. Returns False where unavailable.

    The widget must already have WA_TranslucentBackground from before its native window
    was created; set later, Qt keeps stale pixels and controls leave trails.
    """
    library = _native()
    if library is None or not widget.testAttribute(Qt.WA_TranslucentBackground):
        return False
    try:
        return bool(library.convertitore_attach_window_material(
            ctypes.c_void_p(int(widget.winId()))))
    except (OSError, ValueError):
        return False
