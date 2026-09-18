"""User-manual dialog — tree nav + themed markdown."""

from pathlib import Path

from PyQt5.QtCore import QEvent, Qt, QTimer, QUrl
from PyQt5.QtGui import (
    QColor, QDesktopServices, QImage, QPalette, QPixmap, QTextCharFormat,
    QTextCursor, QTextDocument,
)
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QPushButton, QSplitter, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from src.core.app_info import resource_root
from src.core.user_manual import (
    PAGES, OutlineNode, docs_root, is_toc_title, load_page,
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
        self._fitting = False

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
        self._browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._browser.anchorClicked.connect(self._on_anchor)
        self._browser.viewport().installEventFilter(self)
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

    def eventFilter(self, obj, event):
        if obj is self._browser.viewport() and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self._fit_images)
        return super().eventFilter(obj, event)

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
        parent = path.parent.resolve()
        self._browser.setSearchPaths([
            str(parent),
            str(docs_root()),
            str(docs_root() / "images"),
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
        # Relative ``../images/<locale>/shot.png`` resolves against the page dir.
        self._browser.document().setBaseUrl(QUrl.fromLocalFile(str(parent) + "/"))
        self._browser.setMarkdown(prepare_in_app_markdown(raw))
        self._browser.document().setBaseUrl(QUrl.fromLocalFile(str(parent) + "/"))
        self._apply_document_style()
        self._apply_heading_anchors(self._outline)
        self._fit_images()

    def _apply_heading_anchors(self, nodes: list[OutlineNode]):
        """Invisible named anchors — do not turn headings into underlined links."""
        by_title = {node.title: node.slug for node in nodes}
        doc = self._browser.document()
        t = theme.current_theme()
        blocks = []
        block = doc.begin()
        while block.isValid():
            blocks.append(block)
            block = block.next()
        cursor = QTextCursor(doc)
        for block in reversed(blocks):
            text = block.text().strip()
            slug = by_title.get(text)
            level = block.blockFormat().headingLevel()
            if not slug or is_toc_title(text):
                continue
            if level <= 0 and text not in by_title:
                continue
            fmt = QTextCharFormat()
            fmt.setAnchor(True)
            fmt.setAnchorNames([slug])
            fmt.setForeground(QColor(t.text_primary))
            fmt.setFontUnderline(False)
            cursor.setPosition(block.position())
            cursor.insertText("\u200b", fmt)

    def _natural_image_size(self, name: str) -> tuple[int, int]:
        doc = self._browser.document()
        url = QUrl(name)
        res = doc.resource(QTextDocument.ImageResource, url)
        if res is None:
            res = doc.resource(QTextDocument.ImageResource, QUrl.fromLocalFile(name))
        if isinstance(res, QPixmap) and not res.isNull():
            return res.width(), res.height()
        if isinstance(res, QImage) and not res.isNull():
            return res.width(), res.height()
        path = url.toLocalFile() if url.isLocalFile() else name
        loaded = QImage(path)
        if loaded.isNull() and self._current_path is not None:
            loaded = QImage(str((self._current_path.parent / name).resolve()))
        if loaded.isNull():
            return (0, 0)
        return loaded.width(), loaded.height()

    def _fit_images(self):
        """Scale markdown images to the viewport so they are not clipped."""
        if self._fitting:
            return
        doc = self._browser.document()
        max_w = self._browser.viewport().width() - 8
        if max_w < 80:
            return
        self._fitting = True
        try:
            cursor = QTextCursor(doc)
            block = doc.begin()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    frag = it.fragment()
                    if frag.isValid():
                        cf = frag.charFormat()
                        if cf.isImageFormat():
                            img_fmt = cf.toImageFormat()
                            nw, nh = self._natural_image_size(img_fmt.name())
                            if nw <= 0 or nh <= 0:
                                nw, nh = int(img_fmt.width()), int(img_fmt.height())
                            if nw > max_w > 0:
                                nh = max(1, int(nh * (max_w / nw)))
                                nw = max_w
                            if nw > 0 and nh > 0:
                                img_fmt.setWidth(nw)
                                img_fmt.setHeight(nh)
                                cursor.setPosition(frag.position())
                                cursor.setPosition(
                                    frag.position() + frag.length(),
                                    QTextCursor.KeepAnchor,
                                )
                                cursor.setCharFormat(img_fmt)
                    it += 1
                block = block.next()
        finally:
            self._fitting = False

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
        """Body text; links stay muted. Selection is a gray wash, not accent."""
        t = theme.current_theme()
        self._browser.document().setDefaultStyleSheet(
            f"body {{ color: {t.text_primary}; }}"
            f"a {{ color: {t.text_muted}; text-decoration: underline;"
            f" text-decoration-color: {t.border}; }}"
            f"h1, h2, h3, h4, h5, h6 {{ color: {t.text_primary}; }}"
        )
        pal = self._browser.palette()
        pal.setColor(QPalette.Base, QColor(t.card_bg))
        pal.setColor(QPalette.Text, QColor(t.text_primary))
        pal.setColor(QPalette.Link, QColor(t.text_muted))
        pal.setColor(QPalette.LinkVisited, QColor(t.text_muted))
        pal.setColor(QPalette.Highlight, QColor(t.hover_bg))
        pal.setColor(QPalette.HighlightedText, QColor(t.text_primary))
        pal.setColor(QPalette.Inactive, QPalette.Highlight, QColor(t.hover_bg))
        pal.setColor(
            QPalette.Inactive, QPalette.HighlightedText, QColor(t.text_primary))
        self._browser.setPalette(pal)

    def _apply_theme(self):
        t = theme.current_theme()
        # Reading chrome: gray wash, not the purple list selection or the
        # accent-blue QTextEdit selection from app_qss.
        self._tree.setStyleSheet(
            f"QTreeWidget#ManualTree {{ background-color: {t.panel_bg};"
            f" color: {t.text_primary}; border: none; }}"
            f"QTreeWidget#ManualTree::item {{ padding: 4px 6px; }}"
            f"QTreeWidget#ManualTree::item:hover {{"
            f" background-color: {t.hover_bg}; }}"
            f"QTreeWidget#ManualTree::item:selected {{"
            f" background-color: {t.hover_bg}; color: {t.text_primary}; }}"
            f"QTreeWidget#ManualTree::item:selected:!active {{"
            f" background-color: {t.hover_bg}; color: {t.text_primary}; }}"
            f"QTreeWidget#ManualTree::branch {{ background: {t.panel_bg}; }}"
        )
        self._browser.setStyleSheet(
            f"QTextBrowser#ManualBrowser {{ background-color: {t.card_bg};"
            f" color: {t.text_primary}; border: none;"
            f" selection-background-color: {t.hover_bg};"
            f" selection-color: {t.text_primary}; }}"
        )
        self._apply_document_style()

    def _on_theme_changed(self):
        self._apply_theme()
        if self._current_path is not None:
            self._show_file(self._current_path)
