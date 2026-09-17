"""Central theme system for the IGP Performance Monitor UI.

Provides:
- :class:`Theme` — a dataclass holding every colour used across the app.
- ``DARK`` / ``LIGHT`` presets (tuned for a performance monitor).
- A tiny manager (:func:`current_theme`, :func:`set_theme`, :func:`toggle_theme`)
  with JSON config-file persistence (see :mod:`src.core.app_config`) and a ``themeChanged`` signal.
- QSS generators (:func:`app_qss`, :func:`card_qss`, :func:`stats_list_qss`,
  :func:`system_bar_qss`, :func:`icon_button_qss`, :func:`value_badge_qss`).
- :func:`apply_to_plot` — applies bg / axis / grid styling to a pyqtgraph PlotWidget
  (re-callable, so live theme switching just re-runs it).
- :class:`Crosshair` — hover crosshair + value tooltip on a plot.

The metrics pipeline never imports this — it is presentation only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QApplication

# Anti-aliasing is the single biggest line-smoothness win; at our scale
# (≤5 charts × ≤2000 downsampled points, refreshed every 500 ms) it is cheap.
# Must be set before any plot is created — this module is imported at the top of
# chart_base.py / monitor_view.py, ahead of plot construction.
pg.setConfigOption("antialias", True)
# Use a slightly cleaner default font for pyqtgraph axes.
pg.setConfigOption("foreground", "#9aa3ad")


# ---------------------------------------------------------------------------
# Theme definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    """All colours for one visual theme.

    The design is flat: surfaces are separated by background contrast alone
    (window < panel < card), never by shadows or heavy outlines. ``border`` is a
    hairline reserved for inputs, lists and bar separators.
    """

    name: str
    is_dark: bool
    # Surfaces
    window_bg: str
    panel_bg: str          # group boxes / cards background
    card_bg: str           # chart card body
    border: str
    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    # Plot
    plot_bg: str
    plot_fg: str           # axis + grid + default text colour
    grid_alpha: float
    # Per-process accent line colours
    accent: list[str] = field(default_factory=list)
    # Semantic / system-series colours
    good: str = "#51cf66"
    warn: str = "#ffa94d"
    bad: str = "#ff6b6b"
    total_cpu: str = "#ff6b6b"
    total_gpu: str = "#cc5de8"
    vram: str = "#22d3ee"
    total_ram: str = "#ff6b6b"
    gpu_power: str = "#ffa94d"
    gpu_temp: str = "#ff6b6b"
    # List/table item selection background (deep purple — distinct from accent
    # blue, high contrast with white selection text in both themes)
    selection: str = "#9c36b5"
    selection_text: str = "#ffffff"
    # Fill alpha for area under curves (0-255)
    fill_alpha: int = 55
    # Flat interaction states
    hover_bg: str = "#232833"          # surface under the cursor
    input_bg: str = "#14171d"          # inputs / lists sit one step below panel


DARK = Theme(
    name="dark",
    is_dark=True,
    window_bg="#0f1115",
    panel_bg="#161920",
    card_bg="#1c2027",
    border="#262b34",
    text_primary="#e8ebf1",
    text_secondary="#9ba4af",
    text_muted="#69707b",
    # Charts sit flush inside their card — no inset panel look.
    plot_bg="#1c2027",
    plot_fg="#858d98",
    grid_alpha=0.11,
    accent=["#4dabf7", "#51cf66", "#ffa94d", "#cc5de8"],
    good="#51cf66",
    warn="#ffa94d",
    bad="#ff6b6b",
    total_cpu="#ff6b6b",
    total_gpu="#cc5de8",
    vram="#22d3ee",
    total_ram="#ff8787",
    gpu_power="#ffa94d",
    gpu_temp="#ff6b6b",
    selection="#9c36b5",
    selection_text="#ffffff",
    fill_alpha=55,
    hover_bg="#232833",
    input_bg="#14171d",
)

LIGHT = Theme(
    name="light",
    is_dark=False,
    window_bg="#f0f2f6",
    panel_bg="#f7f8fb",
    card_bg="#ffffff",
    border="#e3e7ee",
    text_primary="#26303a",
    text_secondary="#5b6470",
    text_muted="#8b94a0",
    plot_bg="#ffffff",
    plot_fg="#5b6470",
    grid_alpha=0.20,
    accent=["#1971c2", "#2f9e44", "#d9480f", "#9c36b5"],
    good="#2f9e44",
    warn="#e8590c",
    bad="#e03131",
    total_cpu="#e03131",
    total_gpu="#9c36b5",
    vram="#0c8599",
    total_ram="#e8590c",
    gpu_power="#d9480f",
    gpu_temp="#e03131",
    selection="#9c36b5",
    selection_text="#ffffff",
    fill_alpha=45,
    hover_bg="#eaeef4",
    input_bg="#ffffff",
)

_THEMES = {"dark": DARK, "light": LIGHT}

# Corner radii — one scale for the whole app, shared by QSS and custom painters.
# Tuned for a dense tool UI (Linear / Grafana territory), not a content site:
# small radii read as precise, large ones read as soft and waste edge pixels.
RADIUS_SURFACE = 6    # group boxes, chip bars, panels
RADIUS_CARD = 6       # chart cards, the stats list
RADIUS_CONTROL = 4    # buttons, inputs, combo boxes
RADIUS_CHIP = 3       # small pills, icon buttons, menu rows


# ---------------------------------------------------------------------------
# Manager (persistence + live-switch signal)
# ---------------------------------------------------------------------------

class _Signals(QObject):
    changed = pyqtSignal()


_signals: _Signals | None = None
_current: Theme | None = None


def theme_changed_signal() -> pyqtSignal:
    """Return the ``changed`` signal (creates the QObject lazily, after QApp)."""
    global _signals
    if _signals is None:
        _signals = _Signals()
    return _signals.changed


def _load_saved() -> str:
    """Read persisted theme name from the AppData config file (default dark)."""
    from src.core import app_config
    return "light" if app_config.get("theme", "dark") == "light" else "dark"


def _save(name: str) -> None:
    from src.core import app_config
    app_config.set("theme", name)


def current_theme() -> Theme:
    """The active theme (lazy-loaded from the config file on first call)."""
    global _current
    if _current is None:
        _current = _THEMES[_load_saved()]
    return _current


def set_theme(name: str) -> None:
    """Switch the active theme, persist it, and emit ``themeChanged``."""
    global _current
    name = "light" if name == "light" else "dark"
    _current = _THEMES[name]
    _save(name)
    theme_changed_signal().emit()


def toggle_theme() -> None:
    set_theme("light" if current_theme().is_dark else "dark")


def palette() -> list[str]:
    """Active per-process accent colours."""
    return current_theme().accent


def system_color(key: str) -> str:
    """Active colour for a system-series key (total_cpu/total_gpu/vram/total_ram)."""
    return getattr(current_theme(), key)


def metric_accent(key: str, t: Theme = None) -> str:
    """Resolve a card's accent colour by key.

    ``key`` is either a palette index ("0".."3") or a semantic/system name
    ("vram", "total_cpu", "total_gpu", "good", "warn", "bad").
    """
    t = t or current_theme()
    if key in ("total_cpu", "total_gpu", "vram", "total_ram",
               "gpu_power", "gpu_temp", "good", "warn", "bad"):
        return getattr(t, key)
    try:
        return t.accent[int(key)]
    except (ValueError, IndexError):
        return t.accent[0]


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _rgba(hex_color: str, alpha: int) -> str:
    """Return an rgba() string for a hex colour with the given alpha (0-255)."""
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def fill_brush(hex_color: str, alpha: int | None = None) -> pg.mkBrush:
    """A translucent brush for area fills under a curve."""
    a = alpha if alpha is not None else current_theme().fill_alpha
    c = QColor(hex_color)
    c.setAlpha(a)
    return pg.mkBrush(c)


def lerp_color(start: str | QColor, end: str | QColor, t: float) -> QColor:
    """Blend two colours; ``t`` 0 → *start*, 1 → *end*. For animated painting."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    a, b = QColor(start), QColor(end)
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def tint(hex_color: str, alpha: int) -> str:
    """An rgba() string for *hex_color* — flat accent washes in QSS."""
    return _rgba(hex_color, alpha)


