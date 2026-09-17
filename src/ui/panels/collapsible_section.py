"""Shared expand/collapse chrome. Chevron + title stay; only the body hides."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from src.i18n import tr
from src.ui import motion
from src.ui.theme import RADIUS_SURFACE, current_theme


class CollapsibleSection(QWidget):
    """The only expand/collapse shell for live panels.

    Subclasses put domain widgets in :meth:`set_body`. Do not copy another
    chevron header. Collapse hides the body; the header must stay on screen.
    A custom ``heightForWidth`` that returns ``-1`` or ``0`` makes the whole
    block vanish — this class always floors height at the header.
    """

    expanded_changed = pyqtSignal(bool)

    def __init__(self, title_key: str, parent=None, *, name: str,
                 stacked: bool = True):
        super().__init__(parent)
        self._title_key = title_key
        self._name = name
        self._stacked = stacked
        self._body: QWidget | None = None
        self._expanded = False
        self.setObjectName(f"{name}Panel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        if stacked:
            root = QVBoxLayout(self)
            root.setSpacing(2)
        else:
            root = QHBoxLayout(self)
            root.setSpacing(8)
        root.setContentsMargins(8, 4, 8, 4)
        self._root = root

        header = QHBoxLayout() if stacked else root
        if stacked:
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(8)

        align = Qt.AlignVCenter if stacked else Qt.AlignTop
        self._toggle = QToolButton()
        self._toggle.setObjectName(f"{name}Toggle")
        self._toggle.setAutoRaise(True)
        self._toggle.setToolTip(tr(title_key))
        self._toggle.clicked.connect(self.toggle_expanded)
        header.addWidget(self._toggle, 0, align)

        self._title = QLabel(tr(title_key))
        self._title.setObjectName(f"{name}Title")
        header.addWidget(self._title, 0, align)
        if stacked:
            header.addStretch()
            root.addLayout(header)

        self.apply_theme()

    def set_body(self, body: QWidget):
        if self._body is not None:
            self._root.removeWidget(self._body)
        self._body = body
        body.setParent(self)
        self._root.addWidget(body, 1 if not self._stacked else 0)
        # Force the first expand even if someone called set_expanded early.
        self._expanded = False
        self.set_expanded(True)

    def toggle_expanded(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool):
        expanded = bool(expanded)
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self._toggle.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)
        if self._body is not None:
            self._body.setVisible(expanded)
            if expanded and self.isVisible():
                motion.fade_in(self._body, motion.NORMAL)
        self.updateGeometry()
        self.expanded_changed.emit(self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        """Header always counts. Never return -1 / 0 (that hides the chrome)."""
        m = self._root.contentsMargins()
        header_h = max(
            self._toggle.sizeHint().height(),
            self._title.sizeHint().height(),
            1,
        )
        total = header_h + m.top() + m.bottom()
        body = self._body
        if not self._expanded or body is None or body.isHidden():
            return total
        inner_w = max(0, width - m.left() - m.right())
        if self._stacked:
            body_w = inner_w
        else:
            used = (
                self._toggle.sizeHint().width()
                + self._title.sizeHint().width()
                + 2 * self._root.spacing()
            )
            body_w = max(0, inner_w - used)
        if body.hasHeightForWidth():
            body_h = max(0, body.heightForWidth(body_w))
        else:
            body_h = max(0, body.sizeHint().height())
        if self._stacked:
            return total + self._root.spacing() + body_h
        return max(total, body_h + m.top() + m.bottom())

    def sizeHint(self):
        hint = super().sizeHint()
        floor = self.heightForWidth(max(hint.width(), 200))
        if hint.height() < floor:
            hint.setHeight(floor)
        return hint

    def apply_theme(self, t=None):
        t = t or current_theme()
        self.setStyleSheet(self._shell_qss(t) + self._extra_qss(t))
        self._title.setStyleSheet(
            f"color: {t.text_primary}; font-weight: 600; font-size: 9pt;")

    def _shell_qss(self, t) -> str:
        panel = f"{self._name}Panel"
        toggle = f"{self._name}Toggle"
        return (
            f"QWidget#{panel} {{ background-color: {t.panel_bg};"
            f" border: none; border-radius: {RADIUS_SURFACE}px; }}"
            f"QToolButton#{toggle} {{ background: transparent; border: none;"
            f" color: {t.text_secondary}; padding: 1px; }}"
        )

    def _extra_qss(self, t) -> str:
        return ""
