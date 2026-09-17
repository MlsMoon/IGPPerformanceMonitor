"""Test: ui_overlay — OverlayWindow per-app construction + update_frame (real frames)."""

from PyQt5.QtCore import Qt

from src.ui.views.overlay_window import OverlayWindow
from src.tests._factory import load_real_frames_by_app


def run():
    for name, frames in load_real_frames_by_app().items():
        ow = OverlayWindow(name)
        ow.update_frame(frames[0])
        ow._refresh_display()
        assert ow is not None, f"OverlayWindow {name}"

    # Tier 0: click-through toggle + master-suppress flag.
    ow = OverlayWindow("t-app")
    ow.set_click_through(True)
    assert ow.testAttribute(Qt.WA_TransparentForMouseEvents), "click-through enabled"
    ow.set_click_through(False)
    assert not ow.testAttribute(Qt.WA_TransparentForMouseEvents), "click-through disabled"
    ow.set_suppressed(True)
    assert ow._suppressed, "suppressed flag set"
