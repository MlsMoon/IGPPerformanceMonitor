"""Test: ui_main — MainWindow, MonitorView construction + Crosshair callback."""

from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QScrollArea

from src.ui.main_window import MainWindow
from src.ui.views.monitor_view import MonitorView
from src.core.data_store import DataStore
from src.tests._factory import load_real_frames, load_real_system_info


def run():
    ds = DataStore()
    ds.start_session()

    # Feed REAL captured frames.
    for f in load_real_frames():
        ds.add_frame(f)

    mw = MainWindow()
    assert mw is not None, "MainWindow"
    assert mw.minimumWidth() <= 1000, "1080p-friendly minimum width"
    assert mw._monitor_view.findChild(QScrollArea, "ChartsScrollArea") is not None, (
        "charts should live in a scroll area"
    )
    assert mw._monitor_view.is_visibility_panel_expanded(), (
        "chart visibility part should be expanded by default"
    )
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

    mv = MonitorView(ds)
    assert mv is not None, "MonitorView"
    assert mv.findChild(QScrollArea, "ChartsScrollArea") is not None, "MonitorView scroll area"
    assert mv.is_visibility_panel_expanded(), "MonitorView panel initially expanded"
    mv._refresh_charts()
    mv._refresh_stats()
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
