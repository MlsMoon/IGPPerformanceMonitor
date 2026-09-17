"""Shared chart infrastructure for live monitoring and CSV analysis views.

Module-level helpers are extracted from monitor_view.py and csv_analysis_dialog.py
to avoid duplication.  ChartViewMixin provides concrete UI builders that both views
share via multiple inheritance.  Each chart is wrapped in a ChartCard that supports
double-click maximize and a right-click menu (maximize / restore / hide), a live
value badge, and a hover crosshair + tooltip.

Visual styling comes from :mod:`src.ui.theme` (light/dark, live-switchable).
"""

import psutil
from dataclasses import dataclass

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QEvent, QRectF, QSize, pyqtSignal
from PyQt5.QtWidgets import (
    QGridLayout, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMenu,
    QFrame,
)
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter

from src.i18n import tr
from src.models import ProcessStats
from src.core.filters import median_adaptive_filter
from src.ui import motion, theme
from src.ui.theme import (
    RADIUS_CARD, current_theme, apply_to_plot, fill_brush, metric_accent,
    value_badge_qss, icon_button_qss, system_bar_qss,
)

# ---------------------------------------------------------------------------
# Module-level shared constants / helpers
# ---------------------------------------------------------------------------

_MAX_PLOT_POINTS = 2000

# Y-axis ceilings for core/RAM charts (AutoSize is always available per card).
_CORE_COUNT = psutil.cpu_count(logical=True) or 16
_RAM_TOTAL_GB = max(8, round(psutil.virtual_memory().total / (1024 ** 3)))
_VRAM_CEILING_MB = 8192   # default Y ceiling for per-app VRAM (AutoSize available)


@dataclass(frozen=True)
class ChartSpec:
    """One chart in the live performance grid.

    ``kind`` is "line" (per-process or system series) or "multicore" (one curve
    per logical core + a bold average). ``span`` is "top" (full first row) or
    "cell" (fills the 2-column grid below). This registry is the single source
    of truth for both the grid layout and the show/hide control list.
    """
    name: str
    label_key: str
    kind: str          # "line" | "multicore"
    accent_key: str
    fill: bool
    span: str          # "top" | "cell"
    ymin: float
    ymax: float


# Display order. The first "top" chart spans the full first row; the rest fill a
# 2-column grid in order, reflowing without gaps when some are hidden.
CHART_REGISTRY: tuple[ChartSpec, ...] = (
    ChartSpec("fps",           "label_fps",               "line",      "0",         True,  "top",  0, 300),
    ChartSpec("frametime",     "label_frame_time_ms",     "line",      "1",         False, "cell", 0, 50),
    ChartSpec("cpu",           "label_cpu_percent",       "line",      "2",         False, "cell", 0, 100),
    ChartSpec("cpu_cores",     "label_cpu_cores_percent", "multicore", "2",         False, "cell", 0, 100),
    ChartSpec("app_cpu_cores", "label_app_cpu_cores",     "line",      "2",         False, "cell", 0, _CORE_COUNT),
    ChartSpec("mem",           "label_memory_mb",         "line",      "1",         False, "cell", 0, 4096),
    ChartSpec("system_ram",    "label_system_ram_gb",     "line",      "total_ram", False, "cell", 0, _RAM_TOTAL_GB),
    ChartSpec("gpu",           "label_gpu_percent",       "line",      "3",         False, "cell", 0, 100),
    ChartSpec("app_vram",      "label_app_vram_mb",       "line",      "vram",      False, "cell", 0, _VRAM_CEILING_MB),
    ChartSpec("gpu_power",     "label_gpu_power_w",       "line",      "gpu_power", False, "cell", 0, 300),
    ChartSpec("gpu_temp",      "label_gpu_temp_c",        "line",      "gpu_temp",  False, "cell", 0, 110),
    ChartSpec("vram",          "label_vram_percent",      "line",      "vram",      False, "cell", 0, 100),
)


def next_palette_color(colors: dict[str, str], name: str,
                       palette: list[str] | None = None) -> str:
    """Assign + cache a palette colour for *name* (round-robin by insertion order)."""
    if name not in colors:
        if palette is None:
            palette = theme.palette()
        colors[name] = palette[len(colors) % len(palette)]
    return colors[name]


_pg_pen_cache: dict[str, pg.mkPen] = {}


