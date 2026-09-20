"""``python -m src.selfcheck plan`` — print what to run for the current diff."""

from __future__ import annotations

import argparse
import sys

from src.selfcheck.plan import collect_changed, plan, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan or run self-checks. Areas are discovered from *_area.py.")
    sub = parser.add_subparsers(dest="cmd")

    plan_p = sub.add_parser("plan", help="print what to run for the current git diff")
    plan_p.add_argument("paths", nargs="*", help="limit to these paths (default: git status)")
    plan_p.add_argument("--user-asked", action="store_true",
                        help="the user explicitly asked to verify")
    plan_p.add_argument("--commit", action="store_true",
                        help="this change is about to be committed")
    plan_p.add_argument("--suspect", action="store_true",
                        help="a report already has an unexplained SUSPECT")

    args = parser.parse_args(argv)
    if args.cmd != "plan":
        parser.print_help()
        print("\nTo run an area:  python -m src.main -t ui|startup|capture|update|all",
              file=sys.stderr)
        return 2

    changed = collect_changed(args.paths or None)
    print(render(plan(
        changed,
        user_asked=args.user_asked,
        about_to_commit=args.commit,
        unexplained_suspect=args.suspect,
    )))
    return 0


if __name__ == "__main__":
    sys.exit(main())
