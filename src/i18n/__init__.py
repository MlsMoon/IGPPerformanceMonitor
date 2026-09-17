"""I18n package — locale detection + translation lookup."""

import locale
import os

from src.i18n.en import TRANSLATIONS as _EN
from src.i18n.zh_CN import TRANSLATIONS as _ZH_CN

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": _EN,
    "zh_CN": _ZH_CN,
}


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
        text = _TRANSLATIONS.get(self.locale, _EN).get(key)
        if text is None:
            text = _EN.get(key, key)
        if args:
            return text.format(*args)
        return text

    @staticmethod
    def _detect() -> str:
        env_lang = os.environ.get("IGP_LANG", "")
        if env_lang:
            return env_lang
        try:
            loc = locale.getdefaultlocale()
            if loc and loc[0]:
                if loc[0].startswith("zh"):
                    return "zh_CN"
        except Exception:
            pass
        return "en"


_instance = I18n()


def tr(key: str, *args) -> str:
    """Shorthand for the global I18n instance."""
    return _instance.tr(key, *args)


def get_locale() -> str:
    return _instance.locale


def set_locale(loc: str):
    _instance.set_locale(loc)
