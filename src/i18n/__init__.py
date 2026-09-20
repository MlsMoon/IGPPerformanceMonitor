"""I18n package — locale detection + translation lookup from JSON catalogs.

UI copy lives in ``src/i18n/locales/<locale>.json``, not in Python. Dropping a
new file there is enough to add a locale; ``tr()`` stays the only lookup API.
"""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path


def locales_dir() -> Path:
    """Directory of ``*.json`` catalogs (dev package dir, or the frozen copy)."""
    here = Path(__file__).resolve().parent / "locales"
    if here.is_dir():
        return here
    from src.core.app_info import resource_root
    return resource_root() / "src" / "i18n" / "locales"


def _load_file(path: Path) -> tuple[str, dict[str, str]] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    native = data.get("native_name")
    strings = data.get("strings")
    if not isinstance(native, str) or not native:
        return None
    if not isinstance(strings, dict):
        return None
    cleaned: dict[str, str] = {}
    for key, value in strings.items():
        if isinstance(key, str) and isinstance(value, str) and key and value:
            cleaned[key] = value
    if not cleaned:
        return None
    return native, cleaned


def _discover() -> tuple[tuple[str, ...], dict[str, str], dict[str, dict[str, str]]]:
    folder = locales_dir()
    natives: dict[str, str] = {}
    tables: dict[str, dict[str, str]] = {}
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            loaded = _load_file(path)
            if loaded is None:
                continue
            code = path.stem
            natives[code], tables[code] = loaded
    codes = list(tables)
    if "en" in codes:
        codes.remove("en")
        codes.insert(0, "en")
    return tuple(codes), natives, tables


UI_LOCALES, LOCALE_NATIVE_NAMES, _TRANSLATIONS = _discover()

_FALLBACK: dict[str, str] = _TRANSLATIONS.get("en") or (
    _TRANSLATIONS[UI_LOCALES[0]] if UI_LOCALES else {}
)


class I18n:
    """Translation controller. Detects locale, provides tr()."""

    def __init__(self):
        self._locale: str | None = None

    @property
    def locale(self) -> str:
        if self._locale is None:
            self._locale = self._detect()
        return self._locale

    def set_locale(self, loc: str):
        self._locale = loc

    def tr(self, key: str, *args) -> str:
        """Translate key to current locale. Format with optional args."""
        table = _TRANSLATIONS.get(self.locale, _FALLBACK)
        text = table.get(key)
        if text is None:
            text = _FALLBACK.get(key, key)
        if args:
            return text.format(*args)
        return text

    @staticmethod
    def _detect() -> str:
        env_lang = os.environ.get("IGP_LANG", "")
        if env_lang:
            return env_lang
        try:
            from src.core import app_config
            saved = app_config.get("locale")
            if saved in _TRANSLATIONS:
                return saved
        except Exception:
            pass
        try:
            loc = locale.getdefaultlocale()
            if loc and loc[0]:
                if loc[0].startswith("zh") and "zh_CN" in _TRANSLATIONS:
                    return "zh_CN"
        except Exception:
            pass
        return "en" if "en" in _TRANSLATIONS else (UI_LOCALES[0] if UI_LOCALES else "en")


_instance = I18n()


def catalogs() -> dict[str, dict[str, str]]:
    """locale code → string table (the JSON ``strings`` object)."""
    return {code: dict(table) for code, table in _TRANSLATIONS.items()}


def bilingual(key: str) -> str:
    """Join unique translations of *key* across catalogs with `` / ``.

    Used by the first-run picker, which must not call ``tr()`` (that would
    pick a locale before the user has chosen one).
    """
    seen: list[str] = []
    for code in UI_LOCALES:
        text = _TRANSLATIONS.get(code, {}).get(key, "")
        if text and text not in seen:
            seen.append(text)
    return " / ".join(seen) if seen else key


def tr(key: str, *args) -> str:
    """Shorthand for the global I18n instance."""
    return _instance.tr(key, *args)


def get_locale() -> str:
    return _instance.locale


def set_locale(loc: str):
    _instance.set_locale(loc)
