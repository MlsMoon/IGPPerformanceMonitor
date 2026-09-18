"""UI self-check: build the real window, drive the real slots, describe what came out.

This replaces a pile of geometry assertions. Anything that throws is an error;
everything else is printed as a fact, plus PNGs of the real window so the
reader can see the layout instead of inferring it from numbers.
"""

from __future__ import annotations

import os
import re

from PyQt5.QtWidgets import QFrame, QScrollArea
from PyQt5.QtGui import QFontMetrics

from src import selfcheck
from src.i18n import tr
from src.models import frame_series_key, pretty_series_key
from src.selfcheck import data
from src.selfcheck.replay import SETTLE_MS as _SETTLE_MS, seed_window, spin as _spin
from src.selfcheck.report import Report
from src.selfcheck.spec import Area

AREA = Area(
    name="ui",
    needs_qt=True,
    judge="visual",
    touches=(
        "src/ui/",
        "src/i18n/",
        "src/core/user_manual.py",
        "src/core/changelog.py",
        "src/core/app_config.py",
        "src/core/process_list.py",
        "assets/",
        "docs/",
    ),
)
from src.ui import motion, theme, win_chrome
from src.ui.chart_base import SystemChip
from src.ui.main_window import MainWindow
from src.ui.views.overlay_window import OverlayWindow

_SHOT_DIR = "shots"


def run(report: Report, out_dir: str, **_kwargs) -> None:
    frames = data.load_frames_if_available()
    apps = sorted({f.application for f in frames if f.application})
    series = sorted({frame_series_key(f) for f in frames if f.application or f.process_id})

    report.section("input")
    report.fact("real frames", len(frames))
    report.fact("apps in capture", ", ".join(apps) or "(none)")
    report.fact("series keys", ", ".join(pretty_series_key(k) for k in series) or "(none)")
    if not frames:
        report.suspect(
            "no real capture available, so charts and stats render empty — "
            "layout facts below are still meaningful, data ones are not")

    window = MainWindow()
    span = _seed(window, frames, series)
    report.fact("replayed timeline seconds", f"{span:.1f}" if span else "(none)")

    _describe_window(report, window)
    _describe_chips(report, window)
    _exercise_panels(report, window)
    _exercise_process_picker(report, window)
    _exercise_charts(report, window)
    _exercise_qss(report)
    _exercise_docs(report, window)
    _exercise_changelog(report, window)
    _exercise_overlay(report)
    _shoot(report, window, out_dir)
    _report_qt_messages(report)


def _seed(window: MainWindow, frames, apps) -> float:
    """Push the real capture into the window's own store.

    It has to be *this* store: the screenshots are of this window, and feeding
    a throwaway MonitorView instead produced reports describing populated
    charts next to PNGs of an empty app.
    """
    return seed_window(window, frames, apps)


def _report_qt_messages(report: Report) -> None:
    """Qt's own complaints, which are otherwise lost in the console noise.

    A stylesheet Qt cannot parse is silently dropped, so the widget just renders
    unstyled — no exception, no failed assertion, nothing to notice until you
    look at it.
    """
    report.section("qt warnings")
    seen: dict[str, int] = {}
    for message in selfcheck.qt_messages:
        # Collapse the object pointer so repeats of one complaint group up.
        key = re.sub(r"0x[0-9a-fA-F]+", "0x…", message)
        seen[key] = seen.get(key, 0) + 1
    report.fact("distinct warnings", len(seen))
    for message, count in sorted(seen.items(), key=lambda kv: -kv[1]):
        report.suspect(f"Qt: {message}" + (f"  (x{count})" if count > 1 else ""))


def _describe_window(report: Report, window: MainWindow) -> None:
    report.section("window")
    with report.step("window facts"):
        report.fact("title", window.windowTitle())
        report.fact("minimum width", window.minimumWidth())
        report.fact("dev badge", window._dev_badge.text() if window._dev_badge else "(none)")

        shortcuts = set()
        for menu_action in window.menuBar().actions():
            menu = menu_action.menu()
            if menu is None:
                continue
            for action in menu.actions():
                text = action.shortcut().toString()
                if text:
                    shortcuts.add(text)
        report.fact("menu shortcuts", " ".join(sorted(shortcuts)) or "(none)")
        report.fact("click-through default", window._click_through_action.isChecked())

    with report.step("native title bar theming"):
        # Must be a safe no-op off Windows and offscreen.
        win_chrome.apply_to_widget(window)
        win_chrome.refresh_all()
        report.fact("win_chrome COLORREF", hex(win_chrome._colorref("#123456")))

    with report.step("motion"):
        report.fact("animations enabled", motion.enabled())
        motion.fade_in(window)
        # The effect is removed when the animation finishes, so with motion on
        # it is legitimately still attached right now — let it run first.
        _spin(motion.NORMAL * 3)
        if window.graphicsEffect() is not None:
            report.suspect(
                "fade_in left an opacity effect attached after it finished, "
                "which permanently costs a compositing pass on every repaint")
        report.fact("hover duration ms", motion.FAST)
        report.fact("exit duration ms", motion.exit_duration(motion.NORMAL))


