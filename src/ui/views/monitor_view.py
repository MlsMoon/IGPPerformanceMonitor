"""Real-time monitoring view — system info bar, chart grid, multi-app stats."""

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QByteArray, QEvent, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QLabel, QGridLayout, QWidget,
    QScrollArea, QSplitter,
)

from src.i18n import tr
from src.core import app_config
from src.core.data_store import DataStore
from src.models import ProcessStats, format_display_outputs
from src.config import DEFAULT_REFRESH_INTERVAL_MS, DEFAULT_CHART_HISTORY_SECONDS
from src.ui import theme
from src.ui.chart_base import (
    ChartViewMixin, CHART_REGISTRY, _pen, _prepare_series,
)
from src.ui.panels.chart_visibility_panel import ChartVisibilityPanel
from src.ui.panels.system_info_panel import SystemInfoPanel


# Per-process line charts (chart name == metric passed to _get_series_data).
_PROC_LINE_CHARTS = ("fps", "frametime", "mem", "cpu", "app_cpu_cores", "gpu", "app_vram")
# Charts with a system-wide overlay on top of per-process curves.
#   chart_name -> (series_metric, theme_color_attr, i18n_label_key)
_SYSTEM_OVERLAY = {
    "cpu": ("cpu", "total_cpu", "total_cpu"),
    "gpu": ("gpu", "total_gpu", "total_gpu"),
}
# System-only line charts: chart_name -> (metric, color_attr, label_key, fill)
_SYSTEM_ONLY = {
    "vram":       ("vram",      "vram",      "vram",               True),
    "system_ram": ("ram",       "total_ram", "label_system_ram_gb", False),
    "gpu_power":  ("gpu_power", "gpu_power", "label_gpu_power_w",  False),
    "gpu_temp":   ("gpu_temp",  "gpu_temp",  "label_gpu_temp_c",   False),
}

# Responsive chart grid: column count adapts to the charts-area width.
_MIN_CHART_CARD_W = 340   # min width (px) per chart card before dropping a column
_MAX_CHART_COLS = 4       # column cap (even on very wide windows)


