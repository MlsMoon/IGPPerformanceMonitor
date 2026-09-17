"""Overlay window — one per monitored app, positioned at its top-left corner."""

import win32gui
import win32process
import win32con
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QMenu,
)
from PyQt5.QtGui import QColor, QFont

from src.models import FrameData
from src.core.csv_importer import compute_gpu_estimate
from src.i18n import tr
from src.ui import theme


# Offset of the overlay from the tracked window's top-left corner (px)
_OFFSET_X = 8
_OFFSET_Y = 8

# EMA factor for smoothing the displayed FPS (uncapped-frame apps jump wildly)
_FPS_EMA_ALPHA = 0.3


def find_main_window(pid: int) -> int | None:
    """Find the main (largest non-tool) top-level window for a PID.

    Returns None if not found. Picks the largest visible, non-toolwindow,
    titled top-level window — robust for multi-window apps (Unity editor,
    IDEs, browsers) where the old 'first match' heuristic picked the wrong
    panel/tool window.
    """
    best = None
    best_area = 0

    def enum_callback(hwnd, _):
        nonlocal best, best_area
        if not win32gui.IsWindowVisible(hwnd):
            return True
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid != pid:
            return True
        # skip tool windows / floating panels that aren't the main window
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return True
        if not win32gui.GetWindowText(hwnd):
            return True
        try:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
        except Exception:
            return True
        area = (r - l) * (b - t)
        if area > best_area:
            best_area = area
            best = hwnd
        return True

    win32gui.EnumWindows(enum_callback, None)
    return best


