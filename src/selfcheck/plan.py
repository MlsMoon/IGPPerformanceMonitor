"""Decide what to run after a change, and whether a subagent is warranted.

The default is: the agent who made the change runs the gate and the matching
areas, and reads the report itself. A subagent is a second pair of eyes, not
the test runner — it is the exception, not the loop.

Path coverage is derived from each area's ``AREA.touches``. A new ``src/``
package that no area claims shows up as ``UNCOVERED``, which is how this
planner expands with the project instead of rotting as a hardcoded table.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field

from src.selfcheck.discover import discover

# First-party trees that are not product code. Uncovered-package detection
# skips these so a new feature package under src/ is what gets flagged.
_NOT_PRODUCT = (
    "src/selfcheck/",
    "src/tests/",
    "src/__init__.py",
)

# Contract checks are exhaustive comparisons. They select on the single
# source they walk, not on "any file that felt related".
_CONTRACTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("src/i18n/",), "test_i18n"),
    (("src/core/metrics_schema.py", "src/models.py",
      "src/core/csv_importer.py"), "test_csv"),
    (("src/core/release_manifest.py", "src/core/app_info.py"),
     "test_release_manifest"),
)

# Paths whose change is about how the window *looks*. Combined with a visual
# area, these are the only files that can justify a subagent.
_VISUAL_MARKERS = (
    "/theme.py",
    "/motion.py",
    "/win_chrome.py",
    "/chart_base.py",
    "/monitor_view.py",
    "/overlay_window.py",
    "/flow_layout.py",
    "/collapsible_section.py",
    "/system_info_panel.py",
    "/chart_visibility_panel.py",
    "/process_panel.py",
    "/dpi.py",
    "assets/",
    ".qss",
)

@dataclass
class Plan:
    """What to run, who reads it, and why."""

    changed: list[str]
    static: bool
    areas: list[str]
    contracts: list[str]
    subagent: bool
    judge: str
    reasons: list[str] = field(default_factory=list)
    uncovered: list[str] = field(default_factory=list)

    def needs_admin(self) -> bool:
        specs = {spec.name: spec for spec, _ in discover()}
        return any(specs[name].needs_admin for name in self.areas if name in specs)


def collect_changed(explicit: list[str] | None = None, *, root: str | None = None) -> list[str]:
    """Changed paths: *explicit*, or ``git status`` / ``git diff`` against HEAD."""
    if explicit:
        return [_norm(p) for p in explicit]
    root = root or _repo_root()
    found: set[str] = set()
    for args in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            proc = subprocess.run(
                args, cwd=root, capture_output=True, text=True, check=False,
            )
        except OSError:
            continue
        for line in proc.stdout.splitlines():
            path = _norm(line)
            if path:
                found.add(path)
    return sorted(found)


def plan(changed: list[str] | None = None, *,
         user_asked: bool = False,
         about_to_commit: bool = False,
         unexplained_suspect: bool = False) -> Plan:
    """Build a verify plan from the changed paths and a few situational flags.

    *user_asked* / *about_to_commit* / *unexplained_suspect* are the only
    knobs a caller has to set. Everything else is derived from the files and
    each area's ``AREA`` declaration.
    """
    paths = collect_changed(changed)
    areas = _select_areas(paths)
    contracts = _select_contracts(paths)
    uncovered = _uncovered_packages(paths)
    product = any(_is_product(p) for p in paths) or any(
        p.startswith("Scripts/") and p.endswith(".py") for p in paths
    )
    selfcheck_changed = any(
        p.startswith("src/selfcheck/") or p == "Scripts/check.py" for p in paths
    )
    visual = any(_is_visual(p) for p in paths)
    cross_cutting = len(areas) >= 3

    reasons: list[str] = []
    if not paths:
        reasons.append("no changed files - static gate only, as a pulse check")
    if product or selfcheck_changed:
        reasons.append("product or check code changed - static gate is required")
    if not areas and not contracts and product:
        reasons.append(
            "no area claims these paths - static gate only; add AREA.touches "
            "or a new *_area.py if behaviour needs exercising")
    if visual:
        reasons.append("visual files changed - parent opens the PNGs")
    if uncovered:
        reasons.append(
            "new src/ tree has no area - declare AREA.touches on an existing "
            "area or add a *_area.py (this is how coverage grows)")

    subagent = False
    judge = "parent"
    if selfcheck_changed and areas:
        subagent = True
        judge = "subagent"
        reasons.append("self-check machinery changed - a fresh reader dogfoods it")
    elif user_asked and (visual or unexplained_suspect or cross_cutting):
        subagent = True
        judge = "subagent"
        reasons.append("user asked to verify a visual / ambiguous / wide change")
    elif about_to_commit and visual:
        subagent = True
        judge = "subagent"
        reasons.append("UI-facing change about to be committed - second pair of eyes on the PNGs")
    elif unexplained_suspect:
        subagent = True
        judge = "subagent"
        reasons.append("report has an unexplained SUSPECT the author should not mark as fine")
    elif cross_cutting and about_to_commit:
        subagent = True
        judge = "subagent"
        reasons.append("three or more areas about to ship together")
    else:
        if visual:
            reasons.append(
                "do not spawn a subagent: you have the change in context, "
                "open temp/selfcheck/shots/ yourself")
        if areas:
            reasons.append("read the report in this turn; ERROR fails, SUSPECT you judge")

    return Plan(
        changed=paths,
        static=product or selfcheck_changed or not paths,
        areas=areas,
        contracts=contracts,
        subagent=subagent,
        judge=judge,
        reasons=reasons,
        uncovered=uncovered,
    )


def render(plan_: Plan) -> str:
    """Human-readable plan. An agent follows this instead of a habit."""
    lines = ["=== verify plan ===", ""]
    lines.append("changed:    " + (" ".join(plan_.changed) if plan_.changed else "(none)"))
    lines.append(f"static:     {'yes  python Scripts/check.py' if plan_.static else 'no'}")
    if plan_.areas:
        lines.append(f"areas:      {' '.join(plan_.areas)}")
    else:
        lines.append("areas:      (none)")
    lines.append("contracts:  " + (
        f"yes  python -m src.tests   ({', '.join(plan_.contracts)})"
        if plan_.contracts else "no"))
    lines.append(f"judge:      {plan_.judge}")
    lines.append(f"subagent:   {'yes' if plan_.subagent else 'no'}")
    if plan_.uncovered:
        lines.append("UNCOVERED:  " + " ".join(plan_.uncovered))
    if plan_.reasons:
        lines.append("")
        for reason in plan_.reasons:
            lines.append(f"- {reason}")
    lines.append("")
    lines.append(_commands(plan_))
    return "\n".join(lines)


def _commands(plan_: Plan) -> str:
    steps = []
    if plan_.static:
        steps.append("python Scripts/check.py")
    if plan_.areas:
        if plan_.needs_admin() and len(plan_.areas) == 1:
            steps.append("Scripts\\selfcheck.bat " + " ".join(plan_.areas))
        elif plan_.needs_admin():
            others = [a for a in plan_.areas if a != "capture"]
            if others:
                steps.append("python -m src.main -t " + " ".join(others))
            steps.append("Scripts\\selfcheck.bat capture")
        else:
            steps.append("python -m src.main -t " + " ".join(plan_.areas))
    if plan_.contracts:
        steps.append("python -m src.tests")
    if not plan_.subagent and any(
        spec.judge == "visual"
        for spec, _ in discover() if spec.name in plan_.areas
    ):
        steps.append("# open temp/selfcheck/shots/ yourself - do not spawn a subagent")
    if plan_.subagent:
        steps.append("# THEN spawn a subagent to read the report + PNGs; do not have it re-run the commands")
    return "then:\n  " + "\n  ".join(steps) if steps else "then: (nothing)"


def _select_areas(paths: list[str]) -> list[str]:
    selected: list[str] = []
    for spec, _run in discover():
        if spec.name in selected:
            continue
        if any(_matches(path, spec.touches) for path in paths):
            selected.append(spec.name)
    if any(p.startswith("src/selfcheck/") for p in paths):
        # Changing the machinery should exercise every area it can still run
        # without admin. capture stays opt-in (UAC).
        for spec, _run in discover():
            if spec.name not in selected and not spec.needs_admin:
                selected.append(spec.name)
    return selected


def _select_contracts(paths: list[str]) -> list[str]:
    picked: list[str] = []
    for prefixes, name in _CONTRACTS:
        if any(_matches(path, prefixes) for path in paths):
            picked.append(name)
    return picked


def _uncovered_packages(paths: list[str]) -> list[str]:
    """New (or touched) src/ packages that no area's touches claim.

    That is the expand signal: the next ``*_area.py`` or a wider ``touches``
    tuple is how coverage grows, not a new file under ``src/tests/``.
    """
    claimed = []
    for spec, _run in discover():
        claimed.extend(spec.touches)
    hit: set[str] = set()
    for path in paths:
        if not path.startswith("src/") or _is_skipped(path):
            continue
        parts = path.split("/")
        if len(parts) < 3:
            continue  # src/main.py — an entry file, not a feature package
        owner = f"src/{parts[1]}/"
        if _is_skipped(owner):
            continue
        if not _matches(path, tuple(claimed)):
            hit.add(owner)
    return sorted(hit)


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    path = _norm(path)
    for prefix in prefixes:
        prefix = _norm(prefix)
        if not prefix:
            continue
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return True
        elif path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _is_visual(path: str) -> bool:
    path = _norm(path)
    return any(marker in path or path.endswith(marker) for marker in _VISUAL_MARKERS)


def _is_product(path: str) -> bool:
    path = _norm(path)
    return path.startswith("src/") and not _is_skipped(path)


def _is_skipped(path: str) -> bool:
    path = _norm(path)
    return any(path == p.rstrip("/") or path.startswith(p) for p in _NOT_PRODUCT)


def _norm(path: str) -> str:
    return path.strip().replace("\\", "/")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
