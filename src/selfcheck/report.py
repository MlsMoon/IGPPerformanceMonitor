"""Report object shared by the self-check areas.

The split matters. ``error`` is for things no one needs to think about — an
exception, a failed import, a missing file — and it is the only thing that
moves the exit code. ``fact`` and ``suspect`` print observations for whoever
reads the transcript (usually an agent) to judge, because "is 4% of AppGPU%
missing normal?" has no threshold worth hard-coding.
"""

from __future__ import annotations

import traceback
from contextlib import contextmanager


class Report:
    """Collects facts and failures for one self-check area."""

    def __init__(self, area: str) -> None:
        self.area = area
        self.errors: list[str] = []
        self.suspects: list[str] = []
        self._width = 34

    # ── output ──────────────────────────────────────────────────────

    def section(self, title: str) -> None:
        print(f"\n[{title}]")

    def fact(self, key: str, value) -> None:
        """An observation. Never fails on its own; the reader decides."""
        print(f"  {key.ljust(self._width)}{value}")

    def suspect(self, message: str) -> None:
        """Looks wrong but is not provably broken. Does not change the exit code."""
        self.suspects.append(message)
        print(f"  SUSPECT  {message}")

    def error(self, message: str) -> None:
        """Provably broken. Fails the run."""
        self.errors.append(message)
        print(f"  ERROR    {message}")

    # ── helpers ─────────────────────────────────────────────────────

    @contextmanager
    def step(self, name: str):
        """Run a block, turning any exception into an error instead of a crash.

        One broken area should still let the rest of the run report its facts —
        a crash halfway through tells the reader much less than a full report
        with one ERROR line in it.
        """
        try:
            yield
        except Exception as exc:
            self.error(f"{name} raised {type(exc).__name__}: {exc}")
            print(traceback.format_exc())

    def summary(self) -> int:
        print(f"\n=== {self.area}: {len(self.errors)} error(s), "
              f"{len(self.suspects)} suspect(s) ===")
        for message in self.errors:
            print(f"  ERROR    {message}")
        for message in self.suspects:
            print(f"  SUSPECT  {message}")
        return 1 if self.errors else 0
