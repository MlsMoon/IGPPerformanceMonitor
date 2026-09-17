"""Core file-replacement logic for auto_updater."""

import ctypes
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from src.auto_updater.logging_utils import write_log

_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004


class ReplaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplaceCommand:
    parent_pid: int
    source_exe: Path
    target_exe: Path
    backup_exe: Path
    state_path: Path
    target_version: str
    updated_at: str
    log_path: str
    restart: bool


class ReplaceService:
    def run(self, command: ReplaceCommand) -> None:
        write_log(command.log_path, "Auto updater started.")
        self._wait_for_parent_exit(command.parent_pid, command.log_path)
        self._replace_executable(command)
        self._write_state(command)
        if command.restart:
            self._restart_target(command)
        self._cleanup(command)
        write_log(command.log_path, "Auto updater finished successfully.")

    def _wait_for_parent_exit(self, pid: int, log_path: str, timeout_ms: int = 30000) -> None:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            _SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            write_log(log_path, f"Parent process {pid} is already unavailable.")
            return
        try:
            wait_result = kernel32.WaitForSingleObject(handle, timeout_ms)
            if wait_result not in {_WAIT_OBJECT_0, 0}:
                if wait_result == _WAIT_TIMEOUT:
                    raise ReplaceError(f"Timed out waiting for process {pid} to exit.")
                raise ReplaceError(f"Unexpected wait result: {wait_result}.")
        finally:
            kernel32.CloseHandle(handle)

    def _replace_executable(self, command: ReplaceCommand) -> None:
        if not command.source_exe.exists():
            raise ReplaceError(f"Replacement EXE not found: {command.source_exe}")
        command.target_exe.parent.mkdir(parents=True, exist_ok=True)
        if command.backup_exe.exists():
            command.backup_exe.unlink()
        backup_created = False
        try:
            if command.target_exe.exists():
                shutil.move(str(command.target_exe), str(command.backup_exe))
                backup_created = True
            shutil.move(str(command.source_exe), str(command.target_exe))
        except Exception:
            if not command.target_exe.exists() and backup_created and command.backup_exe.exists():
                shutil.move(str(command.backup_exe), str(command.target_exe))
            raise

    def _write_state(self, command: ReplaceCommand) -> None:
        payload = {"version": command.target_version, "updatedAt": command.updated_at}
        command.state_path.parent.mkdir(parents=True, exist_ok=True)
        command.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _restart_target(self, command: ReplaceCommand) -> None:
        subprocess.Popen([str(command.target_exe)], close_fds=True)

    def _cleanup(self, command: ReplaceCommand) -> None:
        for path in (command.backup_exe, command.source_exe):
            if not path.exists():
                continue
            for _ in range(5):
                try:
                    path.unlink()
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    time.sleep(0.5)
                except OSError:
                    break
