"""Test: ui_process_panel — ProcessPanel offscreen construction + search + state."""

from src.ui.panels.process_panel import ProcessPanel
from src.i18n import tr


def run():
    pp = ProcessPanel()
    assert pp is not None, "ProcessPanel construction"

    # Public API
    assert isinstance(pp.get_process_names(), list)
    assert isinstance(pp.has_processes(), bool)
    assert isinstance(pp.get_timed_seconds(), int)

    # set_capture_state over both extremes; the single toggle button shows the
    # action it will perform ("Start" when idle, "Stop" when capturing).
    pp.set_capture_state(True)
    assert pp._capture_btn.text() == tr("btn_stop")
    pp.set_capture_state(False)
    assert pp._capture_btn.text() == tr("btn_start")

    # Search bar input + apply (debounced timer — _apply_search directly)
    pp._search_input.setText("svchost")
    pp._apply_search()
