"""Main application window."""

import math
import sys
from pathlib import Path

from PyQt5.QtCore import QByteArray, QPointF, QRectF, Qt, QTimer, QUrl
from PyQt5.QtGui import (
    QColor, QDesktopServices, QIcon, QKeySequence, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PyQt5.QtWidgets import (
    QAction, QActionGroup, QApplication, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QMainWindow, QMenuBar, QMessageBox, QSplitter, QStatusBar,
    QVBoxLayout, QWidget,
)

from src.i18n import LOCALE_NATIVE_NAMES, UI_LOCALES, get_locale, set_locale, tr
from src.models import SessionConfig, frame_series_key
from src.core.capture_session import CaptureSession
from src.core.csv_importer import import_file
from src.core.app_info import APP_VERSION, APP_BUILD, GITHUB_REPO_URL, is_dev_mode
from src.core.app_update_service import AppUpdateService
from src.ui.panels.process_panel import ProcessPanel
from src.ui.chart_base import CHART_REGISTRY
from src.ui.views.monitor_view import MonitorView
from src.ui.views.overlay_window import OverlayWindow
from src.ui.dialogs.csv_export import CsvExportDialog
from src.ui.dialogs.csv_analysis_dialog import CsvAnalysisDialog
from src.core import app_config
from src.ui.dialogs.changelog_dialog import ChangelogDialog
from src.ui.dialogs.user_manual import UserManualDialog
from src.ui.dialogs.shortcuts_dialog import ShortcutsDialog
from src.ui.dialogs.update_progress import ManifestWorker, UpdateProgressDialog
from src.ui import theme, win_chrome
import logging

logger = logging.getLogger(__name__)


def _resolve_icon_path() -> Path:
    """Return the path to the app icon, handling frozen vs dev mode."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "."))
    else:
        base = Path(__file__).resolve().parents[2]
    return base / "assets" / "icon.png"


def _menu_gutter_icon() -> QIcon:
    """Transparent icon that occupies the check column on plain menu rows."""
    pix = QPixmap(16, 16)
    pix.fill(Qt.transparent)
    return QIcon(pix)


_MENU_ICON_PX = 16


def _paint_menu_glyph(painter: QPainter, kind: str, color: QColor) -> None:
    """Stroke a 16×16 monochrome glyph in the current painter (logical px)."""
    pen = QPen(color, 1.4)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    if kind == "file":
        painter.drawRoundedRect(QRectF(4.0, 2.5, 8.0, 11.0), 1.2, 1.2)
        painter.drawLine(QPointF(6.0, 6.0), QPointF(10.5, 6.0))
        painter.drawLine(QPointF(6.0, 8.5), QPointF(10.5, 8.5))
        painter.drawLine(QPointF(6.0, 11.0), QPointF(9.0, 11.0))
        return
    if kind == "view":
        eye = QPainterPath()
        eye.moveTo(1.5, 8.0)
        eye.quadTo(8.0, 2.5, 14.5, 8.0)
        eye.quadTo(8.0, 13.5, 1.5, 8.0)
        painter.drawPath(eye)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(6.4, 6.4, 3.2, 3.2))
        painter.setBrush(Qt.NoBrush)
        return
    if kind == "settings":
        cx, cy = 8.0, 8.0
        painter.drawEllipse(QPointF(cx, cy), 3.0, 3.0)
        for i in range(6):
            ang = math.radians(i * 60.0 - 90.0)
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            painter.drawLine(
                QPointF(cx + 4.2 * cos_a, cy + 4.2 * sin_a),
                QPointF(cx + 6.5 * cos_a, cy + 6.5 * sin_a),
            )
        return
    painter.drawEllipse(QRectF(2.0, 2.0, 12.0, 12.0))
    mark = QPainterPath()
    mark.moveTo(5.6, 6.2)
    mark.cubicTo(5.6, 3.8, 10.4, 3.8, 10.4, 6.2)
    mark.cubicTo(10.4, 7.6, 8.0, 7.4, 8.0, 9.2)
    painter.drawPath(mark)
    painter.setBrush(color)
    painter.drawEllipse(QPointF(8.0, 11.6), 0.8, 0.8)


class _GlyphMenuBar(QMenuBar):
    """Menubar that paints 16px glyphs beside titles.

    Fusion draws a menubar item as icon *or* text. Putting a QIcon on
    ``menuAction()`` therefore hid File / 文件. Glyphs live in left padding
    instead, keyed by the action's ``menu_kind`` property.
    """

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = QColor(theme.current_theme().text_secondary)
        for action in self.actions():
            kind = action.property("menu_kind")
            if not kind:
                continue
            geo = self.actionGeometry(action)
            painter.save()
            painter.translate(
                geo.x() + 6,
                geo.y() + (geo.height() - _MENU_ICON_PX) // 2,
            )
            _paint_menu_glyph(painter, kind, color)
            painter.restore()


def _align_mixed_menu(menu) -> None:
    """Line up plain rows with checkable rows in the same menu.

    Qt 5.15.2's stylesheet style indents only checkable items (QTBUG-90242).
    A transparent icon on the others occupies the same gutter.
    """
    icon = _menu_gutter_icon()
    for action in menu.actions():
        if action.isSeparator() or action.isCheckable():
            continue
        if action.icon().isNull():
            action.setIcon(icon)
            action.setIconVisibleInMenu(True)


class MainWindow(QMainWindow):
    """IGP Performance Monitor main window."""

    def __init__(self):
        super().__init__()
        self._dev_badge: QLabel | None = None
        self._apply_window_title()
        self.setMinimumSize(1000, 680)

        # App icon
        icon_path = _resolve_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._session = CaptureSession()
        self._data_store = self._session.data_store
        self._wrapper = self._session.wrapper
        self._sampler = self._session.sampler
        self._overlays: dict[int, OverlayWindow] = {}
        self._screen_hook_handle = None
        self._overlays_suppressed = False      # F9 master hide for all overlays
        self._click_through = app_config.get("overlay_click_through", False)
        self._manifest_worker: ManifestWorker | None = None
        self._manifest_job = ""
        self._update_check_silent = False
        self._check_update_action: QAction | None = None
        self._version_history_action: QAction | None = None

        # Apply the persisted theme's global stylesheet before building UI so
        # every widget is created already themed.
        theme.apply_app_qss()

        self._init_ui()
        self._connect_signals()
        self._restore_window_state()
        # Theme the native title bar before the first paint, so the window never
        # flashes the default light chrome.
        win_chrome.apply_to_widget(self)
        theme.theme_changed_signal().connect(self._on_theme_changed)

        # Packaged EXE: silently check for updates shortly after startup.
        # Dev mode is skipped inside _auto_check_update().
        QTimer.singleShot(1500, self._auto_check_update)
        QTimer.singleShot(0, self._connect_screen_change_hooks)

    def _init_ui(self):
        # Order matters: the View menu reads chart state off the monitor view.
        self.setCentralWidget(self._build_central())
        self.setMenuBar(self._build_menu_bar())
        self.setStatusBar(self._build_status_bar())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_central(self) -> QWidget:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 6)
        root.setSpacing(0)

        self._monitor_view = MonitorView(self._data_store)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._build_side_panel())
        self._splitter.addWidget(self._monitor_view)
        # The side panel keeps its width; the charts absorb any extra space.
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([340, 960])  # sensible initial sizes for 1080p
        root.addWidget(self._splitter)
        return central

    def _build_side_panel(self) -> QWidget:
        """Process picker + status hint, stretched to the full window height."""
        side = QWidget()
        layout = QVBoxLayout(side)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(6)

        self._process_panel = ProcessPanel()
        layout.addWidget(self._process_panel, 1)

        self._status_label = QLabel(tr("status_ready_hint"))
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(self._status_label_qss())
        layout.addWidget(self._status_label)

        side.setMinimumWidth(300)
        return side

    def _apply_window_title(self):
        if is_dev_mode():
            self.setWindowTitle(tr("window_title_dev", tr("window_title")))
        else:
            self.setWindowTitle(tr("window_title"))

    def _apply_dev_badge_style(self):
        if self._dev_badge is None:
            return
        t = theme.current_theme()
        fg = t.window_bg if t.is_dark else t.text_primary
        self._dev_badge.setStyleSheet(
            f"QLabel#DevModeBadge {{ background-color: {t.warn}; color: {fg};"
            f" font-weight: 700; font-size: 9pt; padding: 2px 8px;"
            f" border-radius: {theme.RADIUS_CHIP}px; }}"
        )

    def _build_status_bar(self) -> QStatusBar:
        # Window chrome is themed via the global QApplication stylesheet
        # (theme.apply_app_qss); no widget-level stylesheet here.
        self._status_bar = QStatusBar()
        self._status_bar.setSizeGripEnabled(True)
        self._status_bar.showMessage(tr("status_ready"))
        if is_dev_mode():
            self._dev_badge = QLabel(tr("dev_badge"))
            self._dev_badge.setObjectName("DevModeBadge")
            self._apply_dev_badge_style()
            self._status_bar.addPermanentWidget(self._dev_badge)
        return self._status_bar

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> QMenuBar:
        menu_bar = _GlyphMenuBar()
        self._menu_file = menu_bar.addMenu(tr("menu_file"))
        self._build_file_menu(self._menu_file)
        self._menu_view = menu_bar.addMenu(tr("menu_view"))
        self._build_view_menu(self._menu_view)
        self._menu_settings = menu_bar.addMenu(tr("menu_settings"))
        self._build_settings_menu(self._menu_settings)
        self._menu_help = menu_bar.addMenu(tr("menu_help"))
        self._build_help_menu(self._menu_help)
        self._apply_menu_bar_icons()
        return menu_bar

    def _apply_menu_bar_icons(self) -> None:
        for kind, menu in (
            ("file", self._menu_file),
            ("view", self._menu_view),
            ("settings", self._menu_settings),
            ("help", self._menu_help),
        ):
            menu.menuAction().setProperty("menu_kind", kind)
        bar = self.menuBar()
        if bar is not None:
            bar.update()

    def _add_action(self, menu, label_key: str, slot, shortcut: str = "") -> QAction:
        action = QAction(tr(label_key), self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _add_toggle(self, menu, label_key: str, slot, *,
                    checked: bool = False, shortcut: str = "") -> QAction:
        """Checkable menu entry. Checked *before* connecting, so no spurious emit."""
        action = QAction(tr(label_key), self)
        action.setCheckable(True)
        action.setChecked(checked)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.toggled.connect(slot)
        menu.addAction(action)
        return action

    def _build_file_menu(self, menu) -> None:
        self._add_action(menu, "menu_capture_toggle", self._toggle_capture, "F5")
        menu.addSeparator()
        self._add_action(menu, "menu_import_csv", self._import_csv, "Ctrl+I")
        menu.addSeparator()
        self._add_action(menu, "export_csv_action", self._export_csv, "Ctrl+E")

    def _build_view_menu(self, menu) -> None:
        # Chart visibility toggles (submenu) — single source: CHART_REGISTRY.
        charts_submenu = menu.addMenu(tr("menu_charts"))
        self._chart_visibility_actions: dict[str, QAction] = {
            spec.name: self._add_toggle(
                charts_submenu, spec.label_key,
                lambda checked, k=spec.name: self._monitor_view.set_chart_visible(k, checked),
                checked=self._monitor_view.is_chart_visible(spec.name),
            )
            for spec in CHART_REGISTRY
        }

        # Inline show/hide part on the performance page.
        self._charts_panel_action = self._add_toggle(
            menu, "menu_charts_panel", self._on_charts_panel_toggled,
            checked=self._monitor_view.is_visibility_panel_expanded(), shortcut="Ctrl+J")

        menu.addSeparator()
        self._add_action(menu, "menu_overlay_toggle", self._toggle_overlays_visible, "F9")
        _align_mixed_menu(menu)

    def _build_settings_menu(self, menu) -> None:
        self._dark_action = self._add_toggle(
            menu, "menu_dark_mode", self._on_dark_mode_toggled,
            checked=theme.current_theme().is_dark, shortcut="Ctrl+D")
        self._ontop_action = self._add_toggle(
            menu, "always_on_top", self._toggle_always_on_top, shortcut="Ctrl+T")
        self._click_through_action = self._add_toggle(
            menu, "menu_click_through", self._toggle_click_through,
            checked=self._click_through)
        lang_menu = menu.addMenu(tr("menu_language"))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        current = get_locale()
        for loc in UI_LOCALES:
            action = QAction(LOCALE_NATIVE_NAMES[loc], self)
            action.setCheckable(True)
            action.setData(loc)
            action.setChecked(loc == current)
            lang_group.addAction(action)
            lang_menu.addAction(action)
        lang_group.triggered.connect(self._on_language_chosen)
        _align_mixed_menu(menu)

    def _build_help_menu(self, menu) -> None:
        self._add_action(menu, "menu_shortcuts", self._show_shortcuts, "F1")
        self._add_action(menu, "menu_user_manual", self._show_user_manual)
        menu.addSeparator()
        self._check_update_action = self._add_action(
            menu, "menu_check_update", self._check_update)
        self._version_history_action = self._add_action(
            menu, "menu_version_history", self._show_version_history)
        self._add_action(menu, "menu_changelog", self._show_changelog)
        self._add_action(menu, "menu_github", self._open_github)
        menu.addSeparator()
        self._add_action(menu, "menu_about", self._show_about)

    def _connect_signals(self):
        self._process_panel.start_requested.connect(self._start_capture)
        self._process_panel.stop_requested.connect(self._stop_capture)
        self._wrapper.frame_captured.connect(self._on_frame)
        self._wrapper.capture_error.connect(self._on_error)
        self._wrapper.state_changed.connect(self._on_state_changed)
        self._wrapper.status_message.connect(self._on_status)
        # Keep View > Charts checkboxes in sync with the panel / right-click Hide.
        self._monitor_view.visibility_changed.connect(self._on_chart_visibility)
        self._monitor_view.visibility_panel_expanded_changed.connect(
            self._sync_charts_panel_action)
        # Sync the optional inline chart part after widgets settle.
        QTimer.singleShot(150, self._sync_charts_panel_action)

    def _connect_screen_change_hooks(self):
        """Re-fit chart axes when the window moves between monitors."""
        handle = self.windowHandle()
        if handle is None:
            QTimer.singleShot(50, self._connect_screen_change_hooks)
            return
        try:
            if handle is self._screen_hook_handle:
                return
            handle.screenChanged.connect(self._on_screen_changed)
            self._screen_hook_handle = handle
        except Exception:
            pass

    def _on_screen_changed(self, _screen):
        QTimer.singleShot(0, self._refresh_for_screen_change)

    def _refresh_for_screen_change(self):
        self._monitor_view.refresh_display_layout()

    def _start_capture(self):
        """Start PresentMon capture with system info gathering."""
        if not self._process_panel.has_processes():
            QMessageBox.warning(
                self, tr("no_processes_title"), tr("no_processes_text")
            )
            return

        instances, names = self._process_panel.live_capture_targets()
        if not instances and not names:
            QMessageBox.warning(
                self, tr("process_not_running_title"), tr("process_not_running_text")
            )
            return

        logger.info(
            "Starting capture for pids=%s names=%s",
            [i.pid for i in instances], names,
        )

        config = SessionConfig(
            process_names=names,
            process_ids=[i.pid for i in instances],
            process_id_names={i.pid: i.name for i in instances},
            process_labels={i.pid: i.compact_label() for i in instances},
            timed_seconds=self._process_panel.get_timed_seconds(),
        )
        self._session.start(config)

        wanted = {i.pid for i in instances}
        if wanted:
            for pid, ov in list(self._overlays.items()):
                if pid not in wanted:
                    ov.set_capture_active(False)
        for inst in instances:
            self._ensure_overlay(inst.pid, inst.compact_label()).set_capture_active(True)

    def _ensure_overlay(self, pid: int, label: str) -> OverlayWindow:
        """Get (creating if needed) the overlay for a process instance."""
        ov = self._overlays.get(pid)
        if ov is None:
            ov = OverlayWindow(label, pid=pid)
            ov.set_click_through(self._click_through)
            if self._overlays_suppressed:
                ov.set_suppressed(True)
            self._overlays[pid] = ov
        else:
            ov.set_app_name(label)
            ov.set_pid(pid)
        return ov

    def _stop_capture(self):
        self._session.stop(wait_ms=2000)
        frames = self._data_store.get_frame_count()
        self._status_bar.showMessage(tr("status_capture_stopped"))
        if frames == 0:
            QMessageBox.warning(
                self, tr("warn_no_frames_title"), tr("warn_no_frames_text"))

    def _on_frame(self, frame):
        count = self._data_store.get_frame_count()
        elapsed = self._data_store.get_elapsed_seconds()
        if count % 60 == 0:
            self._status_bar.showMessage(tr("status_capturing", count, elapsed))
        pid = frame.process_id
        if pid <= 0:
            return
        ov = self._overlays.get(pid)
        if ov is None:
            label = self._data_store.display_name(frame_series_key(frame))
            ov = self._ensure_overlay(pid, label)
            ov.set_capture_active(True)
        ov.update_frame(frame)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, tr("capture_error_title"), msg)
        self._status_bar.showMessage(tr("status_error", msg))

    def _on_state_changed(self, running: bool):
        self._process_panel.set_capture_state(running)
        self._monitor_view.set_capture_active(running)
        if running:
            self._status_bar.showMessage(tr("status_capture_running"))
            return
        # Every way a capture ends arrives here — the Stop button, the auto-stop
        # timer, the target process exiting, PresentMon failing to launch — so
        # this is the one place that can reliably retire the overlays. Doing it
        # in _stop_capture only covered the button.
        #
        # Only the stop direction belongs here: _overlays keeps entries from
        # earlier sessions, and starting is _start_capture's call because it
        # knows which apps are actually configured now.
        for ov in self._overlays.values():
            ov.set_capture_active(False)
        self._status_bar.showMessage(tr("status_capture_stopped"))

    def _on_status(self, msg: str):
        self._status_bar.showMessage(msg)

    # ------------------------------------------------------------------
    # Shortcuts / overlay controls / window-state persistence (Tier 0)
    # ------------------------------------------------------------------

    def _toggle_capture(self):
        """F5: start or stop capture based on current state."""
        if self._wrapper.is_running:
            self._stop_capture()
        else:
            self._start_capture()

    def _toggle_overlays_visible(self):
        """F9: master show/hide for all overlays."""
        self._overlays_suppressed = not self._overlays_suppressed
        for ov in self._overlays.values():
            ov.set_suppressed(self._overlays_suppressed)

    def _toggle_click_through(self, checked: bool):
        """Settings menu: toggle mouse click-through on all overlays (persisted)."""
        self._click_through = checked
        app_config.set("overlay_click_through", checked)
        for ov in self._overlays.values():
            ov.set_click_through(checked)

    def _show_shortcuts(self):
        """F1 / Help: open the keyboard-shortcuts reference dialog."""
        ShortcutsDialog(self).exec_()

    def _restore_window_state(self):
        """Restore saved geometry / splitter / always-on-top from config."""
        geo = app_config.get("window_geometry")
        if isinstance(geo, str) and geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
        if getattr(self, "_splitter", None) is not None:
            state = app_config.get("splitter_state")
            if isinstance(state, str) and state:
                self._splitter.restoreState(QByteArray.fromBase64(state.encode()))
        if app_config.get("always_on_top", False) and getattr(self, "_ontop_action", None):
            self._ontop_action.blockSignals(True)
            self._ontop_action.setChecked(True)
            self._ontop_action.blockSignals(False)
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

    def _toggle_always_on_top(self, checked: bool):
        """Toggle the main window always-on-top state."""
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()  # re-show needed after setWindowFlags
        QTimer.singleShot(0, self._connect_screen_change_hooks)

    def _on_dark_mode_toggled(self, checked: bool):
        """Switch theme from the Settings → Dark Mode action."""
        theme.set_theme("dark" if checked else "light")

    def _on_theme_changed(self):
        """Re-apply global QSS and re-sync the toggle after a theme switch."""
        theme.apply_app_qss()
        self._apply_menu_bar_icons()
        self._status_label.setStyleSheet(self._status_label_qss())
        self._apply_dev_badge_style()
        # Re-sync the checkbox without re-emitting toggled (avoids feedback loop).
        self._dark_action.blockSignals(True)
        self._dark_action.setChecked(theme.current_theme().is_dark)
        self._dark_action.blockSignals(False)

    def _status_label_qss(self) -> str:
        return theme.muted_placeholder_qss(padding="4px")

    def _on_chart_visibility(self, name: str, visible: bool):
        """Re-sync the View > Charts checkbox (blocked) on external changes."""
        act = self._chart_visibility_actions.get(name)
        if act is not None:
            act.blockSignals(True)
            act.setChecked(visible)
            act.blockSignals(False)

    def _on_charts_panel_toggled(self, checked: bool):
        self._monitor_view.set_visibility_panel_expanded(checked)
        self._sync_charts_panel_action()

    def _sync_charts_panel_action(self, _expanded: bool | None = None):
        vis = self._monitor_view.is_visibility_panel_expanded()
        self._charts_panel_action.blockSignals(True)
        self._charts_panel_action.setChecked(vis)
        self._charts_panel_action.blockSignals(False)

    def _import_csv(self):
        """Import CSV and open analysis dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self, tr("menu_import_csv"), "", tr("import_file_filter"))
        if not path:
            return
        try:
            result = import_file(path)
            if not result.frames:
                QMessageBox.warning(self, tr("analysis_title"), tr("analysis_no_data"))
                return
            dialog = CsvAnalysisDialog(result, self)
            dialog.exec_()
        except Exception as e:
            logger.exception("Failed to import CSV")
            QMessageBox.critical(self, tr("analysis_title"), f"Import failed:\n{e}")

    def _export_csv(self):
        dialog = CsvExportDialog(self._data_store, self)
        dialog.exec_()

    def _check_update(self):
        """Manual update check (shows all results/errors)."""
        self._run_update_check(silent=False)

    def _auto_check_update(self):
        """Startup auto-check: packaged EXE only; quiet unless an update exists."""
        if not getattr(sys, "frozen", False):
            return
        self._run_update_check(silent=True)

    def _run_update_check(self, silent: bool = False):
        """Check for updates and optionally prompt to install.

        silent=True is used for startup auto-check: no modal for no-update or
        network/JSON errors, but still prompts when an update is available.
        Dev mode returns on the GUI thread with no network.
        """
        self._update_check_silent = silent
        if not getattr(sys, "frozen", False):
            if not silent:
                QMessageBox.information(
                    self,
                    tr("update_check_title"),
                    tr("update_dev_mode", APP_VERSION),
                )
            return
        self._start_manifest_job("check")

    def _set_update_actions_enabled(self, enabled: bool) -> None:
        if self._check_update_action is not None:
            self._check_update_action.setEnabled(enabled)
        if self._version_history_action is not None:
            self._version_history_action.setEnabled(enabled)

    def _start_manifest_job(self, job: str) -> None:
        if self._manifest_worker is not None and self._manifest_worker.isRunning():
            return
        worker = ManifestWorker(AppUpdateService(), job, self)
        worker.check_finished.connect(self._on_update_check_finished)
        worker.manifest_finished.connect(self._on_version_history_finished)
        worker.failed.connect(self._on_manifest_failed)
        worker.finished.connect(self._on_manifest_worker_finished)
        self._manifest_worker = worker
        self._manifest_job = job
        self._set_update_actions_enabled(False)
        self._status_bar.showMessage(tr("update_checking"))
        worker.start()

    def _on_manifest_worker_finished(self) -> None:
        self._set_update_actions_enabled(True)
        worker = self._manifest_worker
        self._manifest_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_update_check_finished(self, result) -> None:
        self._status_bar.showMessage(tr("status_ready"))
        if result.status == "update_available":
            answer = QMessageBox.question(
                self,
                tr("update_available_title"),
                tr(
                    "update_available_text",
                    result.current_version,
                    result.remote_version,
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
            manifest = result.remote_manifest
            if manifest is None:
                QMessageBox.critical(
                    self, tr("update_check_title"),
                    tr("update_install_failed", "No manifest available"),
                )
                return
            self._run_install(AppUpdateService(), manifest, tr("update_check_title"))
            return
        if self._update_check_silent:
            return
        QMessageBox.information(
            self,
            tr("update_check_title"),
            tr("update_up_to_date", result.current_version),
        )

    def _on_manifest_failed(self, message: str) -> None:
        self._status_bar.showMessage(tr("status_ready"))
        if self._manifest_job == "check" and self._update_check_silent:
            logger.warning("Startup update check failed: %s", message)
            return
        title = (
            tr("rollback_title") if self._manifest_job == "manifest"
            else tr("update_check_title")
        )
        QMessageBox.critical(self, title, tr("update_check_failed", message))

    def _run_install(self, service: AppUpdateService, manifest: dict, title: str):
        """Download + install behind a progress dialog, then restart on success."""
        dialog = UpdateProgressDialog(service, manifest, title, self)
        accepted = dialog.exec_() == QDialog.Accepted

        if not accepted:
            if dialog.error:
                logger.error("Update install failed: %s", dialog.error)
                QMessageBox.critical(
                    self, title, tr("update_install_failed", dialog.error))
            self._status_bar.showMessage(tr("status_ready"))
            return

        if dialog.result is not None and dialog.result.should_exit:
            self._status_bar.showMessage(tr("update_installing"))
            self.close()

    def _open_github(self):
        """Open the public repository in the default browser."""
        QDesktopServices.openUrl(QUrl(GITHUB_REPO_URL))

    def _show_about(self):
        """Show version info dialog."""
        version_str = APP_VERSION + (f" (build {APP_BUILD})" if APP_BUILD else "")
        QMessageBox.about(
            self,
            tr("about_title"),
            tr("about_text", version_str),
        )

    def _show_changelog(self):
        """Show the changelog dialog."""
        ChangelogDialog(self).exec_()

    def _show_user_manual(self):
        """Show the bundled user guide for the current UI locale."""
        UserManualDialog(self).exec_()

    def _show_version_history(self):
        """Fetch the manifest and offer rollback to the previous release."""
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self, tr("rollback_title"), tr("update_dev_mode", APP_VERSION))
            return
        self._start_manifest_job("manifest")

    def _on_version_history_finished(self, manifest: dict) -> None:
        self._status_bar.showMessage(tr("status_ready"))
        previous = manifest.get("previous")
        if not previous or not isinstance(previous, dict):
            QMessageBox.information(
                self, tr("rollback_title"), tr("rollback_no_previous"))
            return
        prev_ver = str(previous.get("version", "?"))
        answer = QMessageBox.question(
            self, tr("rollback_title"),
            tr("rollback_text", APP_VERSION, prev_ver),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._run_install(AppUpdateService(), previous, tr("rollback_title"))

    def _on_language_chosen(self, action: QAction) -> None:
        loc = action.data()
        if loc == get_locale() or loc not in UI_LOCALES:
            return
        app_config.set("locale", loc)
        set_locale(loc)
        self._replace_main_window()

    def _replace_main_window(self) -> None:
        """Rebuild the window in the same QApplication after a language switch."""
        replacement = MainWindow()
        app = QApplication.instance()
        if app is not None:
            app._igp_main_window = replacement
        replacement.show()
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.close()

    def showEvent(self, event):
        # Toggling always-on-top recreates the native window, which drops the
        # DWM attributes — re-apply them every time the window is shown.
        #
        # Deliberately no startup fade: this is a tool people open, read and
        # close, so an entrance animation is pure latency.
        super().showEvent(event)
        win_chrome.apply_to_widget(self)

    def closeEvent(self, event):
        worker = self._manifest_worker
        if worker is not None and worker.isRunning():
            worker.wait(8000)
        app_config.set("window_geometry", self.saveGeometry().toBase64().data().decode())
        if getattr(self, "_splitter", None) is not None:
            app_config.set("splitter_state", self._splitter.saveState().toBase64().data().decode())
        self._monitor_view.save_layout_state()
        app_config.set("always_on_top", self._ontop_action.isChecked())
        self._session.stop(wait_ms=3000)
        for ov in list(self._overlays.values()):
            ov.shutdown()
        self._overlays.clear()
        event.accept()
