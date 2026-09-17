"""Shortcuts dialog — read-only list of keyboard shortcuts, theme-aware."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QPushButton, QHBoxLayout,
)

from src.i18n import tr
from src.ui import theme


# (description i18n key, shortcut display string) — order is display order.
# Kept in sync with the shortcuts assigned in main_window._init_ui().
_SHORTCUTS: list[tuple[str, str]] = [
    ("sc_capture", "F5"),
    ("sc_overlay", "F9"),
    ("sc_theme", "Ctrl+D"),
    ("sc_export", "Ctrl+E"),
    ("sc_import", "Ctrl+I"),
    ("sc_charts_panel", "Ctrl+J"),
    ("sc_always_top", "Ctrl+T"),
    ("sc_shortcuts", "F1"),
    # Click-through is a menu toggle (no hotkey) — show the menu name.
    ("sc_click_through", tr("menu_click_through")),
]


class ShortcutsDialog(QDialog):
    """Lists all keyboard shortcuts; follows the active light/dark theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("shortcuts_title"))
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(14, 14, 14, 10)
        mono = QFont("Consolas", 10)
        self._key_labels: list[QLabel] = []
        for desc_key, key_display in _SHORTCUTS:
            desc = QLabel(tr(desc_key))
            key = QLabel(key_display)
            key.setFont(mono)
            key.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._key_labels.append(key)
            form.addRow(desc, key)
        root.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(tr("btn_close"), self)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._apply_theme()
        theme.theme_changed_signal().connect(self._apply_theme)

    # ----------------------------------------------------------------
    # Theming
    # ----------------------------------------------------------------

    def _apply_theme(self):
        t = theme.current_theme()
        self.setStyleSheet(
            f"QDialog {{ background-color: {t.panel_bg}; }}"
            f"QLabel {{ color: {t.text_primary}; }}"
        )
        for lbl in self._key_labels:
            lbl.setStyleSheet(f"color: {t.accent[0]};")
