"""Qt high-DPI setup helpers.

These attributes must be set before the first QApplication is created.  Keeping
the logic in one helper lets the GUI entry point, admin dialog path, and tests
share the same startup behavior.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication


def configure_high_dpi() -> bool:
    """Enable Qt high-DPI handling before QApplication construction.

    Returns True when attributes were applied, False when a QApplication already
    exists and Qt can no longer accept process-wide DPI attributes.
    """
    if QApplication.instance() is not None:
        return False

    for attr_name in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        attr = getattr(Qt, attr_name, None)
        if attr is not None:
            QApplication.setAttribute(attr, True)
    return True