class MonitorView(QWidget, ChartViewMixin):
    """Live charts and stats display, backed by DataStore."""

    # Emitted by ChartViewMixin.set_chart_visible so the menu + panel stay in sync.
    visibility_changed = pyqtSignal(str, bool)
    visibility_panel_expanded_changed = pyqtSignal(bool)

    def __init__(self, data_store: DataStore, parent=None):
        super().__init__(parent)
        self._data_store = data_store
        self._history_seconds = DEFAULT_CHART_HISTORY_SECONDS
        # When False (not capturing), the chart x-axis is frozen at its last
        # position instead of sliding with wall-clock elapsed time.
        self._capture_active = False
        self._init_chart_base()

        # Curve state keyed by chart name (lazy-filled on first refresh).
        self._plots: dict[str, pg.PlotWidget] = {}
        self._proc_curves: dict[str, dict[str, pg.PlotDataItem]] = {}
        self._sys_curves: dict[str, pg.PlotDataItem | None] = {}
        self._multicore_curves: dict[str, dict[object, pg.PlotDataItem]] = {}

        self._vis_panel: ChartVisibilityPanel | None = None
        self._sys_info_panel: SystemInfoPanel | None = None
        self._charts_group: QGroupBox | None = None

        self._init_ui()

        # Inline show/hide part is built in _init_ui; keep it synced with
        # QSettings and external visibility changes.
        self._vis_panel.sync_all(self._chart_visible)
        self.visibility_changed.connect(self._on_visibility_changed)

        # Fast timer (500 ms)
        self._chart_timer = QTimer(self)
        self._chart_timer.timeout.connect(self._refresh_charts)
        self._chart_timer.start(DEFAULT_REFRESH_INTERVAL_MS)

        # Slow timer (2 s)
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats)
        self._stats_timer.start(2000)

        # Live theme switching
        theme.theme_changed_signal().connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # ChartViewMixin abstract methods
    # ------------------------------------------------------------------

    def _get_all_stats(self) -> list[ProcessStats]:
        procs = self._data_store.get_process_names()
        all_stats = [self._data_store.compute_stats(p) for p in procs]
        return [s for s in all_stats if s is not None]

    def _get_process_names(self) -> list[str]:
        return self._data_store.get_process_names()

    def _get_series_data(self, proc: str, metric: str) -> list[tuple[float, float]]:
        if metric == "fps":
            return self._data_store.get_fps_history(proc)
        if metric == "frametime":
            # Frame time (ms) = 1000 / instantaneous fps (fps history is raw, not EMA).
            return [(t, 1000.0 / f) for t, f in self._data_store.get_fps_history(proc) if f]
        if metric == "mem":
            return self._data_store.get_memory_history(proc)
        if metric == "cpu":
            return self._data_store.get_cpu_history(proc)
        if metric == "app_cpu_cores":
            # Frame-based history (key=frame_series_key) — matches cpu/mem/gpu;
            # reading per_process_snapshots[proc.name()] would miss the curve when
            # PresentMon Application differs from psutil proc.name().
            return self._data_store.get_cpu_cores_history(proc)
        if metric == "gpu":
            return [(t, v) for t, v in self._data_store.get_gpu_history(proc) if v is not None]
        if metric == "app_vram":
            return self._data_store.get_app_vram_history(proc)
        return []

    def _get_system_series(self, metric: str) -> list[tuple[float, float]]:
        snaps = self._data_store.get_system_snapshots()
        if not snaps:
            return []
        if metric == "cpu":
            return [(s.timestamp, s.total_cpu_percent) for s in snaps]
        if metric == "gpu":
            return [(s.timestamp, s.total_gpu_percent) for s in snaps
                    if s.total_gpu_percent is not None]
        if metric == "vram":
            return [(s.timestamp, s.vram_percent) for s in snaps
                    if s.vram_percent is not None]
        if metric == "ram":
            return [(s.timestamp, s.total_ram_used_gb) for s in snaps
                    if s.total_ram_used_gb is not None]
        if metric == "gpu_power":
            return [(s.timestamp, s.gpu_power_w) for s in snaps
                    if s.gpu_power_w is not None]
        if metric == "gpu_temp":
            return [(s.timestamp, s.gpu_temp_c) for s in snaps
                    if s.gpu_temp_c is not None]
        return []

    def _get_elapsed_seconds(self) -> float:
        return self._data_store.get_elapsed_seconds()

    def set_capture_active(self, active: bool):
        """Tell the view whether a capture is running.

        When inactive, the chart x-axis stops advancing so frozen data stays in
        view instead of scrolling off as wall-clock elapsed time keeps growing.
        """
        self._capture_active = active

    def _get_system_info_text(self) -> str:
        info = self._data_store.get_system_info()
        if info is None:
            return ""
        return (
            f"CPU: {info.cpu_name}  |  "
            f"GPU: {info.gpu_name}  |  "
            f"RAM: {info.ram_total_gb} GB  |  "
            f"Display: {format_display_outputs(info)}"
        )

    def _get_monitored_label_text(self) -> str:
        apps = self._data_store.get_monitored_apps()
        if not apps:
            return ""
        return tr("monitored_apps_label", ", ".join(
            self._data_store.display_name(a) for a in apps))

    def _get_monitored_apps(self) -> list[str]:
        return self._data_store.get_monitored_apps()

    def _display_process_name(self, key: str) -> str:
        return self._data_store.display_name(key)

    # ------------------------------------------------------------------
    # UI construction (delegates to mixin)
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)
        # The main window already supplies the outer margin.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # System info chip bar — collapsible, expanded by default.
        self._sys_info_bar = self._build_system_info_label()
        self._sys_info_panel = SystemInfoPanel(self._sys_info_bar, self)
        layout.addWidget(self._sys_info_panel)

        self._vis_panel = ChartVisibilityPanel(
            CHART_REGISTRY, self._on_panel_toggle, self)
        self._vis_panel.expanded_changed.connect(self._on_visibility_panel_expanded)
        layout.addWidget(self._vis_panel)

        # Monitored apps — created empty and hidden; it only takes a row once a
        # capture gives it text (see _sync_monitored_label).
        t = theme.current_theme()
        self._monitored_label = QLabel("")
        self._monitored_label.setStyleSheet(theme.monitored_label_qss(t))
        self._monitored_label.hide()
        layout.addWidget(self._monitored_label)

        # Stats + Charts side by side, with a draggable divider.
        layout.addWidget(self._build_content_row(), 1)

    def _sync_monitored_label(self):
        """Show the 'Monitored: …' line only while it has something to say."""
        text = self._get_monitored_label_text()
        self._monitored_label.setText(text)
        self._monitored_label.setVisible(bool(text))

    def _build_content_row(self) -> QSplitter:
        content = QSplitter(Qt.Horizontal)
        content.setChildrenCollapsible(False)

        stats_group = QGroupBox(tr("live_statistics"))
        stats_group.setMinimumWidth(220)
        self._stats_grid = QGridLayout(stats_group)
        self._stats_grid.setSpacing(4)
        placeholder = QLabel(tr("no_data_placeholder"))
        placeholder.setStyleSheet(theme.muted_placeholder_qss())
        self._stats_grid.addWidget(placeholder, 0, 0)
        content.addWidget(stats_group)

        self._charts_group = QGroupBox(tr("performance_charts"))
        charts_group_layout = QVBoxLayout(self._charts_group)
        charts_group_layout.setContentsMargins(6, 6, 2, 6)
        charts_group_layout.setSpacing(0)

        self._charts_scroll = QScrollArea(self._charts_group)
        self._charts_scroll.setWidgetResizable(True)
        self._charts_scroll.setFrameShape(QScrollArea.NoFrame)
        self._charts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._charts_scroll.setObjectName("ChartsScrollArea")
        self._charts_scroll.viewport().installEventFilter(self)

        self._charts_content = QWidget()
        self._charts_content.setObjectName("ChartsScrollContent")
        charts_layout = QGridLayout(self._charts_content)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        self._plots = self._build_chart_grid(charts_layout)
        self._charts_scroll.setWidget(self._charts_content)
        charts_group_layout.addWidget(self._charts_scroll)
        content.addWidget(self._charts_group)

        # Stats keep their width; the chart grid absorbs the rest.
        content.setStretchFactor(0, 0)
        content.setStretchFactor(1, 1)
        content.setSizes([260, 900])
        self._content_splitter = content
        self._restore_content_splitter()
        return content

    _CONTENT_SPLITTER_KEY = "stats_charts_splitter_state"

    def _restore_content_splitter(self) -> None:
        state = app_config.get(self._CONTENT_SPLITTER_KEY)
        if isinstance(state, str) and state:
            self._content_splitter.restoreState(QByteArray.fromBase64(state.encode()))

    def save_layout_state(self) -> None:
        """Persist the stats/charts divider (called from MainWindow.closeEvent)."""
        splitter = getattr(self, "_content_splitter", None)
        if splitter is None:
            return
        app_config.set(
            self._CONTENT_SPLITTER_KEY,
            splitter.saveState().toBase64().data().decode(),
        )

    # ------------------------------------------------------------------
    # Chart refresh (fast, 500 ms)
    # ------------------------------------------------------------------

    def _latest_value(self, proc: str, metric: str) -> float | None:
        data = self._get_series_data(proc, metric)
        if not data:
            return None
        return data[-1][1]

    def _update_card_badges(self):
        """Push the latest values into each card's live value badge."""
        procs = self._get_process_names()
        proc = procs[0] if procs else None
        cards = self._chart_widgets

        def setv(name: str, text: str | None):
            card = cards.get(name)
            if card is not None:
                card.set_current_value(text)

        fps = self._latest_value(proc, "fps") if proc else None
        setv("fps", f"{fps:.0f}" if fps else None)
        mem = self._latest_value(proc, "mem") if proc else None
        setv("mem", f"{mem:.0f} MB" if mem is not None else None)
        cpu = self._latest_value(proc, "cpu") if proc else None
        setv("cpu", f"{cpu:.0f}%" if cpu is not None else None)

        snaps = self._data_store.get_system_snapshots()
        if snaps:
            s = snaps[-1]
            gpu = s.total_gpu_percent
            setv("gpu", f"{gpu:.0f}%" if gpu is not None else None)
            vram = s.vram_percent
            setv("vram", f"{vram:.0f}%" if vram is not None else None)

    def _refresh_charts(self):
        # Machine info is available before capture starts; keep it visible even
        # when no PresentMon frames have arrived yet.
        self._refresh_system_info()
        self._sync_monitored_label()

        procs = self._get_process_names()
        if not procs:
            return

        t = theme.current_theme()
        plots = self._plots

        # --- Per-process line charts ---
        for name in _PROC_LINE_CHARTS:
            self._update_chart_curves(
                plots[name], self._proc_curves.setdefault(name, {}), name)

        # --- System-wide overlays on the per-process CPU / GPU charts ---
        for chart_name, (metric, color_attr, label_key) in _SYSTEM_OVERLAY.items():
            self._sys_curves[chart_name] = self._update_system_curve(
                plots[chart_name], self._sys_curves.get(chart_name),
                metric, getattr(t, color_attr), tr(label_key))

        # --- System-only line charts ---
        for chart_name, (metric, color_attr, label_key, fill) in _SYSTEM_ONLY.items():
            self._sys_curves[chart_name] = self._update_system_curve(
                plots[chart_name], self._sys_curves.get(chart_name),
                metric, getattr(t, color_attr), tr(label_key), fill=fill)

        # --- Multi-core CPU utilization (one curve per core + bold average) ---
        self._update_multicore_curve(
            plots["cpu_cores"], self._multicore_curves.setdefault("cpu_cores", {}))

        # Live value badges
        self._update_card_badges()

        # X range: maximized chart auto-ranges; others scroll. Only advance the
        # rolling window while capturing — when idle the last window is kept so
        # the frozen data stays put (elapsed time keeps growing but we ignore it;
        # a new session resets the clock + clears data via start_session()).
        if not self._maximized and self._capture_active:
            self._set_chart_xrange(list(plots.values()), self._get_elapsed_seconds())

    def _update_multicore_curve(self, plot: pg.PlotWidget, curve_cache: dict):
        """One line per logical core (golden-angle hue spread) + a bold average.

        Curves are cached by core index; a string key ``"avg"`` holds the
        average. Stale cores (e.g. fewer cores than last session) are removed.
        """
        snaps = self._data_store.get_system_snapshots()
        if not snaps:
            return
        n = len(snaps[-1].per_core_cpu_percent or [])
        t = theme.current_theme()
        xs = [s.timestamp for s in snaps]
        active: set[object] = set()

        for i in range(n):
            ys = []
            for s in snaps:
                pc = s.per_core_cpu_percent
                ys.append(pc[i] if pc is not None and i < len(pc) else None)
            data = _prepare_series(list(zip(xs, ys)), filter_outliers=False)
            if not data:
                continue
            times, vals = zip(*data)
            pen = _pen(self._core_color(i), 1.0)
            if i not in curve_cache:
                curve_cache[i] = plot.plot(
                    list(times), list(vals), pen=pen, name=f"{tr('label_core')} {i}")
            else:
                item = curve_cache[i]
                item.setData(list(times), list(vals))
                item.setPen(pen)
            active.add(i)

        # Bold average = aggregate total CPU%.
        avg = _prepare_series(
            [(s.timestamp, s.total_cpu_percent) for s in snaps
             if s.total_cpu_percent is not None],
            filter_outliers=False)
        if avg:
            times, vals = zip(*avg)
            pen = _pen(t.total_cpu, 2.5)
            key = "avg"
            if key not in curve_cache:
                curve_cache[key] = plot.plot(
                    list(times), list(vals), pen=pen, name=tr("total_cpu"))
            else:
                item = curve_cache[key]
                item.setData(list(times), list(vals))
                item.setPen(pen)
            active.add(key)

        for stale in list(set(curve_cache) - active):
            plot.removeItem(curve_cache.pop(stale))

    @staticmethod
    def _core_color(i: int) -> str:
        """Distinct hue per core via the golden angle (readable for 8-32 cores)."""
        return QColor.fromHsv(int((i * 137.508) % 360), 215, 240).name()

    # ------------------------------------------------------------------
    # Stats refresh (slow, 2 s)
    # ------------------------------------------------------------------

    def _refresh_stats(self):
        if not self._get_process_names():
            return
        self._build_stats_grid(self._stats_grid)

    # ------------------------------------------------------------------
    # Inline chart visibility part
    # ------------------------------------------------------------------

    def _on_panel_toggle(self, name: str, checked: bool):
        self.set_chart_visible(name, checked)

    def _on_visibility_changed(self, name: str, visible: bool):
        # Back-sync the panel when the change came from the menu / right-click Hide.
        if self._vis_panel is not None:
            self._vis_panel.set_checked(name, visible)

    def _on_visibility_panel_expanded(self, expanded: bool):
        self.visibility_panel_expanded_changed.emit(expanded)

    def toggle_visibility_panel(self):
        self.set_visibility_panel_expanded(not self.is_visibility_panel_expanded())

    def set_visibility_panel_expanded(self, expanded: bool):
        if self._vis_panel is None:
            return
        self._vis_panel.set_expanded(expanded)

    def is_visibility_panel_expanded(self) -> bool:
        return self._vis_panel is not None and self._vis_panel.is_expanded()

    def set_system_info_expanded(self, expanded: bool):
        if self._sys_info_panel is None:
            return
        self._sys_info_panel.set_expanded(expanded)

    def is_system_info_expanded(self) -> bool:
        return self._sys_info_panel is not None and self._sys_info_panel.is_expanded()

    def refresh_display_layout(self):
        """Re-derive chart columns from the charts-area width, then refresh axes.

        Called on viewport/view resize and on screen changes. Reflow happens only
        when the column count actually changes, so dragging the window does not
        re-pack the grid every frame.
        """
        scroll = getattr(self, "_charts_scroll", None)
        width = scroll.viewport().width() if scroll is not None else 0
        n_cols = self._columns_for_width(width)
        if n_cols != getattr(self, "_chart_columns", 2):
            self._chart_columns = n_cols
            if not getattr(self, "_maximized", None):
                self._reflow()
        self.refresh_chart_axis_layout()
        self.update()

    def _columns_for_width(self, width: int) -> int:
        """Chart grid column count for a charts-area *width* (0/unknown → keep current)."""
        if width <= 0:
            return getattr(self, "_chart_columns", 2)
        return max(1, min(_MAX_CHART_COLS, width // _MIN_CHART_CARD_W))

    def eventFilter(self, obj, event):
        if (getattr(self, "_charts_scroll", None) is not None
                and obj is self._charts_scroll.viewport()
                and event.type() == QEvent.Resize):
            QTimer.singleShot(0, self.refresh_display_layout)
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_display_layout()

    # ------------------------------------------------------------------
    # Live theme switching
    # ------------------------------------------------------------------

    def _on_theme_changed(self):
        """Re-skin everything; recreate curves so pens + legends follow."""
        # Drop existing data items so the next refresh rebuilds them themed.
        for plot in self._plots.values():
            for item in list(plot.listDataItems()):
                plot.removeItem(item)
        for d in self._proc_curves.values():
            d.clear()
        self._proc_curves.clear()
        self._sys_curves.clear()
        for d in self._multicore_curves.values():
            d.clear()
        self._multicore_curves.clear()
        if self._vis_panel is not None:
            self._vis_panel.apply_theme()
        if self._sys_info_panel is not None:
            self._sys_info_panel.apply_theme()
        self.apply_theme()
        self._refresh_charts()
