"""Test: i18n — every key exists in every JSON locale; tr() returns the translation.

Full-key coverage instead of a cherry-picked subset — catches "added a key to
en.json but forgot zh_CN.json" and any key that falls back to its own name.
"""

from src.i18n import (
    LOCALE_NATIVE_NAMES, UI_LOCALES, bilingual, catalogs, set_locale, tr,
)


def run():
    tables = catalogs()
    assert tables, "no locale JSON catalogs loaded from src/i18n/locales/"
    assert "en" in tables, "English catalog (en.json) is required as the fallback"
    assert UI_LOCALES and UI_LOCALES[0] == "en"
    assert set(UI_LOCALES) == set(tables)
    for loc in UI_LOCALES:
        name = LOCALE_NATIVE_NAMES.get(loc, "")
        assert isinstance(name, str) and name.strip(), f"missing native_name for {loc}"

    keysets = {loc: set(table) for loc, table in tables.items()}
    reference = keysets["en"]
    for loc, keys in keysets.items():
        assert keys == reference, (
            f"locale key mismatch vs en: {loc}-only={keys - reference}, "
            f"en-only={reference - keys}"
        )

    for loc, table in tables.items():
        set_locale(loc)
        for key, expected in table.items():
            val = tr(key)
            assert val == expected, f"tr({key!r}) != table in {loc}"
            assert val and len(val) > 0, f"empty translation for {key!r} in {loc}"
            assert key not in val, f"tr({key!r}) returned the key itself in {loc}"

    title = bilingual("language_picker_title")
    assert " / " in title or len(tables) == 1, (
        "first-run picker title should join every locale catalog"
    )
    assert "language_picker_title" not in title