def _pen(color: str, width: float = 1.5) -> pg.mkPen:
    """Cached pen factory."""
    key = f"{color}_{width}"
    if key not in _pg_pen_cache:
        _pg_pen_cache[key] = pg.mkPen(color=color, width=width)
    return _pg_pen_cache[key]


def _downsample(data: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Min-max decimation to a fixed number of buckets for stable rendering."""
    n = len(data)
    if n <= _MAX_PLOT_POINTS:
        return data
    result: list[tuple[float, float]] = []
    for i in range(_MAX_PLOT_POINTS):
        start = int(i * n / _MAX_PLOT_POINTS)
        end = int((i + 1) * n / _MAX_PLOT_POINTS)
        chunk = data[start:end]
        if not chunk:
            continue
        t = chunk[-1][0]
        v_min = min(v for _, v in chunk)
        v_max = max(v for _, v in chunk)
        result.append((t, v_min))
        if v_min != v_max:
            result.append((t, v_max))
    return result


def _none_to_zero(v: float | None) -> float:
    return v if v is not None else 0.0


def _ema_smooth(
    data: list[tuple[float, float]], alpha: float = 0.3,
) -> list[tuple[float, float]]:
    """Exponential moving average for high-variance series (e.g. uncapped FPS).

    Applied to the rendered curve only — exported data stays raw.
    """
    if len(data) < 3:
        return list(data)
    result: list[tuple[float, float]] = [data[0]]
    prev = data[0][1]
    for t, v in data[1:]:
        prev = alpha * v + (1 - alpha) * prev
        result.append((t, prev))
    return result


def _prepare_series(
    data: list[tuple[float, float]],
    visible_start: float = 0.0,
    filter_outliers: bool = True,
    smooth_fps: bool = False,
) -> list[tuple[float, float]]:
    """Full pipeline: drop missing → clip → outlier filter → (optional FPS EMA) → downsample."""
    data = [(t, v) for t, v in data if v is not None and t >= visible_start]
    if not data:
        return []
    if filter_outliers:
        data = median_adaptive_filter(data)
    if smooth_fps:
        data = _ema_smooth(data)
    return _downsample(data)


# ---------------------------------------------------------------------------
# System info chip bar (shared by the live view and the analysis dialog)
# ---------------------------------------------------------------------------

class SystemChip(QLabel):
    """One system-info chip, elided to fit.

    A plain QLabel reports its full text width as its *minimum*, so a long GPU
    name used to push the whole window's minimum width past 1100 px. This keeps
    the natural width as the size hint but lets the chip shrink and elide, with
    the full value on the tooltip.
    """

    _MIN_WIDTH = 56

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("SysChip")
        self._full_text = text
        self.setToolTip(text)
        self._apply_elide()

    def _apply_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        width = max(self._MIN_WIDTH, self.width())
        super().setText(metrics.elidedText(self._full_text, Qt.ElideRight, width))

    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        return QSize(metrics.horizontalAdvance(self._full_text) + 4, metrics.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(self._MIN_WIDTH, QFontMetrics(self.font()).height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()


def build_system_chip_bar(text: str, t=None) -> QFrame:
    """Slim themed chip bar built from a ' | '-separated system-info string."""
    t = t or current_theme()
    bar = QFrame()
    bar.setObjectName("SystemBar")
    bar.setStyleSheet(system_bar_qss(t))
    bar.setAttribute(Qt.WA_StyledBackground, True)
    bar._igp_text = None
    lay = QHBoxLayout(bar)
    lay.setContentsMargins(14, 6, 14, 6)
    lay.setSpacing(18)
    populate_system_chip_bar(bar, text, t)
    return bar


def populate_system_chip_bar(bar: QFrame, text: str, t=None) -> None:
    """(Re)build the chip bar contents; no-op if the text is unchanged."""
    if getattr(bar, "_igp_text", None) == text:
        return
    bar._igp_text = text
    lay = bar.layout()
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    t = t or current_theme()
    for seg in text.split(" | "):
        seg = seg.strip()
        if not seg:
            continue
        chip = SystemChip(seg)
        is_gpu = seg.lower().startswith("gpu")
        color = t.accent[3] if is_gpu else t.text_secondary
        chip.setStyleSheet(f"color: {color}; font-size: 9pt;")
        lay.addWidget(chip)
    lay.addStretch()


# ---------------------------------------------------------------------------
# ChartCard — titled PlotWidget container with badge / crosshair / maximize
# ---------------------------------------------------------------------------

class ChartCard(QWidget):
    """A titled PlotWidget with a live value badge, crosshair, maximize/hide.

    ``accent_key`` selects the header dot + badge colour (a palette index or a
    semantic name — see theme.metric_accent). ``fill`` enables a translucent
    area fill under the primary (first) curve.

    The surface is painted here rather than styled with QSS, because QSS has no
    transitions: hovering shifts the fill over ~90ms instead of snapping, and one
    repaint is far cheaper than re-parsing a stylesheet per frame.
    """

    maximize_requested = pyqtSignal(str)
    hide_requested = pyqtSignal(str)

    def __init__(self, name: str, title: str, accent_key: str = "0",
                 fill: bool = False, parent=None):
        super().__init__(parent)
        self._name = name
        self._accent_key = accent_key
        self.fill = fill
        self._maximized = False
        self._is_top_chart = (name == "fps")
        t = current_theme()
        self._theme = t
        self._hover = 0.0
        self._hover_anim = motion.Transition(self, self._on_hover_tick)
        self.setObjectName("ChartCard")
        # Nothing styles this widget through QSS — paintEvent owns the surface.
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setMinimumHeight(220 if name == "fps" else 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(1)

        # Header: [dot] title … [value badge] [autosize] [maximize]
        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        header.setSpacing(6)

        accent = metric_accent(accent_key, t)
        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._dot.setStyleSheet(
            f"background: {accent}; border-radius: 5px; border: none;"
        )
        header.addWidget(self._dot)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(
            f"font-weight: 600; color: {t.text_primary}; padding: 0 2px;"
        )
        header.addWidget(self._title_label)
        header.addStretch()

        self._value_label = QLabel("")
        self._value_label.setStyleSheet(value_badge_qss(t, accent))
        self._value_label.hide()
        header.addWidget(self._value_label)

        self._autosize_btn = self._make_icon_button("↕", tr("chart_autosize"), self._on_autosize)
        header.addWidget(self._autosize_btn)
        self._max_btn = self._make_icon_button("⛶", tr("chart_maximize"), self._on_maximize)
        header.addWidget(self._max_btn)
        layout.addLayout(header)

        self._plot = pg.PlotWidget()
        layout.addWidget(self._plot, 1)
        self._plot.installEventFilter(self)

        # Hover crosshair + value tooltip (scans data items at hover time).
        self._crosshair = theme.Crosshair(self._plot, t)
        self.refresh_axis_layout()

    # -- flat surface + hover motion --

    def paintEvent(self, event):
        """A single filled shape. Hover shifts its colour, nothing else moves.

        No underline, glow or lift: anything that grows or slides on hover reads
        as decoration here, and these cards are hovered constantly.
        """
        t = self._theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.lerp_color(t.card_bg, t.hover_bg, self._hover))
        painter.drawRoundedRect(QRectF(self.rect()), RADIUS_CARD, RADIUS_CARD)

    def _on_hover_tick(self, value: float) -> None:
        self._hover = value
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hover_anim.to(1.0)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hover_anim.to(0.0)

    def _make_icon_button(self, icon: str, tooltip: str, slot) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFont(QFont("Segoe UI Symbol", 11))
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 22)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(icon_button_qss())
        btn.clicked.connect(slot)
        return btn

    # -- public API --

    @property
    def name(self) -> str:
        return self._name

    @property
    def plot(self) -> pg.PlotWidget:
        return self._plot

    def set_current_value(self, text: str | None) -> None:
        """Update the live value badge (hidden when text is falsy)."""
        if not text:
            self._value_label.hide()
            return
        self._value_label.setText(text)
        self._value_label.show()

    def set_maximized_state(self, maximized: bool):
        self._maximized = maximized
        self._max_btn.setText("❐" if maximized else "⛶")
        self._max_btn.setToolTip(tr("chart_restore") if maximized else tr("chart_maximize"))

    def apply_theme(self, t=None) -> None:
        """Re-skin this card after a theme switch (re-callable)."""
        t = t or current_theme()
        accent = metric_accent(self._accent_key, t)
        self._theme = t
        self._dot.setStyleSheet(f"background: {accent}; border-radius: 5px; border: none;")
        self._title_label.setStyleSheet(
            f"font-weight: 600; color: {t.text_primary}; padding: 0 2px;"
        )
        self._value_label.setStyleSheet(value_badge_qss(t, accent))
        for btn in (self._autosize_btn, self._max_btn):
            btn.setStyleSheet(icon_button_qss(t))
        apply_to_plot(self._plot, t)
        self.refresh_axis_layout()
        self._crosshair.restyle(t)
        self._restyle_legend(t)
        self.update()

    def _restyle_legend(self, t) -> None:
        leg = getattr(self._plot, "legend", None)
        if leg is None:
            return
        leg.setBrush(pg.mkBrush(QColor(t.card_bg)))
        leg.setPen(pg.mkPen(t.border))
        try:
            leg.setLabelTextColor(t.text_primary)
        except Exception:
            pass

    def refresh_axis_layout(self) -> None:
        """Recalculate axis density for the card's current size."""
        plot_size = self._plot.size()
        width = plot_size.width() or self.width()
        height = plot_size.height() or self.height()
        compact = (height < 150) or (not self._is_top_chart and height < 180)
        narrow = width < 430
        theme.apply_axis_layout(
            self._plot,
            compact=compact,
            narrow=narrow,
            top_chart=self._is_top_chart,
        )
        self._plot.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_axis_layout()

    # -- interactions --

    def _on_autosize(self):
        """Fit the plot to all visible data."""
        self._plot.getViewBox().autoRange()

    def _on_maximize(self):
        self.maximize_requested.emit(self._name)

    def eventFilter(self, obj, event):
        # Intercept double-click (maximize toggle) and right-click (menu) on the plot
        # before pyqtgraph's ViewBox consumes them.
        if obj is self._plot:
            if event.type() == QEvent.MouseButtonDblClick:
                self.maximize_requested.emit(self._name)
                return True
            if (event.type() == QEvent.MouseButtonPress
                    and event.button() == Qt.RightButton):
                self._show_context_menu(event.globalPos())
                return True
        return super().eventFilter(obj, event)

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        toggle = menu.addAction(
            tr("chart_restore") if self._maximized else tr("chart_maximize"))
        toggle.triggered.connect(
            lambda: self.maximize_requested.emit(self._name))
        if not self._maximized:
            hide = menu.addAction(tr("chart_hide"))
            hide.triggered.connect(lambda: self.hide_requested.emit(self._name))
        menu.exec_(global_pos)


# ---------------------------------------------------------------------------
# ChartViewMixin
# ---------------------------------------------------------------------------

class ChartViewMixin:
    """Shared chart / stats UI for MonitorView + CsvAnalysisDialog.

    Subclass must define `self._process_colors: dict[str, str]` in __init__
    and implement the abstract methods below.
    """

    # -------- Abstract — subclasses MUST implement --------

    def _get_all_stats(self) -> list[ProcessStats]:
        raise NotImplementedError

    def _get_process_names(self) -> list[str]:
        raise NotImplementedError

    def _get_series_data(self, proc: str, metric: str) -> list[tuple[float, float]]:
        """Return (elapsed_sec, value) pairs for *metric* ('fps','mem','cpu','gpu')."""
        raise NotImplementedError

    def _get_system_series(self, metric: str) -> list[tuple[float, float]]:
        """Return (elapsed_sec, value) pairs for system-wide *metric* ('cpu','gpu','vram')."""
        raise NotImplementedError

    def _get_elapsed_seconds(self) -> float:
        raise NotImplementedError

    def _get_system_info_text(self) -> str:
        raise NotImplementedError

    def _get_monitored_label_text(self) -> str:
        raise NotImplementedError

    def _get_monitored_apps(self) -> list[str]:
        """Configured (target) app names — includes idle apps with 0 frames."""
        raise NotImplementedError

    # -------- Concrete helpers --------

    def _init_chart_base(self) -> None:
        """Call in subclass __init__ to set up per-process color state."""
        if not hasattr(self, "_process_colors"):
            self._process_colors: dict[str, str] = {}

    def _get_color(self, process_name: str) -> str:
        return next_palette_color(self._process_colors, process_name)

    def _configure_plot(
        self, plot: pg.PlotWidget, y_label: str,
        y_min: float, y_max: float, history_seconds: float,
    ) -> None:
        """Apply standard axis/grid/range config to a PlotWidget."""
        t = current_theme()
        apply_to_plot(plot, t)
        plot.setLabel("left", y_label, **{"color": t.text_secondary})
        plot.setLabel("bottom", tr("label_elapsed_time"), units="s",
                      **{"color": t.text_secondary})
        plot.setXRange(0, history_seconds)
        plot.setYRange(y_min, y_max)
        plot.addLegend()
        plot.getViewBox().disableAutoRange()
        theme.apply_axis_layout(plot)

    def refresh_chart_axis_layout(self) -> None:
        """Re-apply per-card axis density after resize or screen changes."""
        for card in getattr(self, "_chart_widgets", {}).values():
            card.refresh_axis_layout()

    def _build_system_info_label(self) -> QFrame:
        """Slim chip-bar built from the system info text (split on ' | ')."""
        return build_system_chip_bar(self._get_system_info_text(), current_theme())

    def _populate_system_bar(self, bar: QFrame, text: str) -> None:
        populate_system_chip_bar(bar, text)

    def _refresh_system_info(self) -> None:
        """Re-populate the system bar (lazy fill / theme switch)."""
        bar = getattr(self, "_sys_info_bar", None)
        if bar is not None:
            self._populate_system_bar(bar, self._get_system_info_text())

    def _build_chart_grid(self, charts_layout: QGridLayout) -> dict[str, pg.PlotWidget]:
        """Build every chart in :data:`CHART_REGISTRY` and place the visible ones.

        Returns dict of plot widgets keyed by name. Card visibility is loaded
        from the AppData config file (see ``_load_visibility`` / :mod:`src.core.app_config`);
        hidden cards are still constructed (so toggling is instant) but kept off the grid.
        """
        charts_layout.setSpacing(5)
        h = getattr(self, '_history_seconds', 60)
        self._chart_widgets: dict[str, ChartCard] = {}
        self._chart_positions: dict[str, tuple[int, int, int, int]] = {}
        self._chart_visible: dict[str, bool] = self._load_visibility()
        self._maximized: str | None = None
        self._charts_layout = charts_layout
        self._chart_columns: int = 2  # adapted to charts-area width by refresh_display_layout

        plots: dict[str, pg.PlotWidget] = {}
        for spec in CHART_REGISTRY:
            title = tr(spec.label_key)
            card = ChartCard(spec.name, title, accent_key=spec.accent_key,
                             fill=spec.fill, parent=self)
            self._configure_plot(card.plot, title, spec.ymin, spec.ymax, h)
            card.maximize_requested.connect(self._toggle_maximize)
            card.hide_requested.connect(self._on_card_hide)
            self._chart_widgets[spec.name] = card
            plots[spec.name] = card.plot
        self._reflow()
        return plots

    # ---- statistics tiles ----

    @staticmethod
    def _fps_color(v: float, t) -> str:
        if v is None:
            return t.text_primary
        if v >= 55:
            return t.good
        if v >= 30:
            return t.warn
        return t.bad

    def _value_color(self, label_key: str, v: float, t) -> str:
        if v is None:
            return t.text_primary
        if label_key in ("stat_avg_fps", "stat_1p_low", "stat_5p_low"):
            return self._fps_color(v, t)
        return t.text_primary

    def _fmt_stat(self, v: float | None, suffix: str, precision: int) -> str:
        """Format one stat value; None (idle app) → em-dash placeholder."""
        if v is None:
            return "—"
        if precision == 0:
            return f"{int(round(v))}{suffix}"
        return f"{v:.{precision}f}{suffix}"

    def _stats_row(self, label_key: str, pairs: list[tuple[str, ProcessStats | None]],
                   field_fn, suffix: str, precision: int, t,
                   last: bool = False) -> QFrame:
        """One metric row. *pairs* is [(app, stats|None)]; idle apps render '—'.

        The last row drops its hairline so the separator never sits on the
        container's rounded bottom edge.
        """
        row = QFrame()
        row.setObjectName("StatsRowLast" if last else "StatsRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)

        label = QLabel(tr(label_key))
        label.setStyleSheet(f"color: {t.text_secondary}; font-size: 9pt;")
        lay.addWidget(label)
        lay.addStretch()

        if label_key == "stat_min_max":
            parts = [
                (f"{s.min_fps}/{s.max_fps}" if s is not None else "—")
                for _app, s in pairs
            ]
            text = " / ".join(parts)
            active_mins = [s.min_fps for _app, s in pairs if s is not None]
            color = self._fps_color(min(active_mins, default=0), t)
        else:
            parts = [
                (self._fmt_stat(field_fn(s), suffix, precision) if s is not None else "—")
                for _app, s in pairs
            ]
            text = " / ".join(parts)
            primary = next((field_fn(s) for _app, s in pairs if s is not None), None)
            color = self._value_color(label_key, primary, t)

        value = QLabel(text)
        value.setFont(QFont("Consolas", 11, QFont.Bold))
        value.setStyleSheet(f"color: {color};")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(value)
        return row

    def _build_stats_grid(self, grid: QGridLayout):
        """Populate *grid* with themed value tiles. Clears existing widgets first.

        Lists all *configured* apps (via _get_monitored_apps), so idle apps (0
        frames) still appear — greyed with a 'no frames' suffix and '—' values.
        """
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t = current_theme()
        apps = self._get_monitored_apps()
        if not apps:
            placeholder = QLabel(tr("no_data_placeholder"))
            placeholder.setStyleSheet(theme.muted_placeholder_qss(t, "10px"))
            grid.addWidget(placeholder, 0, 0)
            return

        all_stats = self._get_all_stats()
        by_name = {s.process_name: s for s in all_stats}
        pairs = [(app, by_name.get(app)) for app in apps[:4]]
        idle_apps = [app for app, s in pairs if s is None]

        # Hint line when any configured app hasn't produced frames.
        row = 0
        if idle_apps:
            hint = QLabel(tr("hint_idle_apps"))
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"color: {t.text_muted}; font-style: italic; font-size: 9pt;"
                f" padding: 2px 2px 6px 2px;")
            grid.addWidget(hint, row, 0)
            row += 1

        # Header: per-app coloured dots + names (idle ones greyed + suffix)
        header = QWidget()
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(2, 0, 2, 4)
        hlay.setSpacing(10)
        for app, s in pairs:
            idle = s is None
            c = t.text_muted if idle else self._get_color(app)
            suffix = f" · {tr('stat_no_frames')}" if idle else ""
            chip = QLabel(f"⬤ {app}{suffix}")
            chip.setStyleSheet(
                f"color: {c}; font-weight: 600; font-size: 9pt;"
                + ("" if idle else "")
            )
            hlay.addWidget(chip)
        hlay.addStretch()
        grid.addWidget(header, row, 0)
        row += 1

        metric_defs = [
            ("stat_frames", lambda s: s.frame_count, 0, ""),
            ("stat_avg_fps", lambda s: s.avg_fps, 1, ""),
            ("stat_avg_ft", lambda s: s.avg_frame_time_ms, 1, " ms"),
            ("stat_1p_low", lambda s: s.p99_fps, 1, ""),
            ("stat_5p_low", lambda s: s.p95_fps, 1, ""),
            ("stat_min_max", None, 0, ""),
            ("stat_avg_mem", lambda s: s.avg_app_memory_mb, 1, " MB"),
            ("stat_avg_cpu_app", lambda s: s.avg_app_cpu_percent, 1, "%"),
            ("stat_avg_gpu_app", lambda s: _none_to_zero(s.avg_app_gpu_percent), 1, "%"),
            ("stat_avg_vram", lambda s: s.avg_app_vram_mb, 1, " MB"),
        ]

        table = QFrame()
        table.setObjectName("StatsList")
        table.setStyleSheet(theme.stats_list_qss(t))
        rows = QVBoxLayout(table)
        rows.setContentsMargins(0, 2, 0, 2)
        rows.setSpacing(0)
        for i, (label_key, field_fn, precision, suffix) in enumerate(metric_defs):
            rows.addWidget(self._stats_row(
                label_key, pairs, field_fn, suffix, precision, t,
                last=(i == len(metric_defs) - 1),
            ))
        grid.addWidget(table, row, 0)
        row += 1
        grid.setRowStretch(row, 1)

    # -------- Curve update helpers --------

    def _update_chart_curves(
        self,
        plot: pg.PlotWidget,
        curves: dict[str, pg.PlotDataItem],
        metric: str,
    ):
        """Update per-process curves on *plot* for *metric*.

        FPS curves get extra EMA smoothing (uncapped-frame apps jump wildly);
        other metrics are sampler-paced slow series and need none.
        """
        procs = self._get_process_names()
        active: set[str] = set()
        smooth = (metric == "fps")
        accent = theme.palette()

        card = getattr(self, "_chart_widgets", {}).get(metric)
        fill_enabled = bool(getattr(card, "fill", False)) if card else False

        for i, proc in enumerate(procs):
            data = self._get_series_data(proc, metric)
            data = _prepare_series(data, smooth_fps=smooth)
            if not data:
                continue

            times, vals = zip(*data)
            color = accent[i % len(accent)]
            pen = _pen(color, 2.0)
            if proc not in curves:
                kw = dict(pen=pen, name=proc)
                if fill_enabled and i == 0:
                    kw["fillLevel"] = 0
                    kw["brush"] = fill_brush(color)
                curves[proc] = plot.plot(list(times), list(vals), **kw)
            else:
                item = curves[proc]
                item.setData(list(times), list(vals))
                item.setPen(pen)
                if fill_enabled and i == 0:
                    item.setFillLevel(0)
                    item.setBrush(fill_brush(color))
                else:
                    item.setFillLevel(None)
            active.add(proc)

        for stale in list(curves.keys() - active):
            plot.removeItem(curves.pop(stale))

    def _update_system_curve(
        self,
        plot: pg.PlotWidget,
        curve: pg.PlotDataItem | None,
        metric: str,
        color: str,
        name: str,
        width: float = 2.5,
        fill: bool = False,
    ) -> pg.PlotDataItem | None:
        """Update a single system-wide curve (Total CPU / Total GPU / VRAM).

        Returns the PlotDataItem (new or existing).
        """
        data = self._get_system_series(metric)
        data = _prepare_series(data)
        if not data:
            return curve

        times, vals = zip(*data)
        pen = _pen(color, width)
        if curve is None:
            kw = dict(pen=pen, name=name)
            if fill:
                kw["fillLevel"] = 0
                kw["brush"] = fill_brush(color)
            curve = plot.plot(list(times), list(vals), **kw)
        else:
            curve.setData(list(times), list(vals))
            curve.setPen(pen)
            if fill:
                curve.setFillLevel(0)
                curve.setBrush(fill_brush(color))
            else:
                curve.setFillLevel(None)
        return curve

    def _set_chart_xrange(self, plots: list[pg.PlotWidget], max_time: float):
        """Scroll all *plots* to the rolling window."""
        h = getattr(self, '_history_seconds', 60)
        x_max = max_time if max_time > h else h
        x_min = max_time - h if max_time > h else 0
        for p in plots:
            p.setXRange(x_min, x_max)

    # -------- Chart maximize / hide (shared by both views) --------

    def _toggle_maximize(self, name: str):
        if self._maximized == name:
            self._restore_grid()
        else:
            self._maximize_card(name)

    def _maximize_card(self, name: str):
        self._maximized = name
        layout = self._charts_layout
        for card in self._chart_widgets.values():
            layout.removeWidget(card)
        card = self._chart_widgets[name]
        layout.addWidget(card, 0, 0, 3, getattr(self, "_chart_columns", 2))
        card.set_maximized_state(True)
        card.plot.getViewBox().enableAutoRange()
        card.setVisible(True)
        for n, c in self._chart_widgets.items():
            if n != name:
                c.setVisible(False)

    def _restore_grid(self):
        """Exit maximize and re-pack only the visible cards (no gaps)."""
        self._maximized = None
        for card in self._chart_widgets.values():
            card.set_maximized_state(False)
            card.plot.getViewBox().disableAutoRange()
        self._reflow()

    def _on_card_hide(self, name: str):
        self.set_chart_visible(name, False)

    def set_chart_visible(self, name: str, visible: bool):
        """Show/hide a chart by name, reflow the grid, persist, and notify.

        Single entry point used by the menu, the visibility panel, and the
        card right-click Hide. Emits ``visibility_changed`` (if the subclass
        defines it) so every control stays in sync.
        """
        self._chart_visible[name] = visible
        self._persist_visibility()
        sig = getattr(self, "visibility_changed", None)
        if sig is not None:
            sig.emit(name, visible)
        if self._maximized:
            # Don't reflow while a card is maximized; _restore_grid handles it.
            return
        self._reflow()

    def is_chart_visible(self, name: str) -> bool:
        return self._chart_visible.get(name, True)

    # ---- Grid layout (reflow) ----

    @staticmethod
    def _compute_layout(visible: list[ChartSpec], n_cols: int = 2) -> dict[str, tuple[int, int, int, int]]:
        """Pack visible charts into an *n_cols*-wide grid.

        The first 'top' chart spans the whole first row (all n_cols); cells fill
        the n_cols-wide grid below. If no 'top' chart is visible, cells start at
        row 0 so nothing hovers over an empty top row. ``n_cols`` is set from the
        charts-area width by ``refresh_display_layout`` (see monitor_view).
        """
        n_cols = max(1, n_cols)
        pos: dict[str, tuple[int, int, int, int]] = {}
        top_done = False
        cell_idx = 0
        for spec in visible:
            if spec.span == "top" and not top_done:
                pos[spec.name] = (0, 0, 1, n_cols)
                top_done = True
            elif spec.span == "cell":
                row = (1 if top_done else 0) + cell_idx // n_cols
                col = cell_idx % n_cols
                pos[spec.name] = (row, col, 1, 1)
                cell_idx += 1
        return pos

    def _reflow(self):
        """Re-place every visible chart in the grid; hide the rest (no gaps)."""
        layout = self._charts_layout
        for card in self._chart_widgets.values():
            layout.removeWidget(card)
        visible = [s for s in CHART_REGISTRY if self._chart_visible.get(s.name, True)]
        positions = self._compute_layout(visible, getattr(self, "_chart_columns", 2))
        for name, (row, col, rs, cs) in positions.items():
            card = self._chart_widgets[name]
            layout.addWidget(card, row, col, rs, cs)
            self._chart_positions[name] = (row, col, rs, cs)
            card.setVisible(True)
        for name, card in self._chart_widgets.items():
            if name not in positions:
                card.setVisible(False)

    # ---- Visibility persistence (app_config) ----

    _VISIBILITY_KEY = "chart_visibility"

    def _default_visibility(self) -> dict[str, bool]:
        """All visible by default; GPU-only charts hidden when no GPU backend."""
        from src.core.system_metrics import gpu_available
        defaults = {spec.name: True for spec in CHART_REGISTRY}
        if not gpu_available():
            for name in ("gpu_power", "gpu_temp", "vram", "app_vram"):
                defaults[name] = False
        return defaults

    def _load_visibility(self) -> dict[str, bool]:
        from src.core import app_config
        defaults = self._default_visibility()
        stored = app_config.get(self._VISIBILITY_KEY, {}) or {}
        if not isinstance(stored, dict):
            stored = {}
        return {name: bool(stored.get(name, defaults[name])) for name in defaults}

    def _persist_visibility(self):
        from src.core import app_config
        app_config.set(self._VISIBILITY_KEY, self._chart_visible)

    # -------- Live theme switching --------

    def apply_theme(self, t=None) -> None:
        """Re-skin all chart cards + stats + system bar after a theme switch.

        Clears the per-card curve dicts so the next refresh rebuilds curves with
        themed pens and repopulates legends; maximized state is preserved.
        """
        t = t or current_theme()
        # Cards (plot bg/axes, header, badge, crosshair, legend).
        for card in getattr(self, "_chart_widgets", {}).values():
            leg = getattr(card.plot, "legend", None)
            if leg is not None:
                leg.clear()
            card.apply_theme(t)
        # Stats tiles + monitored label.
        if hasattr(self, "_stats_grid"):
            self._build_stats_grid(self._stats_grid)
        if hasattr(self, "_monitored_label") and self._monitored_label is not None:
            self._monitored_label.setStyleSheet(
                theme.monitored_label_qss(t)
            )
            self._monitored_label.setText(self._get_monitored_label_text())
        # System info chip bar.
        bar = getattr(self, "_sys_info_bar", None)
        if bar is not None:
            bar.setStyleSheet(system_bar_qss(t))
            bar._igp_text = None  # force re-populate with themed chip colours
            self._populate_system_bar(bar, self._get_system_info_text())