def _describe_chips(report: Report, window: MainWindow) -> None:
    """The system info bar has clipped and has stretched the window before."""
    report.section("system info chips")
    with report.step("chip measurement"):
        long_chip = SystemChip("GPU: " + "NVIDIA GeForce RTX 4060 Ti " * 6)
        report.fact("long chip min width", long_chip.minimumSizeHint().width())
        if long_chip.minimumSizeHint().width() >= 200:
            report.suspect(
                "a long GPU string widens the row minimum and can stretch the window")

        bar = window._monitor_view._sys_info_bar
        clipping = []
        for i in range(bar.layout().count()):
            chip = bar.layout().itemAt(i).widget()
            if not isinstance(chip, SystemChip):
                continue
            margins = chip.contentsMargins()
            needed = (QFontMetrics(chip.font()).height()
                      + margins.top() + margins.bottom())
            if chip.sizeHint().height() < needed:
                clipping.append(chip.toolTip()[:40])
        report.fact("chips", bar.layout().count())
        report.fact("chips that would clip", len(clipping))
        for text in clipping:
            report.suspect(f"chip clips its text: {text!r}")


def _exercise_panels(report: Report, window: MainWindow) -> None:
    report.section("panels")
    view = window._monitor_view
    with report.step("system info collapse/expand"):
        report.fact("system info expanded", view.is_system_info_expanded())
        view.set_system_info_expanded(False)
        collapsed_hidden = view._sys_info_bar.isHidden()
        header_left = (
            not view._sys_info_panel.isHidden()
            and not view._sys_info_panel._title.isHidden()
        )
        view.set_system_info_expanded(True)
        expanded_shown = not view._sys_info_bar.isHidden()
        report.fact("collapse hides chips", collapsed_hidden)
        report.fact("collapse keeps header", header_left)
        report.fact("expand shows chips", expanded_shown)
        if not (collapsed_hidden and expanded_shown):
            report.suspect("system info toggle does not round-trip")
        if not header_left:
            report.suspect("system info collapse hid the header — reuse CollapsibleSection")

    with report.step("chart visibility panel sync"):
        view.toggle_visibility_panel()
        window._sync_charts_panel_action()
        after_collapse = window._charts_panel_action.isChecked()
        view.toggle_visibility_panel()
        window._sync_charts_panel_action()
        after_expand = window._charts_panel_action.isChecked()
        report.fact("menu item tracks panel", f"collapsed={after_collapse} expanded={after_expand}")
        if after_collapse or not after_expand:
            report.suspect("View menu checkbox is out of sync with the inline panel")