# ---------------------------------------------------------------------------
# QSS generators
# ---------------------------------------------------------------------------

def app_qss(t: Theme = None) -> str:
    """Global stylesheet — applied at the QApplication level (covers menus).

    Flat by design: surfaces are filled shapes, outlines are reserved for inputs
    and separators, and every interactive state is a background/colour swap.
    """
    t = t or current_theme()
    hover = t.accent[0]
    soft = _rgba(hover, 40)
    return f"""
        QWidget {{
            background-color: {t.window_bg};
            color: {t.text_primary};
            font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
            font-size: 10pt;
        }}
        QMainWindow, QDialog {{ background-color: {t.window_bg}; }}
        QMenuBar {{
            background-color: {t.window_bg}; color: {t.text_primary};
            border-bottom: 1px solid {t.border}; padding: 3px 6px;
        }}
        QMenuBar::item {{ background: transparent; padding: 4px 10px; border-radius: {RADIUS_CHIP}px; }}
        QMenuBar::item:selected {{ background: {t.border}; color: {hover}; }}
        QMenuBar::item:pressed {{ background: {t.panel_bg}; color: {hover}; }}
        QMenu {{
            background-color: {t.panel_bg}; color: {t.text_primary};
            border: 1px solid {t.border}; border-radius: {RADIUS_CONTROL}px; padding: 5px;
        }}
        QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: {RADIUS_CHIP}px; }}
        QMenu::item:selected {{ background-color: {soft}; color: {hover}; }}
        QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}
        QStatusBar {{
            background-color: {t.window_bg}; color: {t.text_secondary};
            border-top: 1px solid {t.border}; padding: 2px 10px;
        }}
        QStatusBar::item {{ border: none; }}
        QGroupBox {{
            background-color: {t.panel_bg};
            border: none;
            border-radius: {RADIUS_SURFACE}px;
            margin-top: 15px;
            padding: 14px 10px 10px 10px;
            font-weight: 600;
            color: {t.text_primary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 4px; padding: 0 4px;
            color: {t.text_secondary};
            font-size: 9pt;
        }}
        QLabel {{ background: transparent; color: {t.text_primary}; }}
        QPushButton {{
            background-color: {t.card_bg};
            color: {t.text_primary};
            border: none;
            border-radius: {RADIUS_CONTROL}px;
            padding: 8px 16px;
        }}
        QPushButton:hover {{ background-color: {soft}; color: {hover}; }}
        QPushButton:pressed {{ background-color: {t.hover_bg}; color: {hover}; }}
        QPushButton:disabled {{ background-color: {t.panel_bg}; color: {t.text_muted}; }}
        QLineEdit, QPlainTextEdit, QTextEdit {{
            background-color: {t.input_bg};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {RADIUS_CONTROL}px;
            padding: 6px 9px;
            selection-background-color: {hover};
        }}
        QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {{ border-color: {t.text_muted}; }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {hover}; }}
        QListWidget, QTableWidget, QTreeView {{
            background-color: {t.input_bg};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {RADIUS_CONTROL}px;
            alternate-background-color: {t.panel_bg};
            selection-background-color: {t.selection};
            selection-color: {t.selection_text};
            outline: 0;
            padding: 2px;
        }}
        QListWidget::item, QTableWidget::item {{
            padding: 6px 10px; border: 0; border-radius: {RADIUS_CHIP}px;
        }}
        QListWidget::item:hover {{ background-color: {soft}; color: {hover}; }}
        QHeaderView::section {{
            background-color: {t.panel_bg};
            color: {t.text_secondary};
            border: 0;
            border-right: 1px solid {t.border};
            border-bottom: 1px solid {t.border};
            padding: 7px 10px;
            font-weight: 600;
        }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {t.text_muted}; border-radius: {RADIUS_CHIP}px; min-height: 28px; margin: 2px; }}
        QScrollBar::handle:vertical:hover {{ background: {t.text_secondary}; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
        QScrollBar::handle:horizontal {{ background: {t.text_muted}; border-radius: {RADIUS_CHIP}px; min-width: 28px; margin: 2px; }}
        QScrollBar::handle:horizontal:hover {{ background: {t.text_secondary}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        /* Flat progress: a track and a fill, no groove bevel or chunk gaps. */
        QProgressBar {{
            background: {t.input_bg}; border: none;
            border-radius: {RADIUS_CHIP}px; height: 6px;
        }}
        QProgressBar::chunk {{
            background: {t.accent[0]}; border-radius: {RADIUS_CHIP}px;
        }}
        QSplitter::handle {{ background: transparent; }}
        QSplitter::handle:horizontal {{ width: 8px; }}
        QSplitter::handle:vertical {{ height: 8px; }}
        QSplitter::handle:hover {{ background: {soft}; }}
        /* Flat tabs: an accent underline instead of a raised folder tab. */
        QTabWidget::pane {{ border: none; border-top: 1px solid {t.border}; top: -1px; }}
        QTabBar::tab {{
            background: transparent; color: {t.text_secondary};
            border: none; border-bottom: 2px solid transparent;
            padding: 8px 16px; margin-right: 2px;
        }}
        QTabBar::tab:hover {{ color: {t.text_primary}; }}
        QTabBar::tab:selected {{ color: {hover}; border-bottom-color: {hover}; }}
        QCheckBox, QRadioButton {{ color: {t.text_primary}; spacing: 6px; }}
        QComboBox {{
            background-color: {t.input_bg}; color: {t.text_primary};
            border: 1px solid {t.border}; border-radius: {RADIUS_CONTROL}px; padding: 5px 9px;
        }}
        QComboBox:focus {{ border-color: {hover}; }}
        QComboBox QAbstractItemView {{
            background-color: {t.panel_bg}; color: {t.text_primary};
            border: 1px solid {t.border}; border-radius: {RADIUS_CHIP}px;
            selection-background-color: {soft}; selection-color: {hover};
        }}
        QSpinBox {{
            background-color: {t.input_bg}; color: {t.text_primary};
            border: 1px solid {t.border}; border-radius: {RADIUS_CONTROL}px; padding: 4px 6px;
        }}
        QSpinBox:focus {{ border-color: {hover}; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            background-color: transparent; border: none; width: 18px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background-color: {soft}; }}
        QSpinBox::up-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid {t.text_secondary}; width: 0; height: 0; }}
        QSpinBox::down-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {t.text_secondary}; width: 0; height: 0; }}
        QToolTip {{
            background-color: {t.card_bg}; color: {t.text_primary};
            border: 1px solid {t.border}; border-radius: {RADIUS_CHIP}px; padding: 5px 9px;
        }}
    """


