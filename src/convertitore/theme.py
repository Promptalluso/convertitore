"""Shared visual system: macOS glass surfaces, one pastel-blue accent, system type.

Corner radii: buttons are pills, panels 14 px, inputs 10 px.
"""

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QGuiApplication


@dataclass(frozen=True)
class Tokens:
    window: str         # solid fallback where the glass material is unavailable
    text: str
    text_muted: str
    hairline: str
    panel: str
    panel_hover: str
    canvas: str
    accent: str          # pastel blue fill: hovered sector, primary button
    accent_strong: str   # pressed state and slider fill
    accent_ink: str      # text and icons drawn on the accent
    focus: str
    error: str


LIGHT = Tokens(
    window='#eef2f7', text='#1d2430', text_muted='#5a6474', hairline='rgba(29, 36, 48, 0.12)',
    panel='rgba(255, 255, 255, 0.62)', panel_hover='rgba(255, 255, 255, 0.82)',
    canvas='#e4e9f0', accent='#cfe6fb', accent_strong='#a9d2f7',
    accent_ink='#123a5c', focus='#5aa7e8', error='#b3261e')

DARK = Tokens(
    window='#1f242c', text='#eef2f7', text_muted='#a9b3c1', hairline='rgba(255, 255, 255, 0.14)',
    panel='rgba(255, 255, 255, 0.08)', panel_hover='rgba(255, 255, 255, 0.14)',
    canvas='#1c2129', accent='#cfe6fb', accent_strong='#a9d2f7',
    accent_ink='#123a5c', focus='#8cc4f2', error='#ffb4ab')


def is_dark() -> bool:
    app = QGuiApplication.instance()
    return bool(app) and app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def tokens() -> Tokens:
    return DARK if is_dark() else LIGHT


def qcolor(value: str) -> QColor:
    if value.startswith('rgba('):
        r, g, b, a = (part.strip() for part in value[5:-1].split(','))
        return QColor(int(r), int(g), int(b), round(float(a) * 255))
    return QColor(value)


def stylesheet() -> str:
    t = tokens()
    return f"""
        QWidget {{ color: {t.text}; font-size: 13px; }}
        QMainWindow, QDialog {{ background: {t.window}; }}
        QLabel {{ background: transparent; }}
        QLabel#title {{ font-size: 26px; font-weight: 700; }}
        QLabel#muted, QLabel#footer {{ color: {t.text_muted}; }}
        QLabel#footer {{ font-size: 11px; }}
        QLabel#error {{ color: {t.error}; }}
        QListWidget {{ background: {t.panel}; border: 1px solid {t.hairline};
                       border-radius: 14px; padding: 10px; outline: none; }}
        QListWidget::item {{ padding: 7px 8px; border-radius: 8px; }}
        QListWidget::item:selected {{ background: {t.accent}; color: {t.accent_ink}; }}
        QPushButton {{ background: {t.panel}; border: 1px solid {t.hairline};
                       border-radius: 15px; padding: 7px 16px; min-height: 16px; }}
        QPushButton:hover {{ background: {t.panel_hover}; }}
        QPushButton:pressed {{ background: {t.accent}; color: {t.accent_ink}; }}
        QPushButton:focus {{ border: 2px solid {t.focus}; }}
        QPushButton:disabled {{ color: {t.text_muted}; background: transparent; }}
        QPushButton#primary, QPushButton:default {{
            background: {t.accent}; color: {t.accent_ink}; border: 1px solid {t.accent_strong};
            font-weight: 600; }}
        QPushButton#primary:hover, QPushButton:default:hover {{ background: {t.accent_strong}; }}
        QPushButton#primary:disabled {{ background: {t.panel}; color: {t.text_muted};
                                        border-color: {t.hairline}; }}
        QComboBox, QLineEdit, QSpinBox {{ background: {t.panel}; border: 1px solid {t.hairline};
                       border-radius: 10px; padding: 6px 10px; min-height: 18px; }}
        QComboBox:hover, QLineEdit:hover {{ background: {t.panel_hover}; }}
        QComboBox:focus, QLineEdit:focus {{ border: 2px solid {t.focus}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox QAbstractItemView {{ border-radius: 10px; padding: 4px;
                       selection-background-color: {t.accent}; selection-color: {t.accent_ink}; }}
        QProgressBar {{ background: transparent; border: none; max-height: 4px;
                        border-radius: 2px; }}
        QProgressBar::chunk {{ background: {t.accent_strong}; border-radius: 2px; }}
        QSlider::groove:horizontal {{ height: 4px; border-radius: 2px; background: {t.hairline}; }}
        QSlider::sub-page:horizontal {{ height: 4px; border-radius: 2px;
                                        background: {t.accent_strong}; }}
        QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -7px 0;
                                      border-radius: 9px; background: #fbfcfe;
                                      border: 1px solid rgba(29, 36, 48, 0.18); }}
        QSlider::handle:horizontal:hover {{ background: {t.accent}; }}
        QToolTip {{ color: {t.text}; background: {t.canvas}; border: 1px solid {t.hairline};
                    border-radius: 8px; padding: 4px 8px; }}
    """


def prepare_surface(window) -> None:
    """Call in the constructor of every GLASS_SURFACE window, before it is shown."""
    from .native_glass import glass_available
    if glass_available():
        window.setAttribute(Qt.WA_TranslucentBackground)


def apply_surface(window) -> None:
    """Glass window on macOS, solid window background everywhere else."""
    from .native_glass import attach_window_material
    glass = attach_window_material(window)
    if glass:
        window.setStyleSheet('QMainWindow, QDialog { background: transparent; }')
    layout = window.layout() if window.inherits('QDialog') else None
    if layout is not None:
        # With glass the content runs under the transparent title bar.
        layout.setContentsMargins(20, 46 if glass else 20, 20, 16)
        layout.setSpacing(12)


class _SurfaceFilter(QObject):
    """Gives every window that sets GLASS_SURFACE its material the first time it shows."""

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Show and getattr(watched, 'GLASS_SURFACE', False)
                and not watched.property('glassApplied')):
            watched.setProperty('glassApplied', True)
            apply_surface(watched)
        return False


def install(app) -> None:
    app.setStyleSheet(stylesheet())
    app.styleHints().colorSchemeChanged.connect(lambda _: app.setStyleSheet(stylesheet()))
    app._surface_filter = _SurfaceFilter(app)
    app.installEventFilter(app._surface_filter)
