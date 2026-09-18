"""Process selection panel — two-panel design with arrow buttons.

Each running ``.exe`` is one row per PID (Task Manager Details), labelled with
the main-window title so two Unity Editors are distinct. Capture uses
``--process_id`` for those rows. Click a row to flash its window; right-click
Switch to, like Task Manager.
"""

from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (
    QGroupBox, QHBoxLayout, QVBoxLayout, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QLabel, QSpinBox, QMenu,
)

from src.i18n import tr
from src.core.process_list import (
    ProcessInstance,
    flash_process_window,
    instance_from_persist,
    list_process_instances,
    switch_to_process_window,
)
from src.core import app_config
from src.ui import theme


_ROLE_INST = Qt.UserRole
_ROLE_SEARCH = Qt.UserRole + 1


def _process_item(inst: ProcessInstance) -> QListWidgetItem:
    """List entry: elided label, full identity in tooltip + UserRole."""
    item = QListWidgetItem(inst.list_label())
    item.setToolTip(inst.tooltip())
    item.setData(_ROLE_INST, {
        "pid": inst.pid,
        "name": inst.name,
        "title": inst.title,
        "exe_path": inst.exe_path,
        "name_wide": inst.name_wide,
    })
    item.setData(_ROLE_SEARCH, inst.search_blob())
    return item


def _item_instance(item: QListWidgetItem | None) -> ProcessInstance | None:
    if item is None:
        return None
    data = item.data(_ROLE_INST)
    if isinstance(data, ProcessInstance):
        return data
    if isinstance(data, dict) and data.get("name"):
        return ProcessInstance(
            pid=int(data.get("pid") or 0),
            name=str(data.get("name") or ""),
            title=str(data.get("title") or ""),
            exe_path=str(data.get("exe_path") or ""),
            name_wide=bool(data.get("name_wide")),
        )
    return None


