"""Static gate: compile and import every module under src/.

This is the cheap half of testing — it catches syntax errors, bad imports and
circular imports without admin, a display, or a capture. Run it after every
edit; it is the precondition for the `-t` self-checks, which are useless if the
code does not import in the first place.

    python Scripts/check.py            # compile + import + lint
    python Scripts/check.py --quick    # compile only

Exit code is 0 only when everything compiles and imports.
"""

from __future__ import annotations

import argparse
import importlib
import os
import py_compile
import subprocess
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Qt must not try to open a display, and the self-check areas must not be able
# to scribble on the developer's real config while we merely import them.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Modules that are entry points or have import-time side effects we do not want
# during a static sweep.
_SKIP_IMPORT = {
    "src.main",              # argparse + admin relaunch
    "src.tests",             # runs its own harness setup
    "src.auto_updater.main",  # waits on a parent process
}


def _iter_modules() -> list[tuple[str, str]]:
    """Every (module_name, path) under src/, in import order."""
    found: list[tuple[str, str]] = []
    src = os.path.join(_ROOT, "src")
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, _ROOT)
            parts = rel.replace("\\", "/")[:-3].split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
            found.append((".".join(parts), path))
    return found


def _compile(modules: list[tuple[str, str]]) -> list[str]:
    failures = []
    for name, path in modules:
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{name}: {exc.msg.strip()}")
    return failures


def _import(modules: list[tuple[str, str]]) -> list[str]:
    failures = []
    for name, _path in modules:
        if not name or name in _SKIP_IMPORT:
            continue
        try:
            importlib.import_module(name)
        except Exception:
            failures.append(f"{name}:\n{traceback.format_exc()}")
    return failures


def _lint() -> list[str]:
    """pyflakes if it is installed; absence is not a failure."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pyflakes", "src", "Scripts"],
            cwd=_ROOT, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return []
    if proc.returncode == 0:
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="compile only")
    args = parser.parse_args()

    sys.path.insert(0, _ROOT)
    modules = _iter_modules()
    print(f"=== static check ({len(modules)} modules) ===\n")

    failed = False

    compile_failures = _compile(modules)
    print(f"compile  {len(modules) - len(compile_failures)}/{len(modules)} ok")
    for failure in compile_failures:
        print(f"  FAIL  {failure}")
    failed |= bool(compile_failures)

    if not args.quick and not compile_failures:
        importable = [m for m in modules if m[0] and m[0] not in _SKIP_IMPORT]
        import_failures = _import(modules)
        # Name the gap, or the smaller import count reads as a silent failure.
        print(f"import   {len(importable) - len(import_failures)}/{len(importable)} ok "
              f"({len(modules) - len(importable)} skipped: "
              f"{', '.join(sorted(_SKIP_IMPORT))})")
        for failure in import_failures:
            print(f"  FAIL  {failure}")
        failed |= bool(import_failures)

        warnings = _lint()
        print(f"lint     {len(warnings)} warning(s)")
        for warning in warnings:
            print(f"  WARN  {warning}")

    print("\nFAILED" if failed else "\nOK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