def _exercise_process_picker(report: Report, window: MainWindow) -> None:
    """Prove same-exe instances stay distinct in the picker (Task Manager style)."""
    from collections import Counter

    from src.core.process_list import (
        ProcessInstance, format_instance_label, list_process_instances,
    )

    report.section("process picker")
    a = format_instance_label("Unity.exe", 111, "CatGame - Unity")
    b = format_instance_label("Unity.exe", 222, "Kitchen - Unity")
    report.fact("same-exe labels differ", f"{a!r} vs {b!r}")
    if a == b:
        report.error("two Unity instances format to the same list label")
    la = ProcessInstance(111, "Unity.exe", "CatGame - Unity").list_label()
    lb = ProcessInstance(222, "Unity.exe", "Kitchen - Unity").list_label()
    report.fact("picker row labels differ", f"{la!r} vs {lb!r}")
    if la == lb:
        report.error("two Unity picker rows format to the same text")
    if "CatGame" not in la or "Kitchen" not in lb:
        report.error("picker rows dropped the window title that distinguishes Unity instances")

    instances = list_process_instances()
    names = [i.name.lower() for i in instances]
    dupes = sorted({n for n, c in Counter(names).items() if c > 1})
    report.fact("running exe instances", len(instances))
    report.fact("duplicate exe names", ", ".join(dupes[:8]) or "(none)")

    panel = window._process_panel
    avail = panel._available_list
    from src.ui.panels.process_panel import _item_instance

    pids: list[int] = []
    for i in range(avail.count()):
        inst = _item_instance(avail.item(i))
        if inst is not None and inst.pid:
            pids.append(inst.pid)
    report.fact("available list rows", avail.count())
    if pids and len(pids) != len(set(pids)):
        report.error("available list has duplicate PIDs")

    for exe in dupes[:3]:
        rows = []
        for i in range(avail.count()):
            inst = _item_instance(avail.item(i))
            if inst is not None and inst.name.lower() == exe:
                rows.append(inst.pid)
        live = sum(1 for p in instances if p.name.lower() == exe)
        monitored = [t for t in panel.get_targets() if t.name.lower() == exe]
        report.fact(f"{exe} rows (available/live)", f"{len(rows)}/{live}")
        if not monitored and live > 1 and len(rows) < 2:
            report.error(
                f"{exe} has {live} live PIDs but the available list collapsed them")

    titled = next((i for i in instances if i.title.strip()), None)
    if titled and titled.title.strip():
        needle = titled.title.strip()[:8]
        panel._search_input.setText(needle)
        panel._apply_search()
        visible = sum(
            1 for i in range(avail.count()) if not avail.item(i).isHidden())
        report.fact("search by window title visible rows", visible)
        if visible == 0:
            report.suspect(
                "search by window title hid every row — tooltip/search blob may omit titles")
        panel._search_input.clear()
        panel._apply_search()


def _exercise_charts(report: Report, window: MainWindow) -> None:
    report.section("charts and stats")
    with report.step("MonitorView with real frames"):
        view = window._monitor_view
        store = window._data_store
        view.refresh_display_layout()
        view.save_layout_state()

        report.fact("chart cards", len(view._chart_widgets))
        report.fact("charts in a scroll area",
                    view.findChild(QScrollArea, "ChartsScrollArea") is not None)
        report.fact("stats/charts splitter panes", view._content_splitter.count())

        containers = view.findChildren(QFrame, "StatsList")
        rows = containers[0].findChildren(QFrame, "StatsRow") if containers else []
        last = containers[0].findChildren(QFrame, "StatsRowLast") if containers else []
        report.fact("stats containers", len(containers))
        report.fact("stats rows", f"{len(rows)} + {len(last)} last")
        # With no frames the stats area is a placeholder, so a missing container
        # says nothing — do not make the reader chase it.
        if store.get_frame_count() and len(containers) != 1:
            report.suspect(
                f"stats should be one flat surface, found {len(containers)} containers")

        for key in list(view._chart_widgets)[:1]:
            view.set_chart_visible(key, False)
            hidden = not view.is_chart_visible(key)
            view.set_chart_visible(key, True)
            shown = view.is_chart_visible(key)
            report.fact("visibility toggle round-trip", f"hide={hidden} show={shown}")


def _exercise_qss(report: Report) -> None:
    """Generate every QSS string from every theme and check it parses.

    Walking the module rather than listing generators means a new one is
    covered the day it is written. Unbalanced braces are the failure mode worth
    catching by machine: Qt drops a stylesheet it cannot parse and renders the
    widget unstyled, with no exception and nothing to notice but the look.
    """
    report.section("stylesheets")
    generators = sorted(
        name for name in dir(theme)
        if name.endswith("_qss") and callable(getattr(theme, name))
    )
    checked = 0
    for preset in (theme.DARK, theme.LIGHT):
        for name in generators:
            try:
                qss = getattr(theme, name)(preset)
            except Exception as exc:
                report.error(f"theme.{name}({preset.name}) raised {exc!r}")
                continue
            if not isinstance(qss, str):
                continue  # an applier (apply_app_qss), not a generator
            checked += 1
            if qss.count("{") != qss.count("}"):
                report.error(
                    f"theme.{name}({preset.name}) has unbalanced braces "
                    f"({qss.count('{')} open, {qss.count('}')} close) — "
                    "Qt will silently drop the whole stylesheet")
    report.fact("generators", len(generators))
    report.fact("stylesheets checked", checked)