def card_qss(t: Theme = None, selector: str = "QFrame") -> str:
    """Flat card surface — filled shape, no outline, no shadow."""
    t = t or current_theme()
    return (
        f"{selector} {{ background-color: {t.card_bg}; border: none;"
        f" border-radius: {RADIUS_CARD}px; }}"
    )


def panel_button_qss(t: Theme = None, role: str = "primary") -> str:
    """Solid action-button QSS for panels/dialogs.

    role: "start" (green/good), "stop" (red/bad), "primary" (blue/accent[0]).
    Hover/press stay flat: the same fill, one step darker via an accent wash.
    """
    t = t or current_theme()
    color = {"start": t.good, "stop": t.bad, "primary": t.accent[0]}[role]
    return (
        f"QPushButton {{ background-color: {color}; color: #ffffff; font-weight: 600;"
        f" border: none; border-radius: {RADIUS_CONTROL}px; padding: 8px 14px; }}"
        f"QPushButton:hover {{ background-color: {_rgba(color, 200)}; }}"
        f"QPushButton:pressed {{ background-color: {_rgba(color, 160)}; }}"
        f"QPushButton:disabled {{ background-color: {t.panel_bg}; color: {t.text_muted}; }}"
    )


def value_badge_qss(t: Theme = None, accent: str | None = None) -> str:
    """Big live-value readout in a card header (transparent — the card shows through)."""
    t = t or current_theme()
    c = accent or t.accent[0]
    return (
        f"QLabel {{ color: {c}; background: transparent;"
        f" font-family: 'Consolas','Cascadia Mono',monospace; font-size: 13pt; font-weight: 700;"
        f" padding: 0 4px; }}"
    )


