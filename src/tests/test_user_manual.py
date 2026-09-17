"""Test: bundled user-manual paths and in-app dialog."""

from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QTreeWidget

from src.core.user_manual import (
    PAGE_FILES, docs_root, load_page, locale_folder, page_outline,
    page_path, prepare_in_app_markdown, resolve_doc_href,
)
from src.i18n import tr
from src.ui.dialogs.user_manual import UserManualDialog
from src.ui.main_window import MainWindow


def run():
    assert locale_folder("zh_CN") == "zh-CN"
    assert locale_folder("en") == "en"
    assert locale_folder("ja") == "en", "UI has no ja locale; docs fall back to English"

    root = docs_root()
    assert root.is_dir(), f"docs/ missing at {root}"

    for loc in ("en", "zh_CN"):
        for page_id in PAGE_FILES:
            text = load_page(page_id, loc)
            assert text.strip().startswith("#"), f"{loc}/{page_id} is empty or not markdown"

    guide = page_path("user-guide", "en")
    trouble = resolve_doc_href(guide, "troubleshooting.md")
    assert trouble == page_path("troubleshooting", "en").resolve()

    zh_guide = resolve_doc_href(guide, "../zh-CN/user-guide.md")
    assert zh_guide == page_path("user-guide", "zh_CN").resolve()

    assert resolve_doc_href(guide, "https://github.com/MlsMoon/IGPPerformanceMonitor") is None
    assert resolve_doc_href(guide, "../../src/main.py") is None
    assert resolve_doc_href(guide, "#1-what-you-need") is None

    mw = MainWindow()
    labels = []
    for menu_action in mw.menuBar().actions():
        menu = menu_action.menu()
        if menu is None:
            continue
        for action in menu.actions():
            labels.append(action.text())
    assert tr("menu_user_manual") in labels, "Help → User Manual"

    guide_md = load_page("user-guide", "en")
    outline = page_outline(guide_md)
    assert any(node.level == 2 for node in outline), "guide must have H2 sections"
    assert any(node.level == 3 for node in outline), "guide must have H3 sections"
    assert not any(node.title.casefold() == "contents" for node in outline)
    in_app = prepare_in_app_markdown(guide_md)
    assert "## Contents" not in in_app
    assert "[English]" not in in_app

    dlg = UserManualDialog(mw)
    assert dlg._browser.toPlainText().strip(), "guide body is empty"
    link = dlg._browser.palette().color(QPalette.Link)
    assert link.name().lower() != "#0000ff", f"default web-blue link {link.name()}"
    tree = dlg.findChild(QTreeWidget, "ManualTree")
    assert tree is not None and tree.topLevelItemCount() == 2, "page tree"
    guide_item = tree.topLevelItem(0)
    assert guide_item.childCount() >= 10, "guide H2 rows"
    assert any(
        guide_item.child(i).childCount() > 0
        for i in range(guide_item.childCount())
    ), "guide must nest H3 under H2"
    first = dlg._browser.toPlainText()
    dlg._show_page("troubleshooting")
    second = dlg._browser.toPlainText()
    assert second.strip() and second != first, "switching pages must change the body"
