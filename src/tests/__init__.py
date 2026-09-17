"""Contract checks — the small, boring half of testing.

    python -m src.tests

What lives here is deliberately narrow: exhaustive comparisons against a single
source of truth, where the work is enumerating every key or column and the
answer is mechanically right or wrong. Reviewing 500 i18n keys by eye is
exactly what a person or an agent is worst at, so a machine does it.

Everything else — does the window lay out, does the capture populate its
columns, does an update download and cancel cleanly — is a self-check area
instead, run through the app's own launch flags and judged by whoever reads the
report:

    python Scripts/check.py        # compiles and imports
    python -m src.main -t all      # behaviour, reported for judgement

There are no fabricated fixtures in this package. Checks that need frames read
a real capture via ``src.selfcheck.data``.
"""

import sys
import traceback

from src.selfcheck.data import NoRealCapture

MODULES = [
    "test_i18n",              # every key, both locales
    "test_csv",               # CSV_COLUMNS vs FrameData, real export/import roundtrip
    "test_release_manifest",  # required manifest fields, URL shape, no BOM
]


def _run_module(name: str) -> tuple[str, str | None]:
    """Run *name*'s ``run()``; return (status, detail)."""
    mod = __import__(f"src.tests.{name}", fromlist=["run"])
    try:
        mod.run()
    except NoRealCapture as exc:
        return ("skip", str(exc))
    except Exception as exc:
        return ("fail", f"{exc}\n{traceback.format_exc()}")
    return ("pass", None)


def main() -> int:
    print("=== contract checks ===\n")
    passed = skipped = failed = 0
    failed_names: list[str] = []

    for name in MODULES:
        status, detail = _run_module(name)
        if status == "pass":
            print(f"  PASS  {name}")
            passed += 1
        elif status == "skip":
            print(f"  SKIP  {name}: {(detail or '').splitlines()[0]}")
            skipped += 1
        else:
            print(f"  FAIL  {name}: {(detail or '').splitlines()[0]}")
            if detail:
                print(detail)
            failed += 1
            failed_names.append(name)

    print(f"\n{passed} passed, {skipped} skipped, {failed} failed")
    if failed:
        print(f"FAILED: {', '.join(failed_names)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