def monitored_label_qss(t: Theme = None) -> str:
    """QSS for the 'Monitored: App1, App2' label (shared by live + analysis views)."""
    t = t or current_theme()
    return f"font-weight: 600; font-size: 11pt; color: {t.text_primary}; padding: 4px 0;"


def muted_placeholder_qss(t: Theme = None, padding: str = "8px") -> str:
    """QSS for muted/italic placeholder text (e.g. 'No data yet')."""
    t = t or current_theme()
    return f"color: {t.text_muted}; font-style: italic; padding: {padding};"


def icon_button_qss(t: Theme = None) -> str:
    """AutoSize / maximize toolbar buttons — ghost buttons until hovered."""
    t = t or current_theme()
    hover = t.accent[0]
    return (
        "QPushButton { background: transparent; border: none;"
        f" border-radius: {RADIUS_CHIP}px; color: {t.text_muted};"
        " font-weight: 700; padding: 0; }"
        f"QPushButton:hover {{ background: {_rgba(hover, 40)}; color: {hover}; }}"
        f"QPushButton:pressed {{ background: {_rgba(hover, 70)}; }}"
    )


def stats_list_qss(t: Theme = None) -> str:
    """The statistics readout: one surface, rows split by hairlines.

    Ten separate rounded tiles stacked vertically turn the panel into a column of
    blobs. A single container with hairline-separated rows reads as one table and
    leaves exactly one rounded shape on screen.
    """
    t = t or current_theme()
    return (
        f"QFrame#StatsList {{ background-color: {t.card_bg}; border: none;"
        f" border-radius: {RADIUS_CARD}px; }}"
        "QFrame#StatsRow, QFrame#StatsRowLast"
        " { background: transparent; border: none; }"
        f"QFrame#StatsRow {{ border-bottom: 1px solid {t.border}; }}"
    )


