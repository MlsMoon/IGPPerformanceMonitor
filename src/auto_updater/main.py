"""Auto updater entry point — standalone EXE."""

import sys
from pathlib import Path

from src.auto_updater.args import build_parser
from src.auto_updater.logging_utils import write_log
from src.auto_updater.replace_service import ReplaceCommand, ReplaceError, ReplaceService


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = ReplaceCommand(
        parent_pid=args.parent_pid,
        source_exe=Path(args.source_exe),
        target_exe=Path(args.target_exe),
        backup_exe=Path(args.backup_exe),
        state_path=Path(args.state_path),
        target_version=str(args.target_version),
        updated_at=str(args.updated_at),
        log_path=str(args.log_path),
        restart=str(args.restart).lower() == "true",
    )
    try:
        ReplaceService().run(command)
        return 0
    except ReplaceError as exc:
        write_log(command.log_path, f"Auto updater failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
