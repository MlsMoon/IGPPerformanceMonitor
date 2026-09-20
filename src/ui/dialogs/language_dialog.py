"""First-run language picker.

Copy is joined from every locale catalog (``bilingual``), not ``tr()``: no
locale has been chosen yet, so a single-language ``tr()`` would look like the
app had already decided.
"""

from PyQt5.QtWidgets import (
    QButtonGroup, QDialog, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QVBoxLayout,
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
        self.selected: str | None = None

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
            radio.setProperty("locale", loc)
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

    def selected_locale(self) -> str | None:
        return self.selected

    def _accept(self) -> None:
        button = self._group.checkedButton()
        if button is not None:
            loc = button.property("locale")
            if loc in UI_LOCALES:
                self.selected = loc
        self.accept()

    def _apply_theme(self) -> None:
        t = theme.current_theme()
        self.setStyleSheet(
            f"QDialog {{ background-color: {t.panel_bg}; }}"
            f"QLabel {{ color: {t.text_primary}; }}"
            f"QRadioButton {{ color: {t.text_primary}; }}"
        )
