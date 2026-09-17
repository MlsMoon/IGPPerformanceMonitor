"""Live system-info rows inside the shared collapsible shell."""

from PyQt5.QtWidgets import QFrame

from src.ui.panels.collapsible_section import CollapsibleSection


class SystemInfoPanel(CollapsibleSection):
    """System metric rows in :class:`CollapsibleSection`. Default expanded."""

    def __init__(self, bar: QFrame, parent=None):
        super().__init__("system_info_panel", parent, name="SystemInfo", stacked=True)
        self._bar = bar
        self.set_body(bar)
