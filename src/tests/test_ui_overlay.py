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

    # Capture state drives the overlay. The position timer re-shows the window
    # every 33ms, so stopping must stop the timers — hiding alone bounced back.
    ow = OverlayWindow("t-state")
    assert not ow._pos_timer.isActive(), "timers idle before any capture"
    ow.set_capture_active(True)
    assert ow._pos_timer.isActive() and ow._display_timer.isActive(), "timers run"
    assert ow.isVisible(), "an active capture shows its overlay"
    ow.set_capture_active(False)
    assert not ow._pos_timer.isActive(), "a stopped capture stops the position timer"
    assert not ow._display_timer.isActive(), "and the display timer"
    assert not ow.isVisible(), "a stopped capture hides its overlay"
    # The timer tick is what used to undo hide(), so it must short-circuit. A
    # running overlay would re-resolve this bogus handle and leave it None.
    ow._pid = 4242
    ow._tracked_hwnd = -1
    ow._update_position()
    assert ow._tracked_hwnd == -1, "an inactive overlay must not chase its window"
    assert not ow.isVisible(), "the position timer must not resurrect the overlay"

    # F9 while stopped must not bring it back either.
    ow.set_suppressed(False)
    assert not ow.isVisible(), "un-suppressing a stopped overlay keeps it hidden"

    # F9 while running should, though.
    ow.set_capture_active(True)
    ow.set_suppressed(True)
    assert not ow.isVisible(), "F9 hides a running overlay"
    ow.set_suppressed(False)
    assert ow.isVisible(), "F9 again restores a running overlay"
    ow.shutdown()