class ProcessPanel(QGroupBox):
    """Two-panel process selector: Available ↔ Monitored, with Start/Stop controls."""

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(tr("process_selection"), parent)
        self._targets: list[ProcessInstance] = []
        # Capture state mirrored from state_changed; drives the toggle button.
        self._running = False
        self._refreshing = False
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

        self._available_list = self._make_list("AvailableList", self._add_selected)
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

        self._monitored_list = self._make_list("MonitoredList", self._remove_selected)
        monitored_layout.addWidget(self._monitored_list)
        panels_row.addLayout(monitored_layout)

        layout.addLayout(panels_row, 1)

        hint = QLabel(tr("process_instance_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("ProcessInstanceHint")
        self._hint_label = hint
        layout.addWidget(hint)

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

        self._restore_targets()
        self._refresh_available()

        # Theme: apply once + follow changes (panel used to be fully unstyled/hardcoded)
        self._apply_panel_styles()
        theme.theme_changed_signal().connect(self._on_theme_changed)

    def _make_list(self, object_name: str, on_double_click) -> QListWidget:
        """A process list that elides long names instead of scrolling sideways."""
        widget = QListWidget()
        widget.setObjectName(object_name)
        widget.setSelectionMode(QListWidget.ExtendedSelection)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        widget.setTextElideMode(Qt.ElideMiddle)
        widget.setUniformItemSizes(True)
        widget.setMinimumHeight(150)
        widget.itemDoubleClicked.connect(on_double_click)
        widget.itemClicked.connect(self._on_item_clicked)
        widget.setContextMenuPolicy(Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda pos, w=widget: self._on_list_menu(w, pos))
        return widget

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def _apply_panel_styles(self):
        """Re-colour labels/buttons/list-selection from the current theme."""
        t = theme.current_theme()
        label_qss = (
            f"font-weight: 600; font-size: 9pt; color: {t.text_muted};"
            " padding: 2px 0;"
        )
        self._avail_label.setStyleSheet(label_qss)
        self._mon_label.setStyleSheet(label_qss)
        self._hint_label.setStyleSheet(
            f"color: {t.text_muted}; font-size: 8pt; padding: 0 0 2px 0;")
        self._add_btn.setStyleSheet(self._arrow_qss(t, t.good))
        self._remove_btn.setStyleSheet(self._arrow_qss(t, t.bad))
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

    @staticmethod
    def _arrow_qss(t, color: str) -> str:
        """Flat transfer button: an accent wash that fills in on hover."""
        return (
            f"QPushButton {{ font-size: 15px; background-color: {theme.tint(color, 38)};"
            f" color: {color}; border: none; border-radius: {theme.RADIUS_CONTROL}px; }}"
            f"QPushButton:hover {{ background-color: {color}; color: #ffffff; }}"
            f"QPushButton:pressed {{ background-color: {theme.tint(color, 170)}; }}"
            f"QPushButton:disabled {{ background-color: {t.panel_bg}; color: {t.text_muted}; }}"
        )

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
    # Search / locate
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str):
        """Debounce: only re-filter after typing pauses (avoids per-keystroke freeze)."""
        self._search_timer.start()

    def _apply_search(self):
        """Filter available list by name / title / PID, in one batched update."""
        t = self._search_input.text().lower()
        lw = self._available_list
        lw.setUpdatesEnabled(False)
        try:
            for i in range(lw.count()):
                item = lw.item(i)
                blob = item.data(_ROLE_SEARCH) or item.text()
                item.setHidden(t not in str(blob).lower())
        finally:
            lw.setUpdatesEnabled(True)

    def _on_item_clicked(self, item: QListWidgetItem):
        """Flash the instance's window so the row maps to a real HWND."""
        if self._refreshing:
            return
        inst = _item_instance(item)
        if inst is not None and inst.pid:
            flash_process_window(inst.pid)

    def _on_list_menu(self, widget: QListWidget, pos):
        item = widget.itemAt(pos)
        inst = _item_instance(item)
        if inst is None or not inst.pid:
            return
        menu = QMenu(widget)
        switch_act = menu.addAction(tr("menu_switch_to"))
        chosen = menu.exec_(widget.mapToGlobal(pos))
        if chosen is switch_act:
            switch_to_process_window(inst.pid)

    # ------------------------------------------------------------------
    # Available list
    # ------------------------------------------------------------------

    def _refresh_available(self):
        """Repopulate available process list from running instances."""
        self._refreshing = True
        try:
            running = list_process_instances()
            self._rebind_targets(running)
            self._available_list.clear()
            for inst in running:
                if self._is_monitored(inst):
                    continue
                self._available_list.addItem(_process_item(inst))
            self._rebuild_monitored_list()
            self._apply_search()
        finally:
            self._refreshing = False

    def _rebind_targets(self, running: list[ProcessInstance]) -> None:
        """Refresh titles/PIDs of persisted rows from the live process table."""
        rebound: list[ProcessInstance] = []
        for target in self._targets:
            if target.name_wide or not target.pid:
                live = instance_from_persist(
                    target.to_persist(), running=running)
                rebound.append(live or target)
                continue
            live = instance_from_persist(target.to_persist(), running=running)
            rebound.append(live or target)
        self._targets = rebound

    def _rebuild_monitored_list(self):
        self._monitored_list.clear()
        for target in self._targets:
            self._monitored_list.addItem(_process_item(target))

    def _is_monitored(self, inst: ProcessInstance) -> bool:
        for target in self._targets:
            if target.pid and inst.pid and target.pid == inst.pid:
                return True
            if (target.name_wide or not target.pid) and (
                    target.name.lower() == inst.name.lower()):
                return True
        return False

    def _target_identity(self, inst: ProcessInstance) -> tuple:
        if inst.pid and not inst.name_wide:
            return ("pid", inst.pid)
        return ("name", inst.name.lower())

    # ------------------------------------------------------------------
    # Add / Remove
    # ------------------------------------------------------------------

    def _add_selected(self):
        """Move selected items from Available → Monitored."""
        seen = {self._target_identity(t) for t in self._targets}
        for item in self._available_list.selectedItems():
            inst = _item_instance(item)
            if inst is None:
                continue
            ident = self._target_identity(inst)
            if ident not in seen:
                self._targets.append(inst)
                seen.add(ident)
                self._monitored_list.addItem(_process_item(inst))
            self._available_list.takeItem(self._available_list.row(item))
        self._persist_processes()

    def _remove_selected(self):
        """Move selected items from Monitored → Available."""
        search = self._search_input.text().lower()
        remaining: list[ProcessInstance] = []
        selected_rows = {self._monitored_list.row(i) for i in self._monitored_list.selectedItems()}
        for row in range(self._monitored_list.count()):
            item = self._monitored_list.item(row)
            inst = _item_instance(item)
            if inst is None:
                continue
            if row in selected_rows:
                blob = (item.data(_ROLE_SEARCH) or item.text() or "").lower()
                if not search or search in blob:
                    self._available_list.addItem(_process_item(inst))
            else:
                remaining.append(inst)
        self._targets = remaining
        self._rebuild_monitored_list()
        self._persist_processes()

    # ------------------------------------------------------------------
    # Persist / restore
    # ------------------------------------------------------------------

    def _restore_targets(self):
        running = list_process_instances()
        raw = app_config.get("monitored_targets")
        rows: list = []
        if isinstance(raw, list) and raw:
            rows = raw
        else:
            rows = list(app_config.get("monitored_processes") or [])
        seen: set[tuple] = set()
        for row in rows:
            inst = instance_from_persist(row, running=running)
            if inst is None:
                continue
            ident = self._target_identity(inst)
            if ident in seen:
                continue
            seen.add(ident)
            self._targets.append(inst)

    def _persist_processes(self):
        """Save the monitored set so it survives restarts."""
        app_config.set(
            "monitored_targets",
            [t.to_persist() for t in self._targets],
        )
        # Keep the old key as exe names so a downgrade still has a list.
        names = sorted({t.name for t in self._targets})
        app_config.set("monitored_processes", names)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_targets(self) -> list[ProcessInstance]:
        return list(self._targets)

    def get_process_names(self) -> list[str]:
        """Name-wide targets only (legacy / unresolved). PID rows use ids."""
        return [t.name for t in self._targets if t.name_wide or not t.pid]

    def get_process_ids(self) -> list[int]:
        return [t.pid for t in self._targets if t.pid and not t.name_wide]

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
        return len(self._targets) > 0

    def live_capture_targets(self) -> tuple[list[ProcessInstance], list[str]]:
        """Resolve PIDs now: (instance targets, leftover name-wide exe names)."""
        running = list_process_instances()
        self._rebind_targets(running)
        self._rebuild_monitored_list()
        live_pids = {p.pid for p in running}
        instances = [
            t for t in self._targets
            if t.pid and not t.name_wide and t.pid in live_pids
        ]
        names = [t.name for t in self._targets if t.name_wide or not t.pid]
        return instances, names
