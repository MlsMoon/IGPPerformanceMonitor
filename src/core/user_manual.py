"""Locate bundled user-manual markdown (dev tree or PyInstaller ``_MEIPASS``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.core.app_info import resource_root
from src.i18n import get_locale

# In-document TOCs are replaced by the dialog tree — skip these headings.
_TOC_TITLES = frozenset({"contents", "目录", "目錄", "目次"})
_LANG_NAV = re.compile(
    r"\[(English|简体中文|繁體中文|日本語)\]\s*\(",
)

# Left-nav pages in display order. Filenames match docs/<locale>/.
PAGES: tuple[tuple[str, str], ...] = (
    ("user-guide", "user_manual_page_guide"),
    ("troubleshooting", "user_manual_page_troubleshooting"),
)

PAGE_FILES: dict[str, str] = {page_id: f"{page_id}.md" for page_id, _key in PAGES}

_LOCALE_FOLDERS = {
    "zh_CN": "zh-CN",
    "en": "en",
}


def docs_root() -> Path:
    """``docs/`` next to VERSION — project root in dev, ``_MEIPASS`` when frozen."""
    return resource_root() / "docs"


def locale_folder(locale: str | None = None) -> str:
    """Map a UI locale to a docs/ folder. Unknown locales fall back to English."""
    loc = get_locale() if locale is None else locale
    return _LOCALE_FOLDERS.get(loc, "en")


def page_path(page_id: str, locale: str | None = None) -> Path:
    filename = PAGE_FILES.get(page_id)
    if filename is None:
        raise KeyError(f"unknown manual page: {page_id}")
    return docs_root() / locale_folder(locale) / filename


def load_page(page_id: str, locale: str | None = None) -> str:
    """Return markdown text, or empty string if the file is missing."""
    try:
        return page_path(page_id, locale).read_text(encoding="utf-8")
    except OSError:
        return ""


@dataclass(frozen=True)
class OutlineNode:
    """One markdown heading for the in-app manual tree."""

    level: int
    title: str
    slug: str


def _slugify(title: str, used: set[str]) -> str:
    raw = re.sub(r"\s*\{#[\w-]+\}\s*$", "", title).strip().lower()
    raw = re.sub(r"[^\w\s-]", "", raw, flags=re.UNICODE)
    raw = re.sub(r"[-\s]+", "-", raw).strip("-") or "section"
    slug = raw
    n = 2
    while slug in used:
        slug = f"{raw}-{n}"
        n += 1
    used.add(slug)
    return slug


def is_toc_title(title: str) -> bool:
    return title.strip().casefold() in _TOC_TITLES


def page_outline(markdown: str) -> list[OutlineNode]:
    """Headings below the document H1, skipping the Contents / 目录 block."""
    used: set[str] = set()
    nodes: list[OutlineNode] = []
    skip_first_h1 = True
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = re.sub(r"\s*\{#[\w-]+\}\s*$", "", match.group(2)).strip()
        if skip_first_h1 and level == 1:
            skip_first_h1 = False
            continue
        skip_first_h1 = False
        if is_toc_title(title):
            continue
        nodes.append(OutlineNode(level, title, _slugify(title, used)))
    return nodes


def strip_contents_section(markdown: str) -> str:
    """Drop the Contents / 目录 heading and the lines until the next heading."""
    out: list[str] = []
    skipping = False
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            title = re.sub(r"\s*\{#[\w-]+\}\s*$", "", match.group(2)).strip()
            if is_toc_title(title):
                skipping = True
                continue
            skipping = False
        if skipping:
            continue
        out.append(line)
    return "\n".join(out)


def strip_language_nav(markdown: str) -> str:
    """Drop the inter-locale switcher row (those links are for GitHub, not the app)."""
    out: list[str] = []
    for line in markdown.splitlines():
        if _LANG_NAV.search(line) and line.count("](") >= 2:
            continue
        out.append(line)
    return "\n".join(out)


def prepare_in_app_markdown(markdown: str) -> str:
    """Body shown in the dialog: no language row, no in-document TOC."""
    return strip_contents_section(strip_language_nav(markdown)).strip()


def page_id_for_path(path: Path) -> str | None:
    """Return the nav page id if *path* is a known manual file, else None."""
    name = path.name.lower()
    for page_id, filename in PAGE_FILES.items():
        if name == filename.lower():
            return page_id
    return None


def resolve_doc_href(current_file: Path, href: str) -> Path | None:
    """Resolve a markdown href to a ``.md`` file under ``docs/``, or None.

    Rejects http(s), mailto, and anything that escapes the docs tree.
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith(("http://", "https://", "mailto:")):
        return None

    path_part = href.split("#", 1)[0]
    if not path_part:
        return None

    if path_part.startswith("file:"):
        parsed = urlparse(path_part)
        local = unquote(parsed.path)
        if local.startswith("/") and len(local) >= 3 and local[2] == ":":
            local = local[1:]
        candidate = Path(local)
    else:
        candidate = Path(path_part)
        if not candidate.is_absolute():
            candidate = current_file.parent / candidate

    try:
        candidate = candidate.resolve()
        candidate.relative_to(docs_root().resolve())
    except (OSError, ValueError):
        return None
    if candidate.suffix.lower() != ".md" or not candidate.is_file():
        return None
    return candidate
