"""What a self-check area is, independent of how it is run.

A new ``src/selfcheck/<name>_area.py`` that exports ``AREA`` and ``run`` is
picked up automatically: ``-t all``, ``-t <name>``, and the verify planner
all walk the package. There is no central switch to forget to update.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Area:
    """Declaration exported as ``AREA`` from a ``*_area.py`` module."""

    name: str
    # Path prefixes or files that, when changed, select this area.
    # Trailing slash = directory. Empty = never auto-selected (only ``-t``).
    touches: tuple[str, ...] = ()
    needs_qt: bool = False
    needs_admin: bool = False
    # How the report is meant to be read.
    #   parent  — stdout facts are enough; the agent who made the change reads them
    #   visual  — the PNGs are the point; still parent-first, subagent is optional
    #   numbers — fill rates / counts; parent judges against the machine
    judge: str = "parent"
