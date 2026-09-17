"""Changelog dialog — renders the bundled CHANGELOG.md with version navigation."""
import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton,
    QSplitter, QListWidget, QListWidgetItem, QWidget,
)

from src.i18n import tr
from src.core.app_info import resource_root
from src.ui import theme


class ChangelogDialog(QDialog):
    """Shows the project CHANGELOG.md with a left-side version list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("changelog_title"))
        self.resize(780, 540)

        raw = self._load_changelog_raw()
        self._versions = self._parse_changelog_versions(raw)

        root_layout = QVBoxLayout(self)

        if not self._versions:
            # No parseable versions — fall back to the simple single-pane view
            browser = QTextBrowser(self)
            browser.setOpenExternalLinks(True)
            browser.setPlainText(tr("changelog_empty"))
            root_layout.addWidget(browser, 1)
        else:
            splitter = QSplitter(Qt.Horizontal, self)
            root_layout.addWidget(splitter, 1)

            # --- Left: version list ---
            self._version_list = QListWidget(self)
            self._version_list.setObjectName("VersionList")
            self._version_list.setSelectionMode(QListWidget.SingleSelection)
            self._version_list.setFixedWidth(120)
            for ver, _content in self._versions:
                item = QListWidgetItem(f"v{ver}")
                item.setData(Qt.UserRole, ver)
                self._version_list.addItem(item)
            splitter.addWidget(self._version_list)

            # --- Right: content + close ---
            right = QWidget(self)
            right_layout = QVBoxLayout(right)
            right_layout.setContentsMargins(0, 0, 0, 0)

            self._browser = QTextBrowser(right)
            self._browser.setOpenExternalLinks(True)
            right_layout.addWidget(self._browser, 1)

            btn_row = QHBoxLayout()
            btn_row.addStretch()
            close_btn = QPushButton(tr("btn_close"), self)
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)
            right_layout.addLayout(btn_row)

            splitter.addWidget(right)
            splitter.setStretchFactor(0, 0)   # left fixed-width
            splitter.setStretchFactor(1, 1)   # right stretches

            # Wire selection → content
            self._version_list.currentItemChanged.connect(self._on_version_selected)

            # Theme
            self._apply_theme()
            theme.theme_changed_signal().connect(self._on_theme_changed)

            # Default to latest (first) version
            self._version_list.setCurrentRow(0)

        # Bottom close button for the no-versions fallback
        if not self._versions:
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            close_btn = QPushButton(tr("btn_close"), self)
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)
            root_layout.addLayout(btn_row)

    # ----------------------------------------------------------------
    # Content loading / parsing
    # ----------------------------------------------------------------

    @staticmethod
    def _load_changelog_raw() -> str:
        path = resource_root() / "CHANGELOG.md"
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @staticmethod
    def _parse_changelog_versions(raw: str) -> list[tuple[str, str]]:
        """Split raw CHANGELOG.md into [(version, markdown_block), …].

        Blocks are delimited by ``## X.Y.Z`` lines.  The first ``# Changelog``
        title line is skipped.
        """
        if not raw:
            return []
        # Split on "## " at line start — each block is "X.Y.Z\n- …lines…"
        blocks = re.split(r"\n(?=## )", raw)
        versions: list[tuple[str, str]] = []
        for block in blocks:
            block = block.strip()
            # Skip the top-level "# Changelog" heading
            if not block.startswith("## "):
                continue
            # First line: "## X.Y.Z"
            first_line = block.split("\n", 1)[0]
            ver = first_line[3:].strip()  # remove "## " prefix
            if ver:
                versions.append((ver, block))
        return versions

    # ----------------------------------------------------------------
    # Slots
    # ----------------------------------------------------------------

    def _on_version_selected(self, current: QListWidgetItem, _previous: QListWidgetItem):
        if current is None:
            return
        ver = current.data(Qt.UserRole)
        for v, content in self._versions:
            if v == ver:
                self._browser.setMarkdown(content)
                return

    # ----------------------------------------------------------------
    # Theming
    # ----------------------------------------------------------------

    def _apply_theme(self):
        if not hasattr(self, "_version_list"):
            return
        t = theme.current_theme()
        list_sel = (
            f"QListWidget::item:selected {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
            f"QListWidget::item:selected:!active {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
        )
        self._version_list.setStyleSheet(list_sel)

    def _on_theme_changed(self):
        self._apply_theme()