def _exercise_docs(report: Report, window: MainWindow) -> None:
    """Bundled user manual: pages present, links resolved, dialog usable."""
    from src.core.user_manual import (
        PAGE_FILES, docs_root, load_page, locale_folder, markdown_image_hrefs,
        page_path, resolve_doc_href, resolve_doc_image,
    )
    from src.ui.dialogs.user_manual import UserManualDialog

    report.section("user manual")
    with report.step("bundled pages"):
        report.fact("docs root", docs_root())
        if not docs_root().is_dir():
            report.error(f"docs/ is missing at {docs_root()}")
            return
        missing = [
            f"{loc}/{page}"
            for loc in ("en", "zh_CN") for page in PAGE_FILES
            if not load_page(page, loc).strip().startswith("#")
        ]
        report.fact("pages", f"{len(PAGE_FILES) * 2} expected, {len(missing)} missing")
        for name in missing:
            report.error(f"manual page empty or not markdown: {name}")
        report.fact("unknown locale falls back to", locale_folder("ja"))

    with report.step("link resolution"):
        guide = page_path("user-guide", "en")
        # Escaping the docs tree would let a crafted link open project source
        # in the manual viewer, so these are failures, not judgement calls.
        for href in ("../../src/main.py", "https://github.com/MlsMoon/IGPPerformanceMonitor",
                     "#1-what-you-need"):
            if resolve_doc_href(guide, href) is not None:
                report.error(f"resolve_doc_href should refuse {href!r}")
        report.fact("sibling link", resolve_doc_href(guide, "troubleshooting.md") is not None)
        report.fact("cross-locale link",
                    resolve_doc_href(guide, "../zh-CN/user-guide.md") is not None)
        if resolve_doc_image(guide, "../../assets/icon.png") is not None:
            report.error("resolve_doc_image should refuse a path outside docs/")

    with report.step("markdown images"):
        missing = []
        counted = 0
        for loc_dir in ("en", "zh-CN", "zh-TW", "ja"):
            for filename in PAGE_FILES.values():
                md = docs_root() / loc_dir / filename
                if not md.is_file():
                    continue
                text = md.read_text(encoding="utf-8")
                for href in markdown_image_hrefs(text):
                    if href.startswith(("http://", "https://", "data:")):
                        continue
                    counted += 1
                    if resolve_doc_image(md, href) is None:
                        missing.append(f"{loc_dir}/{filename}: {href}")
        report.fact("image refs", counted)
        for item in missing:
            report.error(f"manual image missing or outside docs/: {item}")

    with report.step("dialog"):
        labels = []
        for menu_action in window.menuBar().actions():
            menu = menu_action.menu()
            if menu is not None:
                labels.extend(action.text() for action in menu.actions())
        report.fact("Help menu entry wired", tr("menu_user_manual") in labels)
        if tr("menu_user_manual") not in labels:
            report.error("Help → User Manual is not in the menu bar")

        dialog = UserManualDialog(window)
        first = dialog._browser.toPlainText()
        dialog._show_page("troubleshooting")
        second = dialog._browser.toPlainText()
        report.fact("guide body chars", len(first))
        report.fact("switching pages changes body", bool(second.strip()) and second != first)
        if not first.strip():
            report.error("the manual dialog opened with an empty body")

        from PyQt5.QtGui import QPalette
        dialog.resize(960, 640)
        dialog.move(-8000, -8000)
        dialog.show()
        _spin(200)
        dialog._show_page("user-guide")
        _spin(200)
        dialog._fit_images()
        n_img = 0
        too_wide = 0
        max_w = dialog._browser.viewport().width()
        block = dialog._browser.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.charFormat().isImageFormat():
                    n_img += 1
                    width = frag.charFormat().toImageFormat().width()
                    if max_w > 80 and width > max_w + 1:
                        too_wide += 1
                it += 1
            block = block.next()
        report.fact("embedded images", n_img)
        report.fact("viewport width", max_w)
        report.fact("images wider than viewport", too_wide)
        if max_w > 80 and n_img == 0:
            report.suspect("user-guide rendered with no images in the manual dialog")
        if too_wide:
            report.error(
                f"{too_wide} manual image(s) wider than the viewport — they will clip")
        highlight = dialog._browser.palette().color(QPalette.Highlight).name()
        report.fact("browser highlight", highlight)
        if highlight.lower() in ("#9c36b5", "#4dabf7", "#1971c2"):
            report.error(
                f"manual browser highlight is {highlight} — use theme.hover_bg")
        dialog.close()


