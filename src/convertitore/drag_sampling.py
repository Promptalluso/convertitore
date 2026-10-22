"""Read global drag modifiers without changing system input."""

import ctypes
import sys
from functools import lru_cache

from PySide6.QtGui import QCursor

from .drag_state import DragSample

MAC_SHIFT_MASK = 1 << 17
VK_LBUTTON = 0x01
VK_SHIFT = 0x10


def mac_buttons(quartz) -> tuple[bool, bool]:
    left = bool(quartz.CGEventSourceButtonState(0, 0))
    shift = bool(quartz.CGEventSourceFlagsState(0) & MAC_SHIFT_MASK)
    return left, shift


def windows_buttons(user32) -> tuple[bool, bool]:
    left = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
    shift = bool(user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
    return left, shift


@lru_cache(maxsize=1)
def _mac_api():
    quartz = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    quartz.CGEventSourceButtonState.argtypes = (ctypes.c_int32, ctypes.c_uint32)
    quartz.CGEventSourceButtonState.restype = ctypes.c_bool
    quartz.CGEventSourceFlagsState.argtypes = (ctypes.c_int32,)
    quartz.CGEventSourceFlagsState.restype = ctypes.c_uint64
    return quartz


@lru_cache(maxsize=1)
def _windows_api():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    return user32


@lru_cache(maxsize=1)
def _core_foundation():
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cf.CFRunLoopGetMain.restype = ctypes.c_void_p
    cf.CFRunLoopCopyCurrentMode.argtypes = (ctypes.c_void_p,)
    cf.CFRunLoopCopyCurrentMode.restype = ctypes.c_void_p
    cf.CFStringGetCString.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long,
                                      ctypes.c_uint32)
    cf.CFStringGetCString.restype = ctypes.c_bool
    cf.CFRelease.argtypes = (ctypes.c_void_p,)
    return cf


def in_default_run_loop() -> bool:
    """False while macOS is still delivering a drop in its own nested run loop."""
    if sys.platform != "darwin":
        return True
    try:
        cf = _core_foundation()
        mode = cf.CFRunLoopCopyCurrentMode(cf.CFRunLoopGetMain())
        if not mode:
            return True
        buffer = ctypes.create_string_buffer(256)
        ok = cf.CFStringGetCString(mode, buffer, len(buffer), 0x08000100)
        cf.CFRelease(mode)
        return not ok or buffer.value == b"kCFRunLoopDefaultMode"
    except (OSError, AttributeError):
        return True


def sample_drag_state() -> DragSample | None:
    try:
        if sys.platform == "darwin":
            left, shift = mac_buttons(_mac_api())
        elif sys.platform == "win32":
            left, shift = windows_buttons(_windows_api())
        else:
            return None
        cursor = QCursor.pos()
        return DragSample(cursor.x(), cursor.y(), left, shift)
    except (OSError, AttributeError, RuntimeError):
        return None
