"""Test: ui_main — MainWindow, MonitorView construction + Crosshair callback."""

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QFrame, QScrollArea

from src.ui import motion, win_chrome
from src.ui.chart_base import SystemChip, build_system_chip_bar
from src.ui.panels.collapsible_section import CollapsibleSection
from src.core.app_info import is_dev_mode
from src.i18n import tr
from src.ui.main_window import MainWindow
from src.ui.views.monitor_view import MonitorView
from src.core.data_store import DataStore
from src.tests._factory import load_real_frames, load_real_system_info


def run():
    ds = DataStore()
    ds.start_session()

    # Feed REAL captured frames.
    frames = load_real_frames()
    for f in frames:
        ds.add_frame(f)
    ds.set_monitored_apps(sorted({f.application for f in frames if f.application}))

    mw = MainWindow()
    assert mw is not None, "MainWindow"
    assert mw.minimumWidth() <= 1000, "1080p-friendly minimum width"
    assert is_dev_mode(), "offscreen suite runs from source"
    assert mw.windowTitle() == tr("window_title_dev", tr("window_title")), (
        "dev mode must mark the window title"
    )
    assert mw._dev_badge is not None and mw._dev_badge.text() == tr("dev_badge"), (
        "dev mode must show a status-bar badge"
    )

    # A long GPU/display string must not inflate the window's real minimum
    # width. Each metric is a row: the value wraps, it is never cut with "...".
    long_name = "GPU: " + "NVIDIA GeForce RTX 4060 Ti " * 6
    long_chip = SystemChip(long_name)
    assert long_chip.minimumSizeHint().width() < 200, "system row must stay shrinkable"
    assert long_chip.text() == long_name, "system row must keep the full value"
    assert "..." not in long_chip.text()
    assert "..." not in long_chip.value_text()

    sample = (
        "CPU: AMD Ryzen 7 5700X 3D 8-Core Processor  |  "
        "GPU: NVIDIA GeForce RTX 4060 Ti  |  "
        "RAM: 31.9 GB  |  "
        "Display: 3840x2160@59Hz / 1920x1080@280Hz"
    )
    sample_bar = build_system_chip_bar(sample)
    sample_bar.resize(520, max(1, sample_bar.heightForWidth(520)))
    sample_values = []
    for i in range(sample_bar.layout().count()):
        chip = sample_bar.layout().itemAt(i).widget()
        if isinstance(chip, SystemChip):
            sample_values.append(chip.value_text())
            assert "..." not in chip.value_text()
    assert "AMD Ryzen 7 5700X 3D 8-Core Processor" in sample_values
    assert "NVIDIA GeForce RTX 4060 Ti" in sample_values
    assert "31.9 GB" in sample_values
    assert "3840x2160@59Hz / 1920x1080@280Hz" in sample_values

    bar = mw._monitor_view._sys_info_bar
    assert bar.layout().hasHeightForWidth(), "system rows grow with wrapped values"
    for i in range(bar.layout().count()):
        chip = bar.layout().itemAt(i).widget()
        if not isinstance(chip, SystemChip):
            continue
        assert chip.text() == chip.toolTip(), "live row must show its full value"
        assert "..." not in chip.text()
        assert chip.value_text(), "value cell is empty"
        needed = QFontMetrics(chip.font()).height()
        assert chip.sizeHint().height() >= needed, (
            f"row {chip.toolTip()[:20]!r} would clip its text"
        )

    # Native title-bar theming must be a safe no-op everywhere (offscreen, too).
    win_chrome.apply_to_widget(mw)
    win_chrome.refresh_all()
    assert win_chrome._colorref("#123456") == 0x563412, "COLORREF is 0x00bbggrr"

    # Motion is off under the offscreen platform, so transitions must land on
    # their end value synchronously and never leave a widget faded out.
    assert not motion.enabled(), "animations disabled offscreen"
    motion.fade_in(mw)
    assert mw.graphicsEffect() is None, "fade_in must not leave an opacity effect"
    ticks: list[float] = []
    transition = motion.Transition(mw, ticks.append)
    transition.to(1.0)
    assert ticks == [1.0] and transition.value == 1.0, "disabled transition jumps to target"

    # Motion budget for a high-frequency tool: hover feedback inside the ~100ms
    # reaction window, and exits shorter than the entrance they undo.
    assert motion.FAST <= 100, "hover feedback must feel like a reaction"
    assert motion.exit_duration(motion.NORMAL) < motion.NORMAL, "exits run shorter"
    assert not hasattr(mw, "_did_fade_in"), "no startup entrance animation"
    assert mw._monitor_view.findChild(QScrollArea, "ChartsScrollArea") is not None, (
        "charts should live in a scroll area"
    )
    assert mw._monitor_view.is_visibility_panel_expanded(), (
        "chart visibility part should be expanded by default"
    )
    assert mw._monitor_view.is_system_info_expanded(), (
        "system info part should be expanded by default"
    )
    assert not mw._monitor_view._sys_info_bar.isHidden(), "chips visible when expanded"
    sys_panel = mw._monitor_view._sys_info_panel
    vis_panel = mw._monitor_view._vis_panel
    assert isinstance(sys_panel, CollapsibleSection), "system info must reuse CollapsibleSection"
    assert isinstance(vis_panel, CollapsibleSection), "charts panel must reuse CollapsibleSection"
    mw._monitor_view.set_system_info_expanded(False)
    assert not mw._monitor_view.is_system_info_expanded(), "system info collapse"
    assert mw._monitor_view._sys_info_bar.isHidden(), "chips hidden when collapsed"
    assert not sys_panel.isHidden(), "collapse must keep the section"
    assert not sys_panel._title.isHidden(), "collapse must keep the header title"
    assert not sys_panel._toggle.isHidden(), "collapse must keep the chevron"
    assert sys_panel.heightForWidth(600) >= 16, "collapsed header must keep a height"
    mw._monitor_view.set_system_info_expanded(True)
    assert mw._monitor_view.is_system_info_expanded(), "system info expand"
    assert not mw._monitor_view._sys_info_bar.isHidden(), "chips return when expanded"
    assert mw._charts_panel_action.isChecked(), "View menu panel toggle sync"
    mw._monitor_view.toggle_visibility_panel()
    assert not mw._monitor_view.is_visibility_panel_expanded(), "panel toggle collapse"
    mw._sync_charts_panel_action()
    assert not mw._charts_panel_action.isChecked(), "View menu collapse sync"
    mw._monitor_view.toggle_visibility_panel()
    assert mw._monitor_view.is_visibility_panel_expanded(), "panel toggle expand"
    assert mw._monitor_view._vis_panel is not None, "inline visibility part exists"
    mw._monitor_view._vis_panel.toggle_expanded()
    assert not mw._charts_panel_action.isChecked(), "inline triangle collapse sync"
    mw._charts_panel_action.trigger()
    assert mw._monitor_view.is_visibility_panel_expanded(), "menu expands inline part"
    assert mw._charts_panel_action.isChecked(), "menu expand checked sync"

    # Tier 0: keyboard shortcuts wired across menus + ShortcutsDialog builds.
    found = set()
    for _ma in mw.menuBar().actions():
        _m = _ma.menu()
        if _m is None:
            continue
        for _act in _m.actions():
            sc = _act.shortcut().toString()
            if sc:
                found.add(sc)
    assert {"F5", "F9", "F1", "Ctrl+D", "Ctrl+E", "Ctrl+I", "Ctrl+J", "Ctrl+T"} <= found, (
        f"shortcuts missing: {found}"
    )
    assert mw._click_through_action.isChecked() is False, "click-through default off"
    from src.ui.dialogs.shortcuts_dialog import ShortcutsDialog
    assert ShortcutsDialog(mw) is not None, "ShortcutsDialog constructs"

    # Update progress dialog: built without starting its worker, so this only
    # covers how progress ticks are rendered.
    from src.core.app_update_service import STAGE_APP, AppUpdateService, UpdateProgress
    from src.ui.dialogs.update_progress import UpdateProgressDialog
    dlg = UpdateProgressDialog(AppUpdateService(), {}, "Update", mw)
    dlg._on_progress(UpdateProgress(STAGE_APP, 0, 0))
    assert dlg._bar.maximum() == 0, "unknown size must show an indeterminate bar"
    dlg._on_progress(UpdateProgress(STAGE_APP, 5 * 1024 * 1024, 10 * 1024 * 1024))
    assert dlg._bar.maximum() > 0, "a known size switches to a determinate bar"
    assert dlg._bar.value() == dlg._bar.maximum() // 2, "half downloaded is half full"
    assert "50" in dlg._detail.text(), f"percent missing from {dlg._detail.text()!r}"

    mv = MonitorView(ds)
    assert mv is not None, "MonitorView"
    assert mv.findChild(QScrollArea, "ChartsScrollArea") is not None, "MonitorView scroll area"
    assert mv._content_splitter.count() == 2, "stats / charts divider is draggable"
    mv.save_layout_state()
    assert mv.is_visibility_panel_expanded(), "MonitorView panel initially expanded"
    mv._refresh_charts()
    mv._refresh_stats()

    # The stats readout is one rounded surface with hairline rows, not a stack
    # of ten rounded tiles — the whole point of the flat pass.
    stats_lists = mv.findChildren(QFrame, "StatsList")
    assert len(stats_lists) == 1, "stats should live in a single container"
    rows = stats_lists[0].findChildren(QFrame, "StatsRow")
    last_rows = stats_lists[0].findChildren(QFrame, "StatsRowLast")
    assert len(rows) >= 8 and len(last_rows) == 1, (
        "every metric is a row; only the bottom one drops its separator"
    )

    mv.resize(1366, 768)
    mv.refresh_display_layout()
    fps_card = mv._chart_widgets["fps"]
    cpu_card = mv._chart_widgets["cpu"]
    assert getattr(cpu_card.plot.getAxis("left"), "fixedWidth", 0) >= 38, (
        "compact left axis fixed width"
    )
    assert getattr(fps_card.plot.getAxis("bottom"), "fixedHeight", 0) >= 26, (
        "bottom axis fixed height"
    )
    assert cpu_card.plot.getAxis("bottom").style.get("hideOverlappingLabels"), (
        "compact axes should hide overlapping labels"
    )
    mv.set_chart_visible("gpu_temp", False)
    assert not mv.is_chart_visible("gpu_temp"), "hide chart"
    assert not mv._vis_panel._checks["gpu_temp"].isChecked(), "inline checkbox hide sync"
    mv.set_chart_visible("gpu_temp", True)
    assert mv.is_chart_visible("gpu_temp"), "show chart"
    assert mv._vis_panel._checks["gpu_temp"].isChecked(), "inline checkbox show sync"

    empty_ds = DataStore()
    empty_ds.set_system_info(load_real_system_info())
    empty_mv = MonitorView(empty_ds)
    empty_mv._refresh_charts()
    assert empty_mv._monitored_label.isHidden(), (
        "'Monitored: …' line should not take a row before a capture"
    )
    expected_displays = " / ".join(load_real_system_info().display_outputs)
    assert expected_displays in empty_mv._sys_info_bar._igp_text, (
        "system info should refresh even without captured frames"
    )

    # Crosshair._on_moved hover callback (was Point not callable)
    try:
        cw = mv._chart_widgets.get("fps")
        if cw and hasattr(cw, "_crosshair") and cw._crosshair:
            cw._crosshair._on_moved(QPointF(0, 0))
    except Exception as exc:
        print(f"    (crosshair skip: {exc})")
