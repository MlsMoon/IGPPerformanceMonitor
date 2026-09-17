"""Test: theme — Theme fields, palette, QSS generators, toggle exists."""

from src.ui import theme as th
from src.ui.dpi import configure_high_dpi


def run():
    t = th.current_theme()
    assert t is not None, "theme not None"

    # Core fields
    for attr in ("text_primary", "text_muted", "window_bg", "panel_bg",
                 "card_bg", "border", "accent", "selection", "selection_text"):
        assert hasattr(t, attr), f"theme missing {attr}"

    # Palette
    pal = th.palette()
    assert isinstance(pal, list) and len(pal) > 0, "palette empty"

    # QSS generators non-empty
    for name, fn in (
        ("app_qss", th.app_qss),
        ("card_qss", th.card_qss),
        ("system_bar_qss", th.system_bar_qss),
        ("monitored_label_qss", th.monitored_label_qss),
        ("muted_placeholder_qss", th.muted_placeholder_qss),
        ("panel_button_qss", lambda t: th.panel_button_qss(t, "primary")),
    ):
        qss = fn(t)
        assert isinstance(qss, str) and len(qss) > 0, f"{name} empty"

    # Toggle/set exist
    assert callable(th.toggle_theme), "toggle_theme callable"
    assert callable(th.set_theme), "set_theme callable"
    assert isinstance(configure_high_dpi(), bool), "dpi helper returns bool"