def system_bar_qss(t: Theme = None) -> str:
    """Slim system-info chip bar."""
    t = t or current_theme()
    return (
        f"QFrame#SystemBar {{ background-color: {t.panel_bg}; border: none;"
        f" border-radius: {RADIUS_SURFACE}px; }}"
        f" QLabel#SysChip {{ background: transparent; color: {t.text_secondary};"
        " padding: 4px 2px; }"
    )


# ---------------------------------------------------------------------------
# Plot styling
# ---------------------------------------------------------------------------

_AXIS_FONT = QFont("Segoe UI", 8)
_AXIS_FONT_COMPACT = QFont("Segoe UI", 7)


def _cosmetic_pen(color: str | QColor, width: int = 1, style=Qt.SolidLine):
    """Return a 1-device-pixel pen for stable axes on mixed-DPI screens."""
    pen = pg.mkPen(color, width=width, style=style)
    try:
        pen.setCosmetic(True)
    except Exception:
        pass
    return pen


def apply_to_plot(plot: pg.PlotWidget, t: Theme = None) -> None:
    """Apply bg / axis / grid styling. Re-callable for live theme switches."""
    t = t or current_theme()
    plot.setBackground(t.plot_bg)
    vb = plot.getViewBox()
    vb.setBackgroundColor(t.plot_bg)
    pen = _cosmetic_pen(t.plot_fg)
    for axis in ("left", "right", "bottom", "top"):
        ax = plot.getAxis(axis)
        ax.setPen(pen)
        ax.setTextPen(t.plot_fg)
        try:
            ax.setStyle(tickFont=_AXIS_FONT)
        except Exception:
            pass
    plot.showGrid(x=True, y=True, alpha=t.grid_alpha)
    plot.setMenuEnabled(False)


def apply_axis_layout(plot: pg.PlotWidget, *, compact: bool = False,
                      narrow: bool = False, top_chart: bool = False) -> None:
    """Adjust axis text/tick density for the plot's current viewport size."""
    font = _AXIS_FONT_COMPACT if compact else _AXIS_FONT
    tick_length = -3 if compact else -5
    text_height = 14 if compact else 18
    text_width = 24 if narrow else 30
    tick_offset = 2 if compact else 4
    density = 0.45 if compact or narrow else 0.7
    max_tick_level = 1 if compact or narrow else 2

    left_width = 38 if compact else 44
    if top_chart:
        left_width += 4

    left = plot.getAxis("left")
    bottom = plot.getAxis("bottom")
    for ax in (left, bottom):
        try:
            ax.setTickDensity(density)
        except Exception:
            pass
        try:
            ax.setStyle(
                tickFont=font,
                tickLength=tick_length,
                tickTextOffset=tick_offset,
                tickTextWidth=text_width,
                tickTextHeight=text_height,
                hideOverlappingLabels=True,
                maxTickLevel=max_tick_level,
                maxTextLevel=1,
            )
        except Exception:
            pass

    try:
        left.setWidth(left_width)
    except Exception:
        pass
    try:
        bottom.setHeight(26 if compact else 32)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Crosshair (hover readout)
