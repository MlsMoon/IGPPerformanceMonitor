"""Test: i18n — every key exists in both locales; tr() returns the translation.

Full-key coverage (both locales) instead of a cherry-picked subset — catches
"added a key to en but forgot zh_CN" and any key that falls back to its own name.
"""

from src.i18n import tr, set_locale
from src.i18n.en import TRANSLATIONS as EN
from src.i18n.zh_CN import TRANSLATIONS as ZH_CN


def run():
    # Both locales must define the exact same key set.
    assert set(EN) == set(ZH_CN), (
        f"locale key mismatch: EN-only={set(EN) - set(ZH_CN)}, "
        f"ZH-only={set(ZH_CN) - set(EN)}"
    )

    for loc, table in (("en", EN), ("zh_CN", ZH_CN)):
        set_locale(loc)
        for key, expected in table.items():
            val = tr(key)
            assert val == expected, f"tr({key!r}) != table in {loc}"
            assert val and len(val) > 0, f"empty translation for {key!r} in {loc}"
            assert key not in val, f"tr({key!r}) returned the key itself in {loc}"
