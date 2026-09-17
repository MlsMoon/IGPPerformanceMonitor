"""Process selection panel — two-panel design with arrow buttons."""

from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (
    QGroupBox, QHBoxLayout, QVBoxLayout, QPushButton,
    QLineEdit, QListWidget, QLabel, QSpinBox, QWidget, QSizePolicy,
)
from PyQt5.QtGui import QFont

from src.i18n import tr
from src.core.system_metrics import get_running_process_names
from src.core import app_config
from src.ui import theme


class ProcessPanel(QGroupBox):
    """Two-panel process selector: Available ↔ Monitored, with Start/Stop controls."""

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(tr("process_selection"), parent)
        self._process_names: set[str] = set()
        # Capture state mirrored from state_changed; drives the toggle button.
        self._running = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # === Search filter ===
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(tr("placeholder_search"))
        self._search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_input)

        # Debounce search: typing fast used to fire a full list re-hide per keystroke
        # (every setHidden relayouts the QListWidget on Windows), freezing the UI.
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_search)

        # === Two-panel area ===
        panels_row = QHBoxLayout()
        panels_row.setSpacing(4)

        # Left: Available
        avail_layout = QVBoxLayout()
        avail_label = QLabel(tr("available_processes"))
        self._avail_label = avail_label
        avail_layout.addWidget(avail_label)

        self._available_list = QListWidget()
        self._available_list.setObjectName("AvailableList")
        self._available_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._available_list.itemDoubleClicked.connect(self._add_selected)
        avail_layout.addWidget(self._available_list)
        panels_row.addLayout(avail_layout)

        # Middle: Arrow buttons
        arrow_layout = QVBoxLayout()
        arrow_layout.addStretch()

        self._add_btn = QPushButton("▶")
        self._add_btn.setFixedSize(36, 36)
        self._add_btn.setToolTip(tr("tooltip_add"))
        self._add_btn.clicked.connect(self._add_selected)
        arrow_layout.addWidget(self._add_btn)

        arrow_layout.addSpacing(6)

        self._remove_btn = QPushButton("◀")
        self._remove_btn.setFixedSize(36, 36)
        self._remove_btn.setToolTip(tr("tooltip_remove"))
        self._remove_btn.clicked.connect(self._remove_selected)
        arrow_layout.addWidget(self._remove_btn)

        arrow_layout.addStretch()
        panels_row.addLayout(arrow_layout)

        # Right: Monitored
        monitored_layout = QVBoxLayout()
        mon_label = QLabel(tr("monitored_processes"))
        self._mon_label = mon_label
        monitored_layout.addWidget(mon_label)

        self._monitored_list = QListWidget()
        self._monitored_list.setObjectName("MonitoredList")
        self._monitored_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._monitored_list.itemDoubleClicked.connect(self._remove_selected)
        monitored_layout.addWidget(self._monitored_list)
        panels_row.addLayout(monitored_layout)

        layout.addLayout(panels_row, 1)

        # === Refresh button ===
        refresh_btn = QPushButton(tr("btn_refresh"))
        refresh_btn.clicked.connect(self._refresh_available)
        layout.addWidget(refresh_btn)

        # === Control row: single Start/Stop toggle button ===
        ctrl_row = QHBoxLayout()

        self._capture_btn = QPushButton(tr("btn_start"))
        self._capture_btn.clicked.connect(self._on_capture_clicked)
        ctrl_row.addWidget(self._capture_btn)

        layout.addLayout(ctrl_row)

        # === Timer ===
        timer_row = QHBoxLayout()
        timer_row.addWidget(QLabel(tr("label_auto_stop")))
        self._timer_spin = QSpinBox()
        self._timer_spin.setRange(0, 86400)
        self._timer_spin.setValue(app_config.get("timed_seconds", 0))
        self._timer_spin.setSuffix(" s")
        self._timer_spin.valueChanged.connect(
            lambda v: app_config.set("timed_seconds", v))
        timer_row.addWidget(self._timer_spin)
        timer_row.addStretch()
        layout.addLayout(timer_row)

        # Restore last session's monitored processes (before refreshing the
        # available list so they're excluded). Stale names are harmless — the
        # user can remove them; they only matter once the app actually runs.
        for name in app_config.get("monitored_processes") or []:
            if name not in self._process_names:
                self._process_names.add(name)
                self._monitored_list.addItem(name)

        # Initial population
        self._refresh_available()

        # Theme: apply once + follow changes (panel used to be fully unstyled/hardcoded)
        self._apply_panel_styles()
        theme.theme_changed_signal().connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def _apply_panel_styles(self):
        """Re-colour labels/buttons/list-selection from the current theme."""
        t = theme.current_theme()
        label_qss = f"font-weight: bold; color: {t.text_secondary};"
        self._avail_label.setStyleSheet(label_qss)
        self._mon_label.setStyleSheet(label_qss)
        # Square arrow buttons: green/red, fixed size override of padding
        self._add_btn.setStyleSheet(
            f"QPushButton {{ font-size: 16px; background-color: {t.good}; color: #ffffff;"
            f" border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {t.panel_bg}; color: {t.good};"
            f" border: 1px solid {t.good}; }}"
            f"QPushButton:disabled {{ background-color: {t.text_muted}; }}"
        )
        self._remove_btn.setStyleSheet(
            f"QPushButton {{ font-size: 16px; background-color: {t.bad}; color: #ffffff;"
            f" border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {t.panel_bg}; color: {t.bad};"
            f" border: 1px solid {t.bad}; }}"
            f"QPushButton:disabled {{ background-color: {t.text_muted}; }}"
        )
        self._apply_capture_btn()
        # Inline item-selection on each list: `::item:selected` paints the
        # item background regardless of keyboard focus (unlike the global
        # `selection-background-color`, which Qt ignores when focus leaves).
        list_sel = (
            f"QListWidget::item:selected {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
            f"QListWidget::item:selected:!active {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
        )
        self._available_list.setStyleSheet(list_sel)
        self._monitored_list.setStyleSheet(list_sel)

    def _on_theme_changed(self):
        self._apply_panel_styles()

    def _apply_capture_btn(self):
        """Re-style the Start/Stop toggle button for the current capture state.

        Shows the action that clicking will perform: "Start" (green) when idle,
        "Stop" (red) while capturing. Reuses panel_button_qss roles + i18n keys
        so no new styles/strings are added.
        """
        if self._running:
            role, key = "stop", "btn_stop"
        else:
            role, key = "start", "btn_start"
        self._capture_btn.setText(tr(key))
        self._capture_btn.setStyleSheet(theme.panel_button_qss(theme.current_theme(), role))

    def _on_capture_clicked(self):
        """Route the single toggle button to start or stop based on state."""
        if self._running:
            self.stop_requested.emit()
        else:
            self.start_requested.emit()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str):
        """Debounce: only re-filter after typing pauses (avoids per-keystroke freeze)."""
        self._search_timer.start()

    def _apply_search(self):
        """Filter available list by current search text, in one batched update."""
        t = self._search_input.text().lower()
        lw = self._available_list
        lw.setUpdatesEnabled(False)
        try:
            for i in range(lw.count()):
                item = lw.item(i)
                item.setHidden(t not in item.text().lower())
        finally:
            lw.setUpdatesEnabled(True)

    # ------------------------------------------------------------------
    # Available list
    # ------------------------------------------------------------------

    def _refresh_available(self):
        """Repopulate available process list from running processes."""
        current_search = self._search_input.text()
        monitored = self._process_names
        processes = get_running_process_names()
        self._available_list.clear()
        for name in processes:
            if name not in monitored:
                self._available_list.addItem(name)
        # Re-apply search filter immediately (no debounce after a refresh)
        self._apply_search()

    # ------------------------------------------------------------------
    # Add / Remove
    # ------------------------------------------------------------------

    def _add_selected(self):
        """Move selected items from Available → Monitored."""
        for item in self._available_list.selectedItems():
            name = item.text()
            if name not in self._process_names:
                self._process_names.add(name)
                self._monitored_list.addItem(name)
            self._available_list.takeItem(self._available_list.row(item))
        self._persist_processes()

    def _remove_selected(self):
        """Move selected items from Monitored → Available."""
        search = self._search_input.text().lower()
        for item in self._monitored_list.selectedItems():
            name = item.text()
            self._process_names.discard(name)
            self._monitored_list.takeItem(self._monitored_list.row(item))
            # Put back in available if matches search (or if no filter)
            if not search or search in name.lower():
                self._available_list.addItem(name)
        self._persist_processes()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_process_names(self) -> list[str]:
        return list(self._process_names)

    def _persist_processes(self):
        """Save the monitored set so it survives restarts."""
        app_config.set("monitored_processes", sorted(self._process_names))

    def get_timed_seconds(self) -> int:
        return self._timer_spin.value()

    def set_capture_state(self, running: bool):
        self._running = running
        self._apply_capture_btn()
        # The toggle button stays enabled in both states; the surrounding
        # process-selection controls lock down while capturing.
        self._search_input.setEnabled(not running)
        self._add_btn.setEnabled(not running)
        self._remove_btn.setEnabled(not running)
        self._timer_spin.setEnabled(not running)

    def has_processes(self) -> bool:
        return len(self._process_names) > 0
