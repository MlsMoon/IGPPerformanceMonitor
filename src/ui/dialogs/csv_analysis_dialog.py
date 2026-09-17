"""CSV analysis dialog — offline data visualization for imported captures."""

from __future__ import annotations

import os
from statistics import mean, median
from typing import Callable

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QWidget,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
)

from src.i18n import tr
from src.models import FrameData, format_display_outputs
from src.core.csv_importer import ImportResult, group_frames_by_app, compute_gpu_estimate
from src.core.filters import iqr_filter_series
from src.core.stutter_analysis import (
    FIXED_33_MS, FIXED_50_MS, analyze_stutter, elapsed_frame_series,
)
from src.ui import theme
from src.ui.theme import apply_to_plot, card_qss, system_bar_qss
from src.ui.chart_base import ChartCard, _pen, _prepare_series, next_palette_color

Extractor = Callable[[FrameData], float | None]


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _numeric_values(frames: list[FrameData], extractor: Extractor) -> list[float]:
    vals: list[float] = []
    for f in frames:
        try:
            v = extractor(f)
        except (TypeError, ValueError):
            continue
        if v is None:
            continue
        vals.append(float(v))
    return vals


def _coverage(frames: list[FrameData], extractor: Extractor) -> tuple[int, int, float]:
    total = len(frames)
    valid = len(_numeric_values(frames, extractor))
    pct = (valid / total * 100.0) if total else 0.0
    return valid, total, pct


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    idx = min(len(vals) - 1, max(0, int(len(vals) * pct)))
    return vals[idx]


def _fmt(v: float | None, suffix: str = "", precision: int = 1) -> str:
    if v is None:
        return "N/A"
    return f"{v:.{precision}f}{suffix}"


def _elapsed_dt(frame: FrameData) -> float:
    dt = (frame.ms_between_presents or 16.667) / 1000.0
    return dt if dt > 0 else 16.667 / 1000.0


