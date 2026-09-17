"""Native Windows window-chrome theming (dark title bar).

Qt stylesheets only reach the client area — the title bar is drawn by DWM, so a
dark app shows a white strip along the top of every window until it opts in via
``DwmSetWindowAttribute``. This module applies the current :mod:`src.ui.theme`
colours to that non-client area.

Everything degrades silently: non-Windows platforms, older builds that reject an
attribute, and widgets without a native handle are all no-ops.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication

from src.ui.theme import Theme, current_theme, theme_changed_signal

_IS_WINDOWS = sys.platform == "win32"

# dwmapi.h attribute indices.
_USE_IMMERSIVE_DARK_MODE = 20      # Windows 10 build 19041+ / Windows 11
_USE_IMMERSIVE_DARK_MODE_LEGACY = 19   # Windows 10 builds 18985-19040
_BORDER_COLOR = 34                 # Windows 11 (build 22000+) only
_CAPTION_COLOR = 35
_TEXT_COLOR = 36


def _colorref(hex_color: str) -> int:
    """Convert ``#rrggbb`` to a Win32 COLORREF (0x00bbggrr)."""
    c = QColor(hex_color)
    return c.red() | (c.green() << 8) | (c.blue() << 16)


def _set_attribute(hwnd: int, attribute: int, value) -> bool:
    try:
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(attribute),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except (AttributeError, OSError):
        return False
    return result == 0


def apply_to_hwnd(hwnd: int, t: Theme | None = None) -> None:
    """Theme one native window's title bar and border."""
    if not _IS_WINDOWS or not hwnd:
        return
    t = t or current_theme()

    dark = ctypes.c_int(1 if t.is_dark else 0)
    if not _set_attribute(hwnd, _USE_IMMERSIVE_DARK_MODE, dark):
        _set_attribute(hwnd, _USE_IMMERSIVE_DARK_MODE_LEGACY, dark)

    # Windows 11 also lets us paint the caption ourselves, so the title bar uses
    # the app's own background instead of the generic system grey.
    _set_attribute(hwnd, _CAPTION_COLOR, ctypes.c_uint(_colorref(t.window_bg)))
    _set_attribute(hwnd, _TEXT_COLOR, ctypes.c_uint(_colorref(t.text_primary)))
    _set_attribute(hwnd, _BORDER_COLOR, ctypes.c_uint(_colorref(t.border)))


def apply_to_widget(widget, t: Theme | None = None) -> None:
    """Theme the title bar of a top-level widget (no-op for child widgets)."""
    if not _IS_WINDOWS or widget is None or not widget.isWindow():
        return
    try:
        hwnd = int(widget.winId())
    except (RuntimeError, TypeError, ValueError):
        return
    apply_to_hwnd(hwnd, t)


def refresh_all(t: Theme | None = None) -> None:
    """Re-apply to every existing top-level window (used after a theme switch)."""
    if not _IS_WINDOWS:
        return
    t = t or current_theme()
    for widget in QApplication.topLevelWidgets():
        apply_to_widget(widget, t)


def _on_focus_window_changed(window) -> None:
    """Catch windows we never touch directly (QMessageBox, native file dialogs)."""
    if window is None:
        return
    try:
        apply_to_hwnd(int(window.winId()))
    except (RuntimeError, TypeError, ValueError):
        pass


def install(app: QApplication) -> None:
    """Keep every window of *app* themed, including ones created later.

    ``focusWindowChanged`` is the cheap hook here: dialogs and message boxes take
    focus as they open, so they get themed without an app-wide event filter.
    """
    if not _IS_WINDOWS or app is None:
        return
    app.focusWindowChanged.connect(_on_focus_window_changed)
    theme_changed_signal().connect(refresh_all)
    refresh_all()
