"""Shared motion helpers.

Qt stylesheets have no CSS transitions, so every bit of movement in the UI is
either a ``QPropertyAnimation`` on a widget property or a ``Transition`` driving
a plain 0..1 float that a custom ``paintEvent`` reads. Durations and easing live
here so the whole app moves at one speed.

This is a dense, high-frequency tool, so the motion budget is deliberately tiny:
micro-interactions only. No entrance animations for the window, charts, stats or
tables — someone opening this app several times a day should never wait on a
fade. Motion also never animates a layout property; it changes colour or opacity
while the layout snaps.

Animations turn themselves off under the ``offscreen`` platform (tests, headless
screenshots) so layout assertions see final geometry immediately.
"""

from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import (
    QAbstractAnimation, QEasingCurve, QPropertyAnimation, QVariantAnimation,
)
from PyQt5.QtWidgets import QApplication, QGraphicsOpacityEffect

# Durations (ms). Two speeds is all this app earns.
FAST = 90       # hover / press — must stay inside the ~100ms "reaction" window
NORMAL = 160    # a region appearing

# Entrances decelerate, exits accelerate and run shorter — symmetric motion
# reads as sluggish.
CURVE_ENTER = QEasingCurve.OutCubic
CURVE_EXIT = QEasingCurve.InCubic
_EXIT_RATIO = 0.75


def exit_duration(duration: int) -> int:
    """The matching exit duration for an entrance of *duration*."""
    return max(1, round(duration * _EXIT_RATIO))


_enabled = True


def set_enabled(value: bool) -> None:
    """Globally enable/disable animation (tests, low-spec or remote sessions)."""
    global _enabled
    _enabled = bool(value)


def enabled() -> bool:
    app = QApplication.instance()
    if app is None or app.platformName() == "offscreen":
        return False
    return _enabled


def animate(widget, prop: bytes, start, end, duration: int = NORMAL,
            curve: QEasingCurve = CURVE_ENTER) -> QPropertyAnimation | None:
    """Animate a Qt property of *widget*.

    Returns the running animation, or None when animation is off (in which case
    the property is set to *end* straight away). The animation is parented to the
    widget so Python does not collect it mid-flight.
    """
    if not enabled():
        widget.setProperty(prop.decode(), end)
        return None
    anim = QPropertyAnimation(widget, prop, widget)
    anim.setDuration(duration)
    anim.setEasingCurve(curve)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.start(QAbstractAnimation.DeleteWhenStopped)
    return anim


def fade_in(widget, duration: int = NORMAL) -> None:
    """Fade *widget* in without touching the layout.

    The widget must already be visible and laid out; only its opacity moves, so
    nothing around it shifts. Always ends fully opaque, including when animation
    is disabled or the animation is cut short.
    """
    if not enabled():
        widget.setGraphicsEffect(None)
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", effect)
    anim.setDuration(duration)
    anim.setEasingCurve(CURVE_ENTER)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    # Drop the effect afterwards: it forces the widget through an offscreen
    # pixmap on every repaint, which we do not want on a live chart panel.
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QAbstractAnimation.DeleteWhenStopped)


class Transition(QVariantAnimation):
    """Drives a 0..1 float and reports it to *on_tick* (for custom painting).

    Use this instead of restyling a widget per frame: re-parsing a stylesheet
    60 times a second is far more expensive than one repaint.
    """

    def __init__(self, parent, on_tick: Callable[[float], None],
                 duration: int = FAST):
        super().__init__(parent)
        self._on_tick = on_tick
        self._value = 0.0
        self._duration = duration
        self.valueChanged.connect(self._emit)

    def _emit(self, value) -> None:
        self._value = float(value)
        self._on_tick(self._value)

    @property
    def value(self) -> float:
        return self._value

    def to(self, target: float) -> None:
        """Animate from wherever we are now to *target*.

        Rising counts as an entrance and falling as an exit, so leaving a widget
        settles back faster than entering it did.
        """
        self.stop()
        target = float(target)
        if not enabled() or abs(target - self._value) < 0.001:
            self._value = target
            self._on_tick(target)
            return
        entering = target > self._value
        self.setDuration(self._duration if entering
                         else exit_duration(self._duration))
        self.setEasingCurve(CURVE_ENTER if entering else CURVE_EXIT)
        self.setStartValue(self._value)
        self.setEndValue(target)
        self.start()
