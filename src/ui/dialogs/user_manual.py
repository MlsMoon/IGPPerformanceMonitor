"""User-manual dialog — renders bundled docs/<locale>/*.md."""

from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QPalette
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from src.core.app_info import resource_root
from src.core.user_manual import PAGES, page_id_for_path, page_path, resolve_doc_href
from src.i18n import tr
from src.ui import theme


class UserManualDialog(QDialog):
    """Left-nav user guide / troubleshooting, markdown on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("user_manual_title"))
        self.resize(860, 600)
        self._current_path: Path = page_path(PAGES[0][0])

        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, 1)

        self._page_list = QListWidget(self)
        self._page_list.setObjectName("ManualPageList")
        self._page_list.setSelectionMode(QListWidget.SingleSelection)
        self._page_list.setMinimumWidth(140)
        self._page_list.setMaximumWidth(260)
        for page_id, label_key in PAGES:
            item = QListWidgetItem(tr(label_key))
            item.setData(Qt.UserRole, page_id)
            self._page_list.addItem(item)
        splitter.addWidget(self._page_list)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._browser = QTextBrowser(right)
        self._browser.setObjectName("ManualBrowser")
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_anchor)
        right_layout.addWidget(self._browser, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(tr("btn_close"), self)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([180, 680])

        self._page_list.currentItemChanged.connect(self._on_page_selected)
        self._apply_theme()
        theme.theme_changed_signal().connect(self._on_theme_changed)
        self._page_list.setCurrentRow(0)

    def _on_page_selected(self, current: QListWidgetItem, _previous: QListWidgetItem):
        if current is None:
            return
        self._show_page(current.data(Qt.UserRole))

    def _show_page(self, page_id: str):
        path = page_path(page_id)
        self._show_file(path)

    def _show_file(self, path: Path):
        self._current_path = path
        self._browser.setSearchPaths([
            str(path.parent),
            str(resource_root() / "assets"),
            str(resource_root()),
        ])
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        if not text:
            self._browser.setPlainText(tr("user_manual_empty"))
        else:
            self._browser.setMarkdown(text)
        self._sync_list_to_path(path)

    def _sync_list_to_path(self, path):
        page_id = page_id_for_path(path)
        if page_id is None:
            return
        for i in range(self._page_list.count()):
            item = self._page_list.item(i)
            if item.data(Qt.UserRole) == page_id:
                if self._page_list.currentRow() != i:
                    self._page_list.blockSignals(True)
                    self._page_list.setCurrentRow(i)
                    self._page_list.blockSignals(False)
                return

    def _on_anchor(self, url: QUrl):
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
            return
        fragment = url.fragment()
        href = url.toLocalFile() if url.isLocalFile() else url.toString()
        if not href or href.startswith("#"):
            if fragment:
                self._browser.scrollToAnchor(fragment)
            return
        target = resolve_doc_href(self._current_path, href)
        if target is None:
            target = resolve_doc_href(self._current_path, url.toString())
        if target is not None:
            self._show_file(target)
            if fragment:
                self._browser.scrollToAnchor(fragment)
            return
        if fragment:
            self._browser.scrollToAnchor(fragment)

    def _apply_theme(self):
        t = theme.current_theme()
        list_sel = (
            f"QListWidget::item:selected {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
            f"QListWidget::item:selected:!active {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
        )
        self._page_list.setStyleSheet(list_sel)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background-color: {t.card_bg}; color: {t.text_primary};"
            f" border: none; }}"
        )
        pal = self._browser.palette()
        pal.setColor(QPalette.Base, QColor(t.card_bg))
        pal.setColor(QPalette.Text, QColor(t.text_primary))
        self._browser.setPalette(pal)

    def _on_theme_changed(self):
        self._apply_theme()
        self._show_file(self._current_path)
