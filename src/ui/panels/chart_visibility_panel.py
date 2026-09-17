"""Inline show/hide part for the live performance charts.

A collapsible row of checkboxes listing every chart in ``CHART_REGISTRY``.
Toggling an item calls back into ``MonitorView.set_chart_visible`` (the single
entry point). When the visibility change originates elsewhere (View menu or a
card's right-click Hide), ``MonitorView.visibility_changed`` back-syncs the
relevant checkbox here via :meth:`set_checked` (signals blocked, so no feedback
loop).
"""

from PyQt5.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QToolButton, QWidget,
)

from src.i18n import tr
from src.ui.theme import apply_shadow, current_theme


class _FlowLayout(QLayout):
    """Simple wrapping layout for compact checkbox chips."""

    def __init__(self, parent=None, margin: int = 0, hspacing: int = 6,
                 vspacing: int = 4):
        super().__init__(parent)
        self._items = []
        self._hspacing = hspacing
        self._vspacing = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Horizontal)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect, test_only: bool):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._hspacing
            if next_x - self._hspacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._vspacing
                next_x = x + hint.width() + self._hspacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + bottom


class ChartVisibilityPanel(QWidget):
    """A collapsible row of checkboxes that drives chart visibility."""

    expanded_changed = pyqtSignal(bool)

    def __init__(self, registry, on_toggle, parent=None):
        super().__init__(parent)
        self._on_toggle = on_toggle
        self._registry = registry
        self._checks: dict[str, QPushButton] = {}
        self._expanded = False
        self.setObjectName("ChartVisPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        t = current_theme()
        self.setStyleSheet(self._qss(t))
        apply_shadow(self, t)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        self._toggle = QToolButton()
        self._toggle.setObjectName("ChartVisToggle")
        self._toggle.setAutoRaise(True)
        self._toggle.setToolTip(tr("charts_panel"))
        self._toggle.clicked.connect(self.toggle_expanded)
        lay.addWidget(self._toggle, 0, Qt.AlignTop)

        self._title = QLabel(tr("charts_panel"))
        self._title.setObjectName("ChartVisTitle")
        self._title.setStyleSheet(
            f"color: {t.text_primary}; font-weight: 600; font-size: 9pt;")
        lay.addWidget(self._title, 0, Qt.AlignTop)

        self._chips = QWidget()
        self._chips.setObjectName("ChartVisChips")
        flow = _FlowLayout(self._chips, hspacing=6, vspacing=4)
        for spec in registry:
            check = QPushButton(tr(spec.label_key))
            check.setObjectName("ChartVisChip")
            check.setCheckable(True)
            check.setChecked(True)
            check.toggled.connect(
                lambda checked, name=spec.name: self._on_check_toggled(name, checked))
            self._checks[spec.name] = check
            flow.addWidget(check)
        lay.addWidget(self._chips, 1)
        self.set_expanded(True)

    # ---- interaction ----

    def _on_check_toggled(self, name: str, checked: bool):
        if self._on_toggle is None:
            return
        self._on_toggle(name, checked)

    def toggle_expanded(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool):
        expanded = bool(expanded)
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._chips.setVisible(self._expanded)
        self._toggle.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)
        self.expanded_changed.emit(self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    # ---- external sync (signals blocked → no feedback loop) ----

    def sync_all(self, state: dict[str, bool]):
        """Set every checkbox from a {name: bool} map without re-emitting."""
        for name, check in self._checks.items():
            check.blockSignals(True)
            check.setChecked(state.get(name, True))
            check.blockSignals(False)

    def set_checked(self, name: str, checked: bool):
        """Update one checkbox without re-emitting (used for back-sync)."""
        check = self._checks.get(name)
        if check is None:
            return
        check.blockSignals(True)
        check.setChecked(checked)
        check.blockSignals(False)

    # ---- theming ----

    def apply_theme(self, t=None):
        t = t or current_theme()
        self.setStyleSheet(self._qss(t))
        apply_shadow(self, t)
        self._title.setStyleSheet(
            f"color: {t.text_primary}; font-weight: 600; font-size: 9pt;")

    def _qss(self, t) -> str:
        return (
            f"QWidget#ChartVisPanel {{ background-color: {t.panel_bg};"
            f" border: 1px solid {t.border}; border-radius: 10px; }}"
            "QToolButton#ChartVisToggle { background: transparent; border: none;"
            f" color: {t.text_secondary}; padding: 1px; }}"
            "QPushButton#ChartVisChip {"
            f" background-color: {t.card_bg}; color: {t.text_primary};"
            f" border: 1px solid {t.border}; border-radius: 6px;"
            " min-height: 22px; padding: 1px 8px;"
            " font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;"
            " font-size: 9pt; text-align: center;"
            "}"
            f"QPushButton#ChartVisChip:hover {{ border-color: {t.accent[0]}; }}"
            f"QPushButton#ChartVisChip:checked {{ border-color: {t.accent[0]};"
            f" color: {t.text_primary}; background-color: {t.panel_bg}; }}"
            f"QPushButton#ChartVisChip:!checked {{ color: {t.text_muted};"
            f" background-color: {t.window_bg}; }}"
        )