class OverlayWindow(QWidget):
    """Frameless always-on-top overlay for a SINGLE monitored app.

    One instance per app; each tracks its own app's main-window HWND and shows
    that app's real-time stats. MainWindow owns the dict of overlays.
    """

    def __init__(self, app_name: str, parent=None):
        super().__init__(parent)
        self._app_name = app_name
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._apply_style()
        theme.theme_changed_signal().connect(self._apply_style)

        self._pid: int | None = None
        self._tracked_hwnd: int | None = None  # cached main-window HWND for this app
        self._latest_frame: FrameData | None = None
        self._fps_ema: float | None = None
        self._shutting_down = False
        self._suppressed = False       # master hide (F9) — _update_position skips show
        self._title_font = QFont("Segoe UI", 9, QFont.Bold)
        self._data_font = QFont("Consolas", 10)

        self._init_ui()

        # Fast position-follow timer (~30fps). Cached HWND means we usually
        # only call GetWindowRect; EnumWindows runs only when the HWND is stale.
        self._pos_timer = QTimer(self)
        self._pos_timer.timeout.connect(self._update_position)
        self._pos_timer.start(33)

        # Display refresh timer (decoupled from frame rate). update_frame only
        # stores data + updates FPS EMA; this timer does the (expensive) setText.
        self._display_timer = QTimer(self)
        self._display_timer.timeout.connect(self._refresh_display)
        self._display_timer.start(250)

        self.setMinimumWidth(240)

    def _apply_style(self):
        t = theme.current_theme()
        bg = QColor(t.panel_bg)
        self.setStyleSheet(
            f"background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 220);"
            f" color: {t.text_primary}; border: 1px solid {t.border}; border-radius: 6px;"
        )

    def set_click_through(self, enabled: bool):
        """When enabled, mouse events pass through the overlay to the app below."""
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)

    def set_suppressed(self, suppressed: bool):
        """Master hide toggle (F9). Suppressed overlays stay hidden and are not
        re-shown by the position-follow timer."""
        self._suppressed = suppressed
        if suppressed:
            self.hide()

    def _init_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 8)
        self._layout.setSpacing(4)

        # App-name title (distinguishes multiple overlays)
        accent = theme.current_theme().accent[0]
        self._title_label = QLabel(self._app_name)
        self._title_label.setFont(self._title_font)
        self._title_label.setStyleSheet(f"color: {accent};")
        self._layout.addWidget(self._title_label)

        # Data rows
        na = tr("ov_dash")
        self._fps_label = QLabel(f"FPS: {na}")
        self._fps_label.setFont(self._data_font)
        self._layout.addWidget(self._fps_label)

        self._ft_label = QLabel(f"{tr('ov_frametime')}: {na} ms")
        self._ft_label.setFont(self._data_font)
        self._layout.addWidget(self._ft_label)

        self._mem_label = QLabel(f"{tr('ov_mem')}: {na} MB")
        self._mem_label.setFont(self._data_font)
        self._layout.addWidget(self._mem_label)

        self._cpu_label = QLabel(f"CPU: {na}%")
        self._cpu_label.setFont(self._data_font)
        self._layout.addWidget(self._cpu_label)

        self._gpu_label = QLabel(f"GPU: {na}%")
        self._gpu_label.setFont(self._data_font)
        self._layout.addWidget(self._gpu_label)

        self._vram_label = QLabel(f"VRAM: {na}%")
        self._vram_label.setFont(self._data_font)
        self._layout.addWidget(self._vram_label)

        self._sys_cpu_label = QLabel(f"{tr('ov_sys_cpu')}: {na}%")
        self._sys_cpu_label.setFont(self._data_font)
        self._layout.addWidget(self._sys_cpu_label)

        # Right-click menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self.adjustSize()

    # ------------------------------------------------------------------
    # Frame ingestion
    # ------------------------------------------------------------------

    def update_frame(self, frame: FrameData):
        """Store latest frame + update FPS EMA. Display refresh is timer-driven."""
        self._latest_frame = frame
        self._pid = frame.process_id or self._pid
        self._update_fps_ema(frame.fps)

    def _update_fps_ema(self, fps):
        """Per-frame EMA smoothing of FPS (uncapped-frame apps jump wildly)."""
        if fps is not None and fps > 0:
            if self._fps_ema is None:
                self._fps_ema = float(fps)
            else:
                self._fps_ema = _FPS_EMA_ALPHA * fps + (1 - _FPS_EMA_ALPHA) * self._fps_ema
        else:
            self._fps_ema = None

    # ------------------------------------------------------------------
    # Display (timer-driven, ~4fps)
    # ------------------------------------------------------------------

    def _refresh_display(self):
        """Update labels with latest frame data for this app."""
        f = self._latest_frame
        if f is None:
            na = tr("ov_na")
            self._fps_label.setText(f"FPS: {na}")
            self._ft_label.setText(f"{tr('ov_frametime')}: {na}")
            self._mem_label.setText(f"{tr('ov_mem')}: {na}")
            self._cpu_label.setText(f"CPU: {na}")
            self._gpu_label.setText(f"GPU: {na}")
            self._vram_label.setText(f"VRAM: {na}")
            self._sys_cpu_label.setText(f"{tr('ov_sys_cpu')}: {na}")
            return

        fps = f"{self._fps_ema:.0f}" if self._fps_ema is not None else "N/A"
        ft = f"{f.ms_between_presents:.1f} ms" if f.ms_between_presents and f.ms_between_presents > 0 else "N/A"
        mem = f"{f.app_memory_mb:.0f} MB" if f.app_memory_mb is not None else "N/A"
        if f.app_cpu_percent is None:
            cpu = "N/A"
        elif f.app_cpu_cores is not None:
            cpu = f"{f.app_cpu_percent:.1f}% · {f.app_cpu_cores:.1f}{tr('cpu_cores_suffix')}"
        else:
            cpu = f"{f.app_cpu_percent:.1f}%"
        # Prefer real NVML per-process GPU, fall back to PresentMon estimate
        if f.app_gpu_percent is not None:
            gpu = f"{f.app_gpu_percent:.0f}%"
        else:
            gpu_est = compute_gpu_estimate(f.ms_gpu_busy, f.ms_between_presents)
            gpu = f"{gpu_est:.0f}%" if gpu_est is not None and gpu_est >= 0 else "N/A"
        vram = f"{f.gpu_vram_percent:.0f}%" if f.gpu_vram_percent is not None else "N/A"
        sys_cpu = f"{f.total_cpu_percent:.1f}%" if f.total_cpu_percent is not None else "N/A"

        self._fps_label.setText(f"FPS: {fps}")
        self._ft_label.setText(f"{tr('ov_frametime')}: {ft}")
        self._mem_label.setText(f"{tr('ov_mem')}: {mem}")
        self._cpu_label.setText(f"CPU: {cpu}")
        self._gpu_label.setText(f"GPU: {gpu}")
        self._vram_label.setText(f"VRAM: {vram}")
        self._sys_cpu_label.setText(f"{tr('ov_sys_cpu')}: {sys_cpu}")

    # ------------------------------------------------------------------
    # Position tracking (~30fps, cached HWND)
    # ------------------------------------------------------------------

    def _update_position(self):
        """Follow this app's main window; hide when minimized/absent/no frame yet."""
        if self._shutting_down or self._suppressed:
            return
        pid = self._pid
        if not pid:
            return  # no frame received yet — nothing to track

        hwnd = self._tracked_hwnd
        if hwnd is None or not win32gui.IsWindow(hwnd):
            hwnd = find_main_window(pid)
            self._tracked_hwnd = hwnd
        if hwnd is None:
            self.hide()
            return

        try:
            if win32gui.IsIconic(hwnd) or not win32gui.IsWindowVisible(hwnd):
                self.hide()
                return
            left, top, _r, _b = win32gui.GetWindowRect(hwnd)
            self.show()
            self.move(left + _OFFSET_X, top + _OFFSET_Y)
        except Exception:
            self._tracked_hwnd = None

    def shutdown(self):
        """Stop timers and remove the top-level overlay during app shutdown."""
        self._shutting_down = True
        if self._pos_timer.isActive():
            self._pos_timer.stop()
        if self._display_timer.isActive():
            self._display_timer.stop()
        self.hide()
        self.deleteLater()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos):
        menu = QMenu(self)
        close_action = menu.addAction(tr("ov_close"))
        action = menu.exec_(self.mapToGlobal(pos))
        if action == close_action:
            self.hide()
