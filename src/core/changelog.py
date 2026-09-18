"""Locate and parse bundled changelog markdown (dev tree or PyInstaller ``_MEIPASS``)."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.app_info import resource_root
from src.i18n import get_locale

# UI locale → filename at resource_root(). Unknown locales fall back to English.
_FILES = {
    "zh_CN": "CHANGELOG.zh-CN.md",
    "en": "CHANGELOG.md",
}

_VERSION_HEADING = re.compile(r"^## (\d+\.\d+\.\d+)\s*$")


def changelog_filename(locale: str | None = None) -> str:
    """Filename for this UI locale. Unknown locales use the English file."""
    loc = get_locale() if locale is None else locale
    return _FILES.get(loc, _FILES["en"])


def changelog_path(locale: str | None = None) -> Path:
    return resource_root() / changelog_filename(locale)


def load_raw(locale: str | None = None) -> str:
    """Return markdown text. Missing locale file falls back to English."""
    path = changelog_path(locale)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    if text:
        return text
    if changelog_filename(locale) != _FILES["en"]:
        return load_raw("en")
    return ""


def parse_versions(raw: str) -> list[tuple[str, str]]:
    """Split changelog markdown into ``[(version, markdown_block), …]``.

    Blocks are delimited by ``## X.Y.Z`` lines (semver only). The top-level
    ``# Changelog`` / ``# 更新记录`` title is skipped, as are any other
    non-semver ``##`` headings.
    """
    if not raw:
        return []
    blocks = re.split(r"\n(?=## )", raw)
    versions: list[tuple[str, str]] = []
    for block in blocks:
        block = block.strip()
        first_line = block.split("\n", 1)[0]
        match = _VERSION_HEADING.match(first_line)
        if match:
            versions.append((match.group(1), block))
    return versions


def version_ids(raw: str) -> list[str]:
    return [ver for ver, _ in parse_versions(raw)]