def _exercise_changelog(report: Report, window: MainWindow) -> None:
    """Both locale files must list the same ## X.Y.Z versions; the dialog must open."""
    from src.core.changelog import changelog_path, load_raw, version_ids
    from src.ui.dialogs.changelog_dialog import ChangelogDialog

    report.section("changelog")
    with report.step("bundled files"):
        en_ids = version_ids(load_raw("en"))
        zh_ids = version_ids(load_raw("zh_CN"))
        report.fact("english versions", ", ".join(en_ids) or "(none)")
        report.fact("chinese versions", ", ".join(zh_ids) or "(none)")
        for loc in ("en", "zh_CN"):
            path = changelog_path(loc)
            if not path.is_file():
                report.error(f"changelog missing: {path.name}")
        if not en_ids:
            report.error("CHANGELOG.md has no ## X.Y.Z blocks")
        if en_ids != zh_ids:
            report.error(
                f"changelog version mismatch: en={en_ids} zh_CN={zh_ids}"
            )

    with report.step("dialog"):
        labels = []
        for menu_action in window.menuBar().actions():
            menu = menu_action.menu()
            if menu is not None:
                labels.extend(action.text() for action in menu.actions())
        report.fact("Help menu entry wired", tr("menu_changelog") in labels)
        if tr("menu_changelog") not in labels:
            report.error("Help → Changelog is not in the menu bar")

        dialog = ChangelogDialog(window)
        body = ""
        if hasattr(dialog, "_browser"):
            body = dialog._browser.toPlainText()
        report.fact("latest body chars", len(body))
        if not body.strip():
            report.error("the changelog dialog opened with an empty body")
        dialog.close()


def _exercise_overlay(report: Report) -> None:
    report.section("overlay")
    with report.step("overlay capture lifecycle"):
        overlay = OverlayWindow("selfcheck.exe")
        idle = overlay._pos_timer.isActive()
        overlay.set_capture_active(True)
        running = overlay._pos_timer.isActive() and overlay.isVisible()
        overlay.set_capture_active(False)
        stopped = not overlay._pos_timer.isActive() and not overlay.isVisible()
        report.fact("timers idle before capture", not idle)
        report.fact("shows and polls while capturing", running)
        report.fact("hides and stops timers on stop", stopped)
        if not stopped:
            report.suspect("overlay survives a stopped capture (the follow timer re-shows it)")
        overlay.shutdown()


def _shoot(report: Report, window: MainWindow, out_dir: str) -> None:
    """Save PNGs of the real window, one per theme and size.

    Everything is grabbed here rather than opportunistically mid-run, and the
    event loop is pumped before every grab. Grabbing straight after
    ``set_theme`` catches the restyle half-applied and produces a window with
    one theme's background under the other theme's text — which reads exactly
    like a theming bug that is not there.
    """
    report.section("screenshots")
    with report.step("grab"):
        from PyQt5.QtGui import QFontDatabase
        from PyQt5.QtWidgets import QApplication

        families = len(QFontDatabase().families())
        report.fact("qt platform", QApplication.platformName())
        report.fact("font families", families)
        if families < 10:
            report.suspect(
                "this Qt has almost no fonts, so text will grab blank — judge "
                "layout and colour from the PNGs, not the missing glyphs")

        shots = os.path.join(out_dir, _SHOT_DIR)
        os.makedirs(shots, exist_ok=True)
        started_on = theme.current_theme().name
        written = []
        try:
            for name in ("dark", "light"):
                theme.set_theme(name)
                _spin(_SETTLE_MS)
                current = theme.current_theme()
                report.fact(f"{name} palette",
                            f"bg={current.window_bg} accent={current.accent[0]}")
                for width, height in ((1280, 800), (1920, 1080)):
                    window.resize(width, height)
                    window._monitor_view.refresh_display_layout()
                    _spin(_SETTLE_MS)
                    path = os.path.join(shots, f"{name}-{width}x{height}.png")
                    window.grab().save(path)
                    written.append(path)
                    # View mixes checkable and plain rows; grab the open menu
                    # so an indent regression is visible. Size is independent
                    # of the window, so once per theme is enough.
                    if (width, height) == (1280, 800):
                        menu_path = os.path.join(shots, f"{name}-view-menu.png")
                        _grab_view_menu(window, menu_path)
                        written.append(menu_path)
        finally:
            theme.set_theme(started_on)

        for path in written:
            report.fact(os.path.basename(path), path)
        report.fact("note", "open all of these; they are the point of this area")
        report.fact("expected title", tr("window_title"))


def _grab_view_menu(window: MainWindow, path: str) -> None:
    """Popup View, grab the dropdown, then dismiss it."""
    view = next(
        action for action in window.menuBar().actions()
        if action.text().replace("&", "") == tr("menu_view")
    )
    menu = view.menu()
    geo = window.menuBar().actionGeometry(view)
    menu.popup(window.menuBar().mapToGlobal(geo.bottomLeft()))
    _spin(80)
    menu.grab().save(path)
    menu.hide()
    _spin(40)
