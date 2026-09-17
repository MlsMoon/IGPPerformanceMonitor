"""Inline show/hide part for the live performance charts.

A collapsible row of checkboxes listing every chart in ``CHART_REGISTRY``.
Toggling an item calls back into ``MonitorView.set_chart_visible`` (the single
entry point). When the visibility change originates elsewhere (View menu or a
card's right-click Hide), ``MonitorView.visibility_changed`` back-syncs the
relevant checkbox here via :meth:`set_checked` (signals blocked, so no feedback
loop).
"""

from PyQt5.QtWidgets import QPushButton, QWidget

from src.i18n import tr
from src.ui.flow_layout import FlowLayout
from src.ui.panels.collapsible_section import CollapsibleSection
from src.ui.theme import RADIUS_CHIP, tint


class ChartVisibilityPanel(CollapsibleSection):
    """Chart show/hide chips in :class:`CollapsibleSection`."""

    def __init__(self, registry, on_toggle, parent=None):
        super().__init__("charts_panel", parent, name="ChartVis", stacked=False)
        self._on_toggle = on_toggle
        self._registry = registry
        self._checks: dict[str, QPushButton] = {}

        self._chips = QWidget()
        self._chips.setObjectName("ChartVisChips")
        flow = FlowLayout(self._chips, hspacing=6, vspacing=4)
        for spec in registry:
            check = QPushButton(tr(spec.label_key))
            check.setObjectName("ChartVisChip")
            check.setCheckable(True)
            check.setChecked(True)
            check.toggled.connect(
                lambda checked, name=spec.name: self._on_check_toggled(name, checked))
            self._checks[spec.name] = check
            flow.addWidget(check)
        self.set_body(self._chips)
        self.apply_theme()

    def _on_check_toggled(self, name: str, checked: bool):
        if self._on_toggle is None:
            return
        self._on_toggle(name, checked)

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

    def _extra_qss(self, t) -> str:
        """Flat pills: an accent wash marks 'shown', a flat fill marks 'hidden'."""
        accent = t.accent[0]
        return (
            "QPushButton#ChartVisChip {"
            f" background-color: {t.card_bg}; color: {t.text_muted};"
            f" border: none; border-radius: {RADIUS_CHIP}px;"
            " min-height: 24px; padding: 2px 10px;"
            " font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;"
            " font-size: 9pt; text-align: center;"
            "}"
            f"QPushButton#ChartVisChip:hover {{ background-color: {tint(accent, 30)};"
            f" color: {t.text_primary}; }}"
            f"QPushButton#ChartVisChip:checked {{ background-color: {tint(accent, 45)};"
            f" color: {accent}; font-weight: 600; }}"
            f"QPushButton#ChartVisChip:checked:hover {{ background-color: {tint(accent, 70)}; }}"
        )
