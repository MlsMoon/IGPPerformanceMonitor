"""First-run language: spawn the real GUI entry, pick a locale, keep a window.

``-t ui`` never reaches ``main()`` (it builds its own QApp). Two shipped bugs
lived only on that path: 0.1.5 lastWindowClosed quit after OK, and 0.1.6
``setProperty("locale")`` stored a QLocale so ``ensure_ui_locale`` sys.exit(0).
This area launches a child of ``python -m src.main`` (and the packed EXE when
one is on disk) with a blank ``IGP_CONFIG_DIR`` so the picker actually shows.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from src.selfcheck.report import Report
from src.selfcheck.spec import Area

AREA = Area(
    name="startup",
    judge="parent",
    needs_qt=False,
    needs_admin=False,
    touches=(
        "src/main.py",
        "src/ui/dialogs/language_dialog.py",
        "src/i18n/",
        "src/core/app_config.py",
        "Scripts/build.bat",
    ),
)

_DEADLINE_S = 30.0
_POLL_S = 0.2


def run(report: Report, out_dir: str, **_kwargs) -> None:
    report.section("python entry")
    root = _repo_root()
    _launch(
        report,
        label="python",
        command=[sys.executable, "-m", "src.main"],
        cwd=root,
        skip_admin=True,
        out_dir=out_dir,
    )

    exe = _find_exe(root)
    report.section("frozen exe")
    if exe is None:
        report.fact("exe", "(none — set IGP_SELFCHECK_EXE or build dist\\)")
        return
    report.fact("exe", exe)
    if not _is_admin():
        report.fact(
            "exe skipped",
            "not admin — packed EXE requests UAC; python child still covers main()",
        )
        return
    _launch(
        report,
        label="exe",
        command=[str(exe)],
        cwd=str(exe.parent),
        skip_admin=True,
        out_dir=out_dir,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _find_exe(root: Path) -> Path | None:
    env = os.environ.get("IGP_SELFCHECK_EXE", "").strip()
    if env:
        forced = Path(env)
        if forced.is_file():
            return forced
    candidates = (
        root / "dist" / "IGPPerformanceMonitor.exe",
        root / "temp" / "IGPPerformanceMonitor.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "IGPPerformanceMonitor" / "IGPPerformanceMonitor.exe",
        Path(r"D:\Program Files\IGPPerformanceMonitor\IGPPerformanceMonitor.exe"),
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None
    # dist\ can hold a months-old build; pick the newest so an installed
    # current EXE is tested instead of a stale one that never had the picker.
    return max(existing, key=lambda path: path.stat().st_mtime)


def _is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _launch(
    report: Report,
    *,
    label: str,
    command: list[str],
    cwd: Path | str,
    skip_admin: bool,
    out_dir: str,
) -> None:
    with report.step(f"{label} first-run"):
        with tempfile.TemporaryDirectory(
            prefix="igp-startup-appdata-",
            ignore_cleanup_errors=True,
        ) as appdata:
            probe = Path(out_dir) / f"startup-{label}-shown.txt"
            try:
                probe.unlink()
            except OSError:
                pass
            env = os.environ.copy()
            env.pop("IGP_LANG", None)
            env["IGP_CONFIG_DIR"] = appdata
            env["IGP_SELFCHECK_ACCEPT_LANGUAGE"] = "1"
            env["IGP_STARTUP_PROBE"] = str(probe)
            if skip_admin:
                env["IGP_SKIP_ADMIN"] = "1"
            # Packed EXEs before IGP_CONFIG_DIR only read %APPDATA%. They also
            # bundle PyQt, so sandboxing APPDATA there does not hide imports.
            # The python child must keep the real roaming profile: pip --user
            # packages live there, and `-t ui` may already have pointed the
            # parent APPDATA at a self-check sandbox.
            if label == "exe":
                env["APPDATA"] = appdata
            else:
                real = env.get("IGP_REAL_APPDATA", "").strip()
                roaming = Path.home() / "AppData" / "Roaming"
                if real:
                    env["APPDATA"] = real
                elif roaming.is_dir():
                    env["APPDATA"] = str(roaming)

            err_log = Path(out_dir) / f"startup-{label}.err"
            err_handle = err_log.open("w", encoding="utf-8")
            proc = subprocess.Popen(
                command,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=err_handle,
            )
            try:
                outcome = _wait_for_main(proc, probe)
            finally:
                _stop(proc)
                err_handle.close()

            report.fact(f"{label} command", " ".join(command))
            report.fact(f"{label} probe file", probe.is_file())
            report.fact(f"{label} saved locale", _saved_locale(appdata))
            report.fact(f"{label} outcome", outcome)
            if outcome != "main window shown":
                extra = ""
                try:
                    tail = err_log.read_text(encoding="utf-8", errors="replace")[-800:]
                    if tail.strip():
                        extra = f" child stderr: {tail.strip()}"
                except OSError:
                    pass
                report.error(
                    f"{label}: first-run language picker did not leave a main "
                    f"window ({outcome}). Known causes: lastWindowClosed quit "
                    f"on dialog close (0.1.5); OK stored a QLocale because "
                    f"QWidget.setProperty('locale', ...) does not round-trip "
                    f"a locale code (0.1.6).{extra}"
                )


def _saved_locale(appdata: str) -> str:
    for path in (
        Path(appdata) / "config.json",
        Path(appdata) / "IGPPerformanceMonitor" / "config.json",
    ):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("locale"):
            return str(data["locale"])
    return "(none)"


def _wait_for_main(proc: subprocess.Popen, probe: Path) -> str:
    deadline = time.monotonic() + _DEADLINE_S
    clicked = False
    while time.monotonic() < deadline:
        if probe.is_file():
            return "main window shown"
        code = proc.poll()
        if code is not None:
            if probe.is_file():
                return "main window shown"
            return f"process exited {code} before a main window"
        if not clicked:
            clicked = _click_language_ok(proc.pid)
        elif _has_main_window(proc.pid):
            return "main window shown"
        time.sleep(_POLL_S)
    if probe.is_file() or _has_main_window(proc.pid):
        return "main window shown"
    return "timed out waiting for main window"


def _stop(proc: subprocess.Popen) -> None:
    # Onefile EXEs spawn a child; killing only the bootloader leaves it holding
    # the stderr handle and the sandbox directory.
    if sys.platform == "win32" and proc.pid:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        return
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except OSError:
            pass


def _click_language_ok(pid: int) -> bool:
    """Enter on the picker HWND — used when the child is an older packed EXE."""
    for hwnd, title in _windows_for_pid(pid):
        if _is_language_title(title):
            _send_enter(hwnd)
            return True
    return False


def _has_main_window(pid: int) -> bool:
    return any(_is_main_title(title) for _hwnd, title in _windows_for_pid(pid))


def _is_language_title(title: str) -> bool:
    lower = title.lower()
    return "language" in lower or "语言" in title


def _is_main_title(title: str) -> bool:
    return "IGP Performance Monitor" in title or "IGP 性能监控器" in title


def _windows_for_pid(pid: int) -> list[tuple[int, str]]:
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hits: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        found = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found))
        if found.value != pid:
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        title = buf.value
        if title:
            hits.append((int(hwnd), title))
        return True

    user32.EnumWindows(_enum, 0)
    return hits


def _send_enter(hwnd: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    wm_keydown = 0x0100
    wm_keyup = 0x0101
    vk_return = 0x0D
    user32.SetForegroundWindow(hwnd)
    user32.PostMessageW(hwnd, wm_keydown, vk_return, 0)
    user32.PostMessageW(hwnd, wm_keyup, vk_return, 0)
