"""User-manual dialog — tree nav + themed markdown."""

from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QPalette, QTextCursor
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QPushButton, QSplitter, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from src.core.app_info import resource_root
from src.core.user_manual import (
    PAGES, OutlineNode, is_toc_title, load_page,
    page_outline, page_path, prepare_in_app_markdown, resolve_doc_href,
)
from src.i18n import tr
from src.ui import theme


class UserManualDialog(QDialog):
    """Left tree (pages + heading outline), markdown on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("user_manual_title"))
        self.resize(960, 640)
        self._current_path: Path | None = None
        self._outline: list[OutlineNode] = []

        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, 1)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("ManualTree")
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.setAnimated(False)
        self._tree.setMinimumWidth(200)
        self._tree.setMaximumWidth(340)
        self._tree.setSelectionMode(QTreeWidget.SingleSelection)
        splitter.addWidget(self._tree)

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
        splitter.setSizes([240, 720])

        self._tree.currentItemChanged.connect(self._on_tree_item)
        self._apply_theme()
        theme.theme_changed_signal().connect(self._on_theme_changed)
        self._rebuild_tree()

    def _rebuild_tree(self):
        self._tree.blockSignals(True)
        self._tree.clear()
        first = None
        for page_id, label_key in PAGES:
            page_item = QTreeWidgetItem([tr(label_key)])
            page_item.setData(0, Qt.UserRole, {"kind": "page", "page_id": page_id})
            font = page_item.font(0)
            font.setBold(True)
            page_item.setFont(0, font)
            self._tree.addTopLevelItem(page_item)
            if first is None:
                first = page_item
            stack: list[tuple[int, QTreeWidgetItem]] = [(1, page_item)]
            for node in page_outline(load_page(page_id)):
                child = QTreeWidgetItem([node.title])
                child.setData(0, Qt.UserRole, {
                    "kind": "heading",
                    "page_id": page_id,
                    "slug": node.slug,
                })
                while stack and stack[-1][0] >= node.level:
                    stack.pop()
                parent = stack[-1][1] if stack else page_item
                parent.addChild(child)
                stack.append((node.level, child))
            self._expand_item(page_item)
        self._tree.blockSignals(False)
        if first is not None:
            self._tree.setCurrentItem(first)

    def _expand_item(self, item: QTreeWidgetItem):
        item.setExpanded(True)
        for i in range(item.childCount()):
            self._expand_item(item.child(i))

    def _on_tree_item(self, current: QTreeWidgetItem, _previous: QTreeWidgetItem):
        if current is None:
            return
        data = current.data(0, Qt.UserRole) or {}
        page_id = data.get("page_id")
        if not page_id:
            return
        self._show_page(page_id, slug=data.get("slug"))

    def _show_page(self, page_id: str, slug: str | None = None):
        path = page_path(page_id)
        if self._current_path is None or path != self._current_path:
            self._show_file(path)
        if slug:
            QTimer.singleShot(0, lambda s=slug: self._browser.scrollToAnchor(s))
        else:
            self._browser.moveCursor(QTextCursor.Start)
            self._browser.ensureCursorVisible()

    def _show_file(self, path: Path):
        self._current_path = path
        self._browser.setSearchPaths([
            str(path.parent),
            str(resource_root() / "assets"),
            str(resource_root()),
        ])
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        if not raw.strip():
            self._outline = []
            self._browser.setPlainText(tr("user_manual_empty"))
            return
        self._outline = page_outline(raw)
        self._browser.setMarkdown(prepare_in_app_markdown(raw))
        self._apply_document_style()
        self._apply_heading_anchors(self._outline)

    def _apply_heading_anchors(self, nodes: list[OutlineNode]):
        """Name each heading block so the tree can scrollToAnchor."""
        by_title = {node.title: node.slug for node in nodes}
        doc = self._browser.document()
        cursor = QTextCursor(doc)
        block = doc.begin()
        while block.isValid():
            text = block.text().strip()
            slug = by_title.get(text)
            level = block.blockFormat().headingLevel()
            if slug and (level > 0 or text in by_title) and not is_toc_title(text):
                cursor.setPosition(block.position())
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                fmt = cursor.charFormat()
                fmt.setAnchor(True)
                fmt.setAnchorNames([slug])
                cursor.mergeCharFormat(fmt)
            block = block.next()

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
        target = None
        if self._current_path is not None:
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

    def _apply_document_style(self):
        """Body text colour; links follow the theme — never the default web blue."""
        t = theme.current_theme()
        self._browser.document().setDefaultStyleSheet(
            f"body {{ color: {t.text_primary}; }}"
            f"a {{ color: {t.text_secondary}; text-decoration: underline;"
            f" text-decoration-color: {t.text_muted}; }}"
            f"h1, h2, h3, h4, h5, h6 {{ color: {t.text_primary}; }}"
        )
        pal = self._browser.palette()
        pal.setColor(QPalette.Base, QColor(t.card_bg))
        pal.setColor(QPalette.Text, QColor(t.text_primary))
        pal.setColor(QPalette.Link, QColor(t.text_secondary))
        pal.setColor(QPalette.LinkVisited, QColor(t.text_muted))
        self._browser.setPalette(pal)

    def _apply_theme(self):
        t = theme.current_theme()
        self._tree.setStyleSheet(
            f"QTreeWidget#ManualTree {{ background-color: {t.panel_bg};"
            f" color: {t.text_primary}; border: none; }}"
            f"QTreeWidget#ManualTree::item {{ padding: 4px 6px; }}"
            f"QTreeWidget#ManualTree::item:selected {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
            f"QTreeWidget#ManualTree::item:selected:!active {{"
            f" background-color: {t.selection}; color: {t.selection_text}; }}"
            f"QTreeWidget#ManualTree::branch {{ background: {t.panel_bg}; }}"
        )
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background-color: {t.card_bg}; color: {t.text_primary};"
            f" border: none; }}"
        )
        self._apply_document_style()

    def _on_theme_changed(self):
        self._apply_theme()
        if self._current_path is not None:
            self._show_file(self._current_path)
