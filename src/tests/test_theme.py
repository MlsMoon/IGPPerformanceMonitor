"""Test: theme — Theme fields, palette, QSS generators, toggle exists."""

from src.ui import theme as th
from src.ui.dpi import configure_high_dpi


def run():
    t = th.current_theme()
    assert t is not None, "theme not None"

    # Core fields
    for attr in ("text_primary", "text_muted", "window_bg", "panel_bg",
                 "card_bg", "border", "accent", "selection", "selection_text",
                 "hover_bg", "input_bg"):
        assert hasattr(t, attr), f"theme missing {attr}"

    # Flat design: surfaces are separated by contrast, never by drop shadows.
    assert not hasattr(th, "apply_shadow"), "shadows were removed from the theme"
    for theme_preset in (th.DARK, th.LIGHT):
        assert theme_preset.plot_bg == theme_preset.card_bg, (
            "the plot must sit flush in its card, not look inset"
        )

    # Shared radius scale (QSS and custom painters must agree). The ceiling is
    # the point of the scale: this is a dense tool UI, where anything above ~6px
    # starts reading as soft rather than precise.
    for name in ("RADIUS_SURFACE", "RADIUS_CARD", "RADIUS_CONTROL", "RADIUS_CHIP"):
        value = getattr(th, name)
        assert isinstance(value, int), f"{name} missing"
        assert 0 <= value <= 6, f"{name}={value} is too round for a tool UI"
    assert th.RADIUS_CHIP <= th.RADIUS_CONTROL <= th.RADIUS_CARD, (
        "smaller elements must not be rounder than the surfaces holding them"
    )

    # Colour blending drives the animated hover fill
    assert th.lerp_color("#000000", "#ffffff", 0.0).name() == "#000000", "lerp start"
    assert th.lerp_color("#000000", "#ffffff", 1.0).name() == "#ffffff", "lerp end"
    assert th.lerp_color("#000000", "#ffffff", 0.5).red() == 128, "lerp midpoint"
    assert th.lerp_color("#000000", "#ffffff", 5.0).name() == "#ffffff", "lerp clamps"

    # Palette
    pal = th.palette()
    assert isinstance(pal, list) and len(pal) > 0, "palette empty"

    # QSS generators non-empty
    for name, fn in (
        ("app_qss", th.app_qss),
        ("card_qss", th.card_qss),
        ("stats_list_qss", th.stats_list_qss),
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