# ---------------------------------------------------------------------------

class Crosshair:
    """Vertical + horizontal crosshair lines plus a value tooltip on hover.

    Scans the plot's data items at hover time, so it auto-adapts to curves
    being added/removed/recreated (e.g. on theme switch). Each data item's
    ``name()`` is used as the label.
    """

    def __init__(self, plot: pg.PlotWidget, t: Theme = None):
        self._plot = plot
        self._vb = plot.getViewBox()
        self._t = t or current_theme()

        line_pen = _cosmetic_pen(QColor(t.plot_fg), width=1, style=Qt.DashLine)
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=line_pen)
        self._hline = pg.InfiniteLine(angle=0, movable=False, pen=line_pen)
        self._label = pg.TextItem(
            text="", color=t.text_primary, fill=pg.mkBrush(QColor(t.card_bg)),
        )
        self._label.setZValue(20)
        for it in (self._vline, self._hline, self._label):
            plot.addItem(it)
            it.hide()

        try:
            plot.scene().sigMouseMoved.connect(self._on_moved)
        except Exception:
            pass  # scene not available; crosshair simply stays disabled

    def _on_moved(self, pos):
        vb = self._vb
        if not vb.sceneBoundingRect().contains(pos):
            self._hide()
            return
        pt = vb.mapSceneToView(pos)
        x = pt.x()
        y = pt.y()
        self._vline.setPos(x)
        self._hline.setPos(y)
        self._vline.show()
        self._hline.show()

        # Build an HTML tooltip: muted time header + one colored line per series.
        t = self._t
        html_parts = [f'<div style="color:{t.text_muted};font-size:8pt;">t = {x:.1f} s</div>']
        plain = [f"t = {x:.1f} s"]
        for item in self._plot.listDataItems():
            try:
                xs, ys = item.getData()
            except Exception:
                continue
            if xs is None or len(xs) == 0:
                continue
            name = getattr(item, "name", None)
            name = name() if callable(name) else name
            if not name:
                continue
            # nearest index by absolute x-distance
            idx = int(np.argmin(np.abs(np.asarray(xs, dtype=float) - x)))
            val = ys[idx]
            try:
                val_str = f"{val:.1f}"
            except (TypeError, ValueError):
                val_str = str(val)
            plain.append(f"{name}: {val_str}")
            # series color from its pen (auto-adapts to theme); fallback muted
            try:
                color = item.pen().color().name()
            except Exception:
                color = t.text_secondary
            html_parts.append(
                f'<div><span style="color:{color};">●</span> '
                f'<span style="color:{t.text_primary};">{name}: {val_str}</span></div>')
        try:
            self._label.textItem.setHtml("".join(html_parts))
        except Exception:
            self._label.setText("\n".join(plain))

        # Position the label near the cursor, anchored to keep it on-screen.
        view_range = vb.viewRange()  # [[xmin, xmax], [ymin, ymax]]
        x0, x1 = view_range[0]
        y0, y1 = view_range[1]
        width_frac = x1 - x0
        anchor_x = 0.0 if (x - x0) < width_frac / 2 else 1.0
        anchor_y = 1.0  # show above cursor
        self._label.setAnchor((anchor_x, anchor_y))
        self._label.setPos(x, y)
        self._label.show()

    def _hide(self):
        self._vline.hide()
        self._hline.hide()
        self._label.hide()

    def restyle(self, t: Theme = None) -> None:
        """Recolour after a theme switch."""
        t = t or current_theme()
        self._t = t
        line_pen = _cosmetic_pen(QColor(t.plot_fg), width=1, style=Qt.DashLine)
        self._vline.setPen(line_pen)
        self._hline.setPen(line_pen)
        self._label.setColor(t.text_primary)
        self._label.fill = pg.mkBrush(QColor(t.card_bg))


def apply_app_qss(t: Theme = None) -> None:
    """Apply the global stylesheet to the running QApplication (if any)."""
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(app_qss(t))