class CsvAnalysisDialog(QDialog):
    """Dialog displaying imported CSV data as an offline analysis report."""

    def __init__(self, result: ImportResult, parent=None):
        super().__init__(parent)
        self._result = result
        self._frames = result.frames or []
        self._grouped = group_frames_by_app(self._frames)
        self._process_colors: dict[str, str] = {}
        self._cards: dict[str, ChartCard] = {}
        self._card_layouts: dict[str, tuple[QGridLayout, int, int, int, int, tuple[str, ...]]] = {}
        self._maximized_card: str | None = None
        self._duration_s = sum(_elapsed_dt(f) for f in self._frames)

        self.setWindowTitle(tr("analysis_title"))
        self.setMinimumSize(1200, 780)
        self._init_ui()
        self._plot_all()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(self._build_system_info_label())
        layout.addWidget(self._build_summary_panel())

        tabs = QTabWidget(self)
        tabs.addTab(self._build_performance_tab(), "Performance")
        tabs.addTab(self._build_metrics_tab(), "System / Process Metrics")
        tabs.addTab(self._build_stutter_tab(), "Stutter")
        tabs.addTab(self._build_quality_tab(), "Data Quality")
        layout.addWidget(tabs, 1)

    def _build_system_info_label(self) -> QFrame:
        """Slim themed chip bar (mirrors the live view)."""
        info = self._result.system_info
        if info:
            text = (
                f"CPU: {info.cpu_name}  |  "
                f"GPU: {info.gpu_name}  |  "
                f"RAM: {info.ram_total_gb} GB  |  "
                f"Display: {format_display_outputs(info)}"
            )
        else:
            text = tr("no_data_placeholder")
        t = theme.current_theme()
        bar = QFrame()
        bar.setObjectName("SystemBar")
        bar.setStyleSheet(system_bar_qss(t))
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 5, 12, 5)
        lay.setSpacing(18)
        for seg in text.split(" | "):
            seg = seg.strip()
            if not seg:
                continue
            chip = QLabel(seg)
            chip.setObjectName("SysChip")
            is_gpu = seg.lower().startswith("gpu")
            color = t.accent[3] if is_gpu else t.text_secondary
            chip.setStyleSheet(f"color: {color}; font-size: 9pt;")
            lay.addWidget(chip)
        lay.addStretch()
        return bar

    def _summary_card(self, title: str, value: str, subtitle: str = "") -> QLabel:
        t = theme.current_theme()
        sub = (
            f"<br><span style='font-size:9pt;color:{t.text_muted}'>{subtitle}</span>"
            if subtitle else ""
        )
        label = QLabel(
            f"<span style='color:{t.text_secondary};font-size:9pt'>{title}</span>"
            f"<br><span style='font-size:18pt;font-weight:700;color:{t.text_primary}'>{value}</span>"
            f"{sub}"
        )
        label.setMinimumWidth(150)
        label.setStyleSheet(
            f"QLabel {{ background:{t.card_bg}; border:1px solid {t.border};"
            f" border-radius:8px; padding:8px 12px; }}"
        )
        return label

    def _build_summary_panel(self) -> QWidget:
        frames = self._frames
        fps_vals = _numeric_values(frames, lambda f: f.fps if f.fps and f.fps > 0 else None)
        ft_vals = _numeric_values(frames, lambda f: f.ms_between_presents if f.ms_between_presents and f.ms_between_presents > 0 else None)
        cpu_cov = _coverage(frames, lambda f: f.app_cpu_percent)
        mem_cov = _coverage(frames, lambda f: f.app_memory_mb)
        vram_cov = _coverage(frames, lambda f: f.gpu_vram_percent)
        app_gpu_cov = _coverage(frames, lambda f: f.app_gpu_percent)

        root = QWidget(self)
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._summary_card("File", os.path.basename(self._result.file_path), ", ".join(self._result.monitored_apps or [])))
        row.addWidget(self._summary_card("Frames", str(len(frames)), f"Duration {_fmt(self._duration_s, 's', 1)}"))
        row.addWidget(self._summary_card("FPS", _fmt(mean(fps_vals) if fps_vals else None, "", 1), f"median {_fmt(median(fps_vals) if fps_vals else None)}"))
        row.addWidget(self._summary_card("1% Low", _fmt(_percentile(fps_vals, 0.01), "", 1), f"max FT {_fmt(max(ft_vals) if ft_vals else None, ' ms', 1)}"))
        row.addWidget(self._summary_card("Coverage", f"CPU {cpu_cov[2]:.0f}%", f"Mem {mem_cov[2]:.0f}% / GPU {app_gpu_cov[2]:.0f}% / VRAM {vram_cov[2]:.0f}%"))
        return root

    def _build_performance_tab(self) -> QWidget:
        tab = QWidget(self)
        grid = QGridLayout(tab)
        grid.setSpacing(6)
        fps = self._add_card(grid, "fps", "FPS (raw export)", "FPS", 0, 0,
                             accent_key="0", fill=True)
        ft = self._add_card(grid, "frame_time", "Frame Time", "ms", 1, 0,
                            accent_key="0")
        fps.plot.setYRange(0, 300)
        ft.plot.setYRange(0, 50)
        return tab

    def _build_metrics_tab(self) -> QWidget:
        tab = QWidget(self)
        grid = QGridLayout(tab)
        grid.setSpacing(6)
        self._add_card(grid, "cpu", "CPU %", "%", 0, 0, accent_key="2")
        self._add_card(grid, "memory", "Memory (MB)", "MB", 0, 1, accent_key="1")
        self._add_card(grid, "gpu", "GPU %", "%", 1, 0, accent_key="3")
        self._add_card(grid, "vram", "VRAM %", "%", 1, 1, accent_key="vram")
        return tab

    def _build_stutter_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)

        self._stutter_result = analyze_stutter(self._frames)
        layout.addWidget(self._build_stutter_summary_panel())

        grid = QGridLayout()
        grid.setSpacing(6)
        ft_card = self._add_card(grid, "stutter_frame_time", "Frame Time + Stutter Thresholds", "ms", 0, 0,
                                 accent_key="warn", fill=False)
        ft_card.plot.setYRange(0, 80)
        layout.addLayout(grid, 1)

        layout.addWidget(QLabel("Per-app stutter summary"))
        layout.addWidget(self._build_stutter_summary_table(), 1)
        layout.addWidget(QLabel("Worst stutter events"))
        layout.addWidget(self._build_stutter_events_table(), 1)
        return tab

    def _build_stutter_summary_panel(self) -> QWidget:
        summaries = self._stutter_result.summaries
        total_frames = sum(s.frame_count for s in summaries)
        total_33 = sum(s.fixed_33_count for s in summaries)
        total_50 = sum(s.fixed_50_count for s in summaries)
        total_spikes = sum(s.dynamic_spike_count for s in summaries)
        worst = max((s.max_frame_time_ms or 0.0 for s in summaries), default=0.0)
        p001 = min((s.p001_low_fps for s in summaries if s.p001_low_fps is not None), default=None)
        p01 = min((s.p01_low_fps for s in summaries if s.p01_low_fps is not None), default=None)
        p05 = min((s.p05_low_fps for s in summaries if s.p05_low_fps is not None), default=None)

        root = QWidget(self)
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._summary_card("Analyzed Frames", str(total_frames), f"{len(summaries)} app(s)"))
        row.addWidget(self._summary_card("0.1% Low", _fmt(p001, "", 1), f"1% {_fmt(p01)} / 5% {_fmt(p05)}"))
        row.addWidget(self._summary_card(">33.3ms", str(total_33), f">50ms {total_50}"))
        row.addWidget(self._summary_card("Dynamic Spikes", str(total_spikes), ">2x rolling median"))
        row.addWidget(self._summary_card("Worst Frame", _fmt(worst if worst else None, " ms", 1), "max frame time"))
        return root

    def _build_stutter_summary_table(self) -> QTableWidget:
        headers = [
            "App", "Frames", "Avg FPS", "0.1% Low", "1% Low", "5% Low",
            "Avg FT", "Max FT", ">33.3ms", ">50ms", "Spikes", "Worst Time",
        ]
        rows = self._stutter_result.summaries
        table = QTableWidget(self)
        table.setColumnCount(len(headers))
        table.setRowCount(len(rows))
        table.setHorizontalHeaderLabels(headers)
        for row, s in enumerate(rows):
            values = [
                s.app,
                str(s.frame_count),
                _fmt(s.avg_fps, "", 1),
                _fmt(s.p001_low_fps, "", 1),
                _fmt(s.p01_low_fps, "", 1),
                _fmt(s.p05_low_fps, "", 1),
                _fmt(s.avg_frame_time_ms, " ms", 2),
                _fmt(s.max_frame_time_ms, " ms", 2),
                str(s.fixed_33_count),
                str(s.fixed_50_count),
                str(s.dynamic_spike_count),
                _fmt(s.worst_time_s, " s", 2),
            ]
            for col, text in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(text))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        return table

    def _build_stutter_events_table(self) -> QTableWidget:
        events = self._stutter_result.events[:50]
        headers = ["App", "Time(s)", "FrameTime", "FPS", "Kind", "Severity"]
        table = QTableWidget(self)
        table.setColumnCount(len(headers))
        table.setRowCount(len(events))
        table.setHorizontalHeaderLabels(headers)
        for row, e in enumerate(events):
            values = [
                e.app,
                f"{e.time_s:.2f}",
                f"{e.frame_time_ms:.2f} ms",
                _fmt(e.fps, "", 1),
                e.kind,
                f"{e.severity:.2f}x",
            ]
            for col, text in enumerate(values):
                table.setItem(row, col, QTableWidgetItem(text))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        return table

    def _build_quality_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Data coverage (valid points / total frames). Missing values are not plotted as zero."))
        table = QTableWidget(self)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Metric", "Valid", "Total", "Coverage", "Notes"])
        metrics: list[tuple[str, Extractor, str]] = [
            ("FPS", lambda f: f.fps, "Exported/derived FPS"),
            ("Frame Time", lambda f: f.ms_between_presents, "PresentMon FrameTime"),
            ("App Memory", lambda f: f.app_memory_mb, "Enriched CSV column"),
            ("App CPU", lambda f: f.app_cpu_percent, "Total share (÷ logical cores)"),
            ("App CPU Cores", lambda f: f.app_cpu_cores, "Cores used (per-core % ÷ 100)"),
            ("Total CPU", lambda f: f.total_cpu_percent, "Enriched CSV column"),
            ("App GPU", lambda f: f.app_gpu_percent, "NVML per-process; may be NA"),
            ("Total GPU", lambda f: f.total_gpu_percent, "NVML total GPU"),
            ("RAM Used", lambda f: f.total_ram_used_gb, "System RAM used"),
            ("VRAM %", lambda f: f.gpu_vram_percent, "System VRAM usage"),
        ]
        table.setRowCount(len(metrics))
        for row, (name, extractor, note) in enumerate(metrics):
            valid, total, pct = _coverage(self._frames, extractor)
            for col, text in enumerate([name, str(valid), str(total), f"{pct:.1f}%", note]):
                table.setItem(row, col, QTableWidgetItem(text))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        layout.addWidget(table, 1)

        spikes = self._build_spikes_table()
        layout.addWidget(QLabel("Top frame-time spikes / lowest FPS samples"))
        layout.addWidget(spikes, 1)
        return tab

    def _build_spikes_table(self) -> QTableWidget:
        rows: list[tuple[str, float, float, str]] = []
        elapsed = 0.0
        for f in self._frames:
            elapsed += _elapsed_dt(f)
            app = f.application or f"pid_{f.process_id}"
            if f.ms_between_presents and f.ms_between_presents > 0:
                rows.append(("FrameTime", elapsed, f.ms_between_presents, app))
            if f.fps is not None and f.fps > 0:
                rows.append(("Low FPS", elapsed, f.fps, app))
        ft_top = sorted([r for r in rows if r[0] == "FrameTime"], key=lambda r: r[2], reverse=True)[:10]
        fps_low = sorted([r for r in rows if r[0] == "Low FPS"], key=lambda r: r[2])[:10]
        combined = ft_top + fps_low
        table = QTableWidget(self)
        table.setColumnCount(4)
        table.setRowCount(len(combined))
        table.setHorizontalHeaderLabels(["Type", "Time(s)", "Value", "App"])
        for row, (kind, t, value, app) in enumerate(combined):
            vals = [kind, f"{t:.2f}", f"{value:.2f}", app]
            for col, text in enumerate(vals):
                table.setItem(row, col, QTableWidgetItem(text))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        return table

    # ------------------------------------------------------------------
    # Chart construction / interaction
    # ------------------------------------------------------------------

    def _add_card(self, layout: QGridLayout, name: str, title: str, y_label: str,
                  row: int, col: int, accent_key: str = "0", fill: bool = False) -> ChartCard:
        t = theme.current_theme()
        card = ChartCard(name, title, accent_key=accent_key, fill=fill, parent=self)
        apply_to_plot(card.plot, t)
        card.plot.setLabel("left", y_label, **{"color": t.text_secondary})
        card.plot.setLabel("bottom", tr("label_elapsed_time"), units="s",
                           **{"color": t.text_secondary})
        card.plot.addLegend()
        card.maximize_requested.connect(self._toggle_maximize)
        layout.addWidget(card, row, col)
        group = tuple(self._cards.keys()) + (name,)
        # group is updated below for all cards in this layout
        self._cards[name] = card
        self._card_layouts[name] = (layout, row, col, 1, 1, group)
        names_in_layout = [n for n, (lay, *_rest) in self._card_layouts.items() if lay is layout]
        group = tuple(names_in_layout)
        for n in names_in_layout:
            lay, r, c, rs, cs, _old = self._card_layouts[n]
            self._card_layouts[n] = (lay, r, c, rs, cs, group)
        return card

    def _toggle_maximize(self, name: str):
        if self._maximized_card == name:
            self._restore_cards()
            return
        self._restore_cards()
        layout, _r, _c, _rs, _cs, group = self._card_layouts[name]
        card = self._cards[name]
        for n in group:
            self._cards[n].setVisible(n == name)
        layout.removeWidget(card)
        layout.addWidget(card, 0, 0, 2, 2)
        card.set_maximized_state(True)
        card.plot.getViewBox().enableAutoRange()
        self._maximized_card = name

    def _restore_cards(self):
        if not self._maximized_card:
            return
        for n, card in self._cards.items():
            layout, row, col, rs, cs, _group = self._card_layouts[n]
            layout.removeWidget(card)
            layout.addWidget(card, row, col, rs, cs)
            card.setVisible(True)
            card.set_maximized_state(False)
            card.plot.getViewBox().disableAutoRange()
        self._maximized_card = None

    # ------------------------------------------------------------------
    # Series / plotting
    # ------------------------------------------------------------------

    def _get_color(self, process_name: str) -> str:
        return next_palette_color(self._process_colors, process_name)

    def _build_series(self, frames: list[FrameData], extractor: Extractor) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        elapsed = 0.0
        for f in frames:
            elapsed += _elapsed_dt(f)
            try:
                val = extractor(f)
            except (TypeError, ValueError):
                continue
            if val is None:
                continue
            result.append((elapsed, float(val)))
        return result

    def _plot_series(self, card_name: str, series: list[tuple[float, float]], label: str, color: str, width: float = 2.0):
        data = _prepare_series(series, filter_outliers=False)
        if not data:
            return
        times, vals = zip(*data)
        self._cards[card_name].plot.plot(list(times), list(vals), pen=_pen(color, width), name=label)

    def _plot_all(self):
        for proc, frames in self._grouped.items():
            color = self._get_color(proc)
            self._plot_series("fps", self._build_series(frames, lambda f: f.fps), proc, color)
            self._plot_series("frame_time", self._build_series(frames, lambda f: f.ms_between_presents), proc, color)
            self._plot_series(
                "stutter_frame_time",
                [(t, ft) for t, _frame, ft in elapsed_frame_series(frames)],
                proc,
                color,
            )
            self._plot_series("memory", self._build_series(frames, lambda f: f.app_memory_mb), proc, color)
            self._plot_series("cpu", self._build_series(frames, lambda f: f.app_cpu_percent), f"{proc} CPU", color)
            self._plot_series(
                "gpu",
                self._build_series(frames, lambda f: f.app_gpu_percent if f.app_gpu_percent is not None else compute_gpu_estimate(f.ms_gpu_busy, f.ms_between_presents)),
                f"{proc} GPU", color,
            )

        # System-wide series
        t = theme.current_theme()
        self._plot_series("cpu", self._build_series(self._frames, lambda f: f.total_cpu_percent), tr("total_cpu"), t.total_cpu, 2.5)
        self._plot_series("memory", self._build_series(self._frames, lambda f: f.total_ram_used_gb * 1024 if f.total_ram_used_gb is not None else None), tr("total_ram"), t.total_ram, 2.5)
        self._plot_series("gpu", self._build_series(self._frames, lambda f: f.total_gpu_percent), tr("total_gpu"), t.total_gpu, 2.5)
        self._plot_series("vram", self._build_series(self._frames, lambda f: f.gpu_vram_percent), tr("vram"), t.vram, 2.5)

        stutter_plot = self._cards.get("stutter_frame_time")
        if stutter_plot is not None:
            x_max = max(self._duration_s, 1.0)
            stutter_plot.plot.plot([0, x_max], [FIXED_33_MS, FIXED_33_MS],
                                   pen=pg.mkPen(t.warn, width=1, style=Qt.DashLine),
                                   name="33.3ms")
            stutter_plot.plot.plot([0, x_max], [FIXED_50_MS, FIXED_50_MS],
                                   pen=pg.mkPen(t.bad, width=1, style=Qt.DashLine),
                                   name="50ms")

        x_max = max(self._duration_s, 1.0)
        for card in self._cards.values():
            card.plot.setXRange(0, x_max)
            card.plot.getViewBox().autoRange()
