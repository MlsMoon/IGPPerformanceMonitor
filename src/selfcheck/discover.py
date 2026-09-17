"""Find every ``*_area.py`` and the ``AREA`` it exports.

Import happens here, not at ``selfcheck`` package import time, so an area
module can ``from src import selfcheck`` without a circular import.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

from src.selfcheck.spec import Area

_cache: list[tuple[Area, Callable]] | None = None


def discover() -> list[tuple[Area, Callable]]:
    """``(AREA, run)`` pairs, sorted by name. Cached after the first call."""
    global _cache
    if _cache is None:
        _cache = _scan()
    return _cache


def area_names() -> tuple[str, ...]:
    return tuple(spec.name for spec, _run in discover())


def get(name: str) -> tuple[Area, Callable]:
    for spec, run in discover():
        if spec.name == name:
            return spec, run
    known = ", ".join(area_names()) or "(none)"
    raise ValueError(f"unknown area {name!r}; expected one of {known} or all")


def _scan() -> list[tuple[Area, Callable]]:
    found: list[tuple[Area, Callable]] = []
    import src.selfcheck as pkg
    for module_info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        short = module_info.name.rsplit(".", 1)[-1]
        if not short.endswith("_area"):
            continue
        module = importlib.import_module(module_info.name)
        run = getattr(module, "run", None)
        if not callable(run):
            continue
        spec = getattr(module, "AREA", None)
        if spec is None:
            spec = Area(name=short[: -len("_area")])
        found.append((spec, run))
    found.sort(key=lambda pair: pair[0].name)
    return found
