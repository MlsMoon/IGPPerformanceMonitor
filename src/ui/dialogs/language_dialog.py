"""First-run language picker.

Copy is joined from every locale catalog (``bilingual``), not ``tr()``: no
locale has been chosen yet, so a single-language ``tr()`` would look like the
app had already decided.
"""

import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAbstractButton, QButtonGroup, QDialog, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QVBoxLayout,
)

from src.i18n import (
    LOCALE_NATIVE_NAMES, UI_LOCALES, bilingual, get_locale,
)
from src.ui import theme, win_chrome


class LanguageDialog(QDialog):
    """Modal: one radio per UI locale. ``selected`` is set only on OK."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(bilingual("language_picker_title"))
        self.setModal(True)
        self.setMinimumWidth(320)
        # Closing this dialog is not "the user quit". Default WA_QuitOnClose
        # plus quitOnLastWindowClosed would QApplication.quit() here, and
        # MainWindow.show() after exec_() would never appear.
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.selected: str | None = None
        # Do not use QWidget.setProperty("locale", ...): "locale" is a real
        # QWidget property of type QLocale, so the string comes back as a
        # QLocale and `loc in UI_LOCALES` fails. First-run OK then sys.exit(0)
        # in ensure_ui_locale — the window never opens (0.1.6).
        self._locale_by_button: dict[QAbstractButton, str] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        hint = QLabel(bilingual("language_picker_hint"))
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._group = QButtonGroup(self)
        current = get_locale() if get_locale() in UI_LOCALES else (
            UI_LOCALES[0] if UI_LOCALES else ""
        )
        for loc in UI_LOCALES:
            radio = QRadioButton(LOCALE_NATIVE_NAMES.get(loc, loc))
            self._locale_by_button[radio] = loc
            self._group.addButton(radio)
            root.addWidget(radio)
            if loc == current:
                radio.setChecked(True)
        if self._group.checkedButton() is None and self._group.buttons():
            self._group.buttons()[0].setChecked(True)

        row = QHBoxLayout()
        row.addStretch()
        ok = QPushButton(bilingual("language_picker_ok"))
        ok.setDefault(True)
        ok.clicked.connect(self._accept)
        row.addWidget(ok)
        root.addLayout(row)

        self._apply_theme()
        win_chrome.apply_to_widget(self)
        # Subprocess self-check (`-t startup`) accepts without a click so it
        # can watch whether MainWindow still appears after exec_() returns.
        if os.environ.get("IGP_SELFCHECK_ACCEPT_LANGUAGE"):
            QTimer.singleShot(0, self._accept)

    def selected_locale(self) -> str | None:
        return self.selected

    def _accept(self) -> None:
        button = self._group.checkedButton()
        loc = self._locale_by_button.get(button) if button is not None else None
        if loc in UI_LOCALES:
            self.selected = loc
        elif UI_LOCALES:
            self.selected = UI_LOCALES[0]
        self.accept()

    def _apply_theme(self) -> None:
        t = theme.current_theme()
        self.setStyleSheet(
            f"QDialog {{ background-color: {t.panel_bg}; }}"
            f"QLabel {{ color: {t.text_primary}; }}"
            f"QRadioButton {{ color: {t.text_primary}; }}"
        )
