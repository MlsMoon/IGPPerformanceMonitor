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
from src.core.data_store import DataStore
from src.i18n import tr
from src.models import SystemSnapshot
from src.selfcheck import data
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
        "src/core/app_config.py",
        "assets/",
        "docs/",
    ),
)
from src.ui import motion, theme, win_chrome
from src.ui.chart_base import SystemChip
from src.ui.main_window import MainWindow
from src.ui.views.overlay_window import OverlayWindow

_SHOT_DIR = "shots"

# Long enough for a restyle, a relayout and any motion to finish before a grab.
_SETTLE_MS = 400


def _spin(ms: int) -> None:
    """Pump the event loop for *ms* so timers and animations actually run."""
    from PyQt5.QtCore import QElapsedTimer
    from PyQt5.QtWidgets import QApplication

    clock = QElapsedTimer()
    clock.start()
    while clock.elapsed() < ms:
        QApplication.processEvents()


def run(report: Report, out_dir: str, **_kwargs) -> None:
    frames = data.load_frames_if_available()
    apps = sorted({f.application for f in frames if f.application})

    report.section("input")
    report.fact("real frames", len(frames))
    report.fact("apps in capture", ", ".join(apps) or "(none)")
    if not frames:
        report.suspect(
            "no real capture available, so charts and stats render empty — "
            "layout facts below are still meaningful, data ones are not")

    window = MainWindow()
    span = _seed(window, frames, apps)
    report.fact("replayed timeline seconds", f"{span:.1f}" if span else "(none)")

    _describe_window(report, window)
    _describe_chips(report, window)
    _exercise_panels(report, window)
    _exercise_charts(report, window)
    _exercise_qss(report)
    _exercise_docs(report, window)
    _exercise_overlay(report)
    _shoot(report, window, out_dir)
    _report_qt_messages(report)


def _seed(window: MainWindow, frames, apps) -> float:
    """Push the real capture into the window's own store.

    It has to be *this* store: the screenshots are of this window, and feeding
    a throwaway MonitorView instead produced reports describing populated
    charts next to PNGs of an empty app.

    ``add_frame`` stamps history with wall-clock elapsed. Dumping a thousand
    frames in a tight loop therefore draws a single spike at t=0. After the
    dump we rewrite the histories from PresentMon's own ``time_in_seconds``
    so the charts show the session that was actually captured.
    """
    store: DataStore = window._data_store
    store.start_session()
    try:
        store.set_system_info(data.load_real_system_info())
    except Exception:
        pass
    for frame in frames:
        store.add_frame(frame)
    store.set_monitored_apps(apps)
    span = _replay_timeline(store, frames)
    view = window._monitor_view
    view._refresh_charts()
    view._refresh_stats()
    if span > 0 and hasattr(view, "_set_chart_xrange"):
        view._set_chart_xrange(list(view._plots.values()), max(span, 10.0))
    return span


def _replay_timeline(store: DataStore, frames) -> float:
    """Rebuild chart histories on PresentMon's timeline. Returns span in seconds."""
    # time_in_seconds is not an export column (imported frames are all 0).
    # Walk each app's frames in file order and accumulate MsBetweenPresents —
    # that is the clock FPS is already computed from.
    from collections import defaultdict

    by_app: dict[str, list] = defaultdict(list)
    for frame in frames:
        by_app[frame.application or f"pid_{frame.process_id}"].append(frame)
    if not by_app:
        return 0.0

    histories = (
        store._fps_history, store._cpu_history, store._mem_history,
        store._gpu_history, store._cpu_cores_history, store._app_vram_history,
    )
    for hist in histories:
        hist.clear()

    last_snap = -1.0
    span = 0.0
    for key, group in by_app.items():
        elapsed = 0.0
        for frame in group:
            elapsed += (frame.ms_between_presents or 0.0) / 1000.0
            if elapsed > span:
                span = elapsed
            if frame.fps is not None and frame.fps > 0:
                store._fps_history[key].append((elapsed, frame.fps))
            if frame.app_cpu_percent is not None:
                store._cpu_history[key].append((elapsed, frame.app_cpu_percent))
            if frame.app_cpu_cores is not None:
                store._cpu_cores_history[key].append((elapsed, frame.app_cpu_cores))
            if frame.app_vram_mb is not None:
                store._app_vram_history[key].append((elapsed, frame.app_vram_mb))
            if frame.app_memory_mb is not None:
                store._mem_history[key].append((elapsed, frame.app_memory_mb))
            if frame.app_gpu_percent is not None:
                store._gpu_history[key].append((elapsed, frame.app_gpu_percent))
            if elapsed - last_snap >= 0.5:
                store.add_system_snapshot(SystemSnapshot(
                    timestamp=elapsed,
                    total_cpu_percent=frame.total_cpu_percent,
                    total_gpu_percent=frame.total_gpu_percent,
                    total_ram_used_gb=frame.total_ram_used_gb,
                    vram_total_mb=frame.gpu_vram_total_mb,
                    vram_used_mb=frame.gpu_vram_used_mb,
                    vram_percent=frame.gpu_vram_percent,
                ))
                last_snap = elapsed
    for hist in histories:
        for key, points in hist.items():
            points.sort(key=lambda pair: pair[0])
    return span


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
        PAGE_FILES, docs_root, load_page, locale_folder, page_path,
        resolve_doc_href,
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
        finally:
            theme.set_theme(started_on)

        for path in written:
            report.fact(os.path.basename(path), path)
        report.fact("note", "open all of these; they are the point of this area")
        report.fact("expected title", tr("window_title"))
